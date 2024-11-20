import { Page } from 'playwright';
import { LoginConfig, CrawlerError, CrawlerErrorType, FormField, CaptchaConfig, StorageState, PreLoginStep } from '../../types/crawler';
import { KeyValueStore, Log } from '@crawlee/core';
import { CaptchaServiceFactory } from '../../services/captcha/factory';
import { CaptchaServiceType } from '../../services/captcha/types';
import { sleep } from 'crawlee';

export class LoginHandler {
    private readonly keyValueStore: KeyValueStore;
    private readonly log: Log;

    constructor(keyValueStore: KeyValueStore, log: Log) {
        this.keyValueStore = keyValueStore;
        this.log = log;
    }

    /**
     * 填写表单字段
     */
    private async fillFormField(page: Page, field: FormField): Promise<void> {
        const element = await page.$(field.selector);
        if (!element) {
            if (field.required) {
                throw new Error(`Required field not found: ${field.name}`);
            }
            return;
        }

        try {
            switch (field.type) {
                case 'text':
                case 'password':
                    await element.fill(field.value as string);
                    break;
                case 'checkbox':
                    if (field.value) {
                        await element.check();
                    } else {
                        await element.uncheck();
                    }
                    break;
                case 'radio':
                    await element.check();
                    break;
                case 'hidden':
                    await page.evaluate(
                        ({ selector, value }: { selector: string; value: string }) => {
                            const el = document.querySelector(selector) as HTMLInputElement;
                            if (el) el.value = value;
                        },
                        { selector: field.selector, value: field.value as string }
                    );
                    break;
            }

            this.log.debug(`Field filled: ${field.name}`, {
                type: field.type,
                selector: field.selector
            });
        } catch (error) {
            throw new Error(`Failed to fill field ${field.name}: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    /**
     * 处理验证码
     */
    private async handleCaptcha(page: Page, captchaConfig?: CaptchaConfig): Promise<void> {
        if (!captchaConfig) {
            this.log.debug('No captcha configuration provided, skipping captcha handling');
            return;
        }

        // 检查是否需要跳过验证码
        if (captchaConfig.solver.type === 'skip') {
            this.log.debug('Captcha handling is configured to be skipped for this site');
            return;
        }

        try {
            // 获取验证码图片
            let captchaImage: Buffer | null = null;

            if (captchaConfig.getCaptchaImage) {
                // 使用站点特定的验证码获取方法
                captchaImage = await captchaConfig.getCaptchaImage(page);
            } else {
                // 使用默认的验证码获取逻辑
                const imgElement = await page.$(captchaConfig.element.selector);
                if (!imgElement) throw new Error('Captcha image not found');
            }

            // 验证必需的配置
            if (!captchaConfig.solver.config?.apiKey) {
                throw new Error('Captcha API key is required');
            }

            // 解析验证码
            const captchaService = CaptchaServiceFactory.createService({
                type: captchaConfig.solver.type,
                apiKey: captchaConfig.solver.config.apiKey,
                apiUrl: captchaConfig.solver.config.apiUrl || undefined,
                timeout: captchaConfig.solver.config.timeout,
                retries: captchaConfig.solver.config.retries
            });
            
            if (!captchaImage) {
                throw new Error('Captcha image not found or failed to download');
            }
            
            const captchaResult = await captchaService.solve(captchaImage);

            // 处理验证码 hash
            if (captchaConfig.hash) {
                const hashElement = await page.$(captchaConfig.hash.selector);
                if (hashElement) {
                    const hash = await hashElement.getAttribute('value');
                    if (hash) {
                        await this.fillFormField(page, {
                            name: captchaConfig.hash.targetField,
                            type: 'hidden',
                            selector: `input[name="${captchaConfig.hash.targetField}"]`,
                            value: hash
                        });
                    }
                }
            }

            // 填写验证码
            await this.fillFormField(page, {
                ...captchaConfig.input,
                value: captchaResult
            });

        } catch (error) {
            throw new Error(`Captcha handling failed: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    /**
     * 执行登录流程
     */
    public async performLogin(page: Page, config: LoginConfig): Promise<void> {
        try {
            this.log.info('Starting login process...', { url: config.loginUrl });
            
            // 导航到登录页面
            await page.goto(config.loginUrl, { 
                waitUntil: 'networkidle',
                timeout: 30000 
            });

            // 首先执行登录前的准备步骤（如点击登录按钮显示表单）
            if (config.preLoginSteps) {
                for (const step of config.preLoginSteps) {
                    await this.executePreLoginStep(page, step);
                }
            }
            // const screenshot = await page.screenshot({
            //     fullPage: true,
            //     path: `after-pre-login-steps-${Date.now()}.png`
            // });
            // await this.keyValueStore.setValue(
            //     `after-pre-login-steps-screenshot-${Date.now()}`,
            //     screenshot
            // );
            // 调试表单选择器
            const formDebugInfo = await page.evaluate((selector) => {
                const form = document.querySelector(selector);
                if (!form) return { exists: false };
                
                return {
                    exists: true,
                    id: form.id,
                    action: (form as HTMLFormElement).action,
                    method: (form as HTMLFormElement).method,
                    classList: Array.from(form.classList),
                    style: {
                        display: window.getComputedStyle(form).display,
                        visibility: window.getComputedStyle(form).visibility,
                        opacity: window.getComputedStyle(form).opacity
                    },
                    html: form.outerHTML
                };
            }, config.formSelector);

            this.log.info('Form selector debug info:', formDebugInfo);

            // 使用 locator API 等待表单渲染和可交互
            const formLocator = page.locator(config.formSelector);
            await formLocator.waitFor();

            // 确保表单真正可交互
            await formLocator.evaluate((form) => {
                const style = window.getComputedStyle(form);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                    throw new Error('Form is not truly visible');
                }
            });

            // 获取验证码图片
            let captchaImage: Buffer | undefined;
            let captchaUrl: string | undefined;
            let captchaContentType: string | undefined;

            if (config.fields.captcha && config.fields.captcha.solver.type !== 'skip') {
                const imgElement = await page.$(config.fields.captcha.element.selector);
                if (!imgElement) throw new Error('Captcha image not found');

                const captchaImage = config.fields.captcha.getCaptchaImage ? await config.fields.captcha.getCaptchaImage(page) : undefined;

                this.log.info('Captcha image downloaded', {
                    size: captchaImage?.length,
                    contentType: captchaContentType,
                    url: captchaUrl
                });
            }

            // 填写用户名和密码
            await sleep(1000);
            await this.fillFormField(page, {
                ...config.fields.username,
                value: config.fields.username.value
            });
            await sleep(1000);
            await this.fillFormField(page, {
                ...config.fields.password,
                value: config.fields.password.value
            });

            // 处理验证码
            if (config.fields.captcha) {
                await this.handleCaptcha(page, config.fields.captcha);
            } else {
                this.log.debug('No captcha configuration in login config, skipping captcha step');
            }

            // 填写其他字段
            if (config.fields.other) {
                for (const field of config.fields.other) {
                    await this.fillFormField(page, field);
                }
            }

            // 提交表单
            await this.handleLoginSubmission(page, config.formSelector, config.successCheck);

            // 保存登录状态
            await this.saveLoginState(page, config);
            
            this.log.info('Login successful');
            
        } catch (error) {
            // 保存页面快照
            try {
                const screenshot = await page.screenshot({
                    fullPage: true,
                    path: `login-error-${Date.now()}.png`
                });
                await this.keyValueStore.setValue(
                    `login-error-screenshot-${Date.now()}`,
                    screenshot
                );
                
                // 保存页面HTML
                const html = await page.content();
                await this.keyValueStore.setValue(
                    `login-error-html-${Date.now()}`,
                    html
                );
            } catch (screenshotError) {
                this.log.error('Failed to save error evidence', { 
                    error: screenshotError instanceof Error ? screenshotError.message : String(screenshotError)
                });
            }

            const errorMessage = error instanceof Error 
                ? error.message 
                : 'Unknown login error';
            
            this.log.error('Login failed', { error: errorMessage });
            await this.handleLoginError(
                error instanceof Error ? error : new Error(errorMessage)
            );
        }
    }

    /**
     * 检查是否已经登录
     */
    private async isAlreadyLoggedIn(page: Page, successCheck: LoginConfig['successCheck']): Promise<boolean> {
        try {
            await page.waitForSelector(successCheck.selector, { timeout: 5000 });
            if (successCheck.expectedText) {
                const text = await page.textContent(successCheck.selector);
                return text?.includes(successCheck.expectedText) ?? false;
            }
            return true;
        } catch {
            return false;
        }
    }

    /**
     * 处理登录提交
     */
    private async handleLoginSubmission(
        page: Page,
        formSelector: string,
        successCheck: LoginConfig['successCheck']
    ): Promise<void> {
        this.log.info('Preparing to submit login form...', {
            formSelector,
            successCheckSelector: successCheck.selector,
            expectedText: successCheck.expectedText
        });

        // 提交前保存页面状态
        const beforeSubmitScreenshot = await page.screenshot({
            fullPage: true,
            path: `before-submit-${Date.now()}.png`
        });
        await this.keyValueStore.setValue(
            `before-submit-screenshot-${Date.now()}`,
            beforeSubmitScreenshot
        );
        this.log.info('Before-submit screenshot saved');

        try {
            // 检查表单是否仍然存在
            const formExists = await page.$(formSelector);
            if (!formExists) {
                throw new Error(`Form not found with selector: ${formSelector}`);
            }

            // 检查提交按钮是否存在
            const submitButton = await page.$(`${formSelector} [type="submit"]`);
            if (!submitButton) {
                throw new Error('Submit button not found');
            }

            // 记录当前URL
            const currentUrl = page.url();
            this.log.info('Current page before submission', { url: currentUrl });

            // 提交表单前记录表单状态
            const formState = await page.evaluate((selector) => {
                const form = document.querySelector(selector);
                if (!form) return null;
                const inputs = Array.from(form.querySelectorAll('input'));
                return inputs.map(input => ({
                    name: input.name,
                    type: input.type,
                    value: input.type === 'password' ? '***' : input.value
                }));
            }, formSelector);
            
            this.log.info('Form state before submission', { formState });

            // 提交表单
            try {
                await Promise.all([
                    page.waitForNavigation({ 
                        waitUntil: 'networkidle',
                        timeout: 30000 
                    }),
                    page.click(`${formSelector} [type="submit"]`),
                ]);
            } catch (navigationError) {
                this.log.error('Navigation error during form submission', {
                    error: navigationError instanceof Error ? navigationError.message : String(navigationError),
                    currentUrl: page.url()
                });
                throw navigationError;
            }

            this.log.info('Form submitted, checking for success indicator...', { 
                selector: successCheck.selector,
                expectedText: successCheck.expectedText,
                currentUrl: page.url()
            });

            // 等待成功标识
            try {
                await page.waitForSelector(successCheck.selector, { timeout: 10000 });
            } catch (selectorError) {
                // 获取页面上所有可见的文本内容，帮助诊断
                const pageText = await page.evaluate(() => document.body.innerText);
                this.log.error('Failed to find success indicator', {
                    selector: successCheck.selector,
                    currentUrl: page.url(),
                    visibleText: pageText.substring(0, 200) + '...' // 只记录前200个字符
                });
                throw selectorError;
            }
            
            if (successCheck.expectedText) {
                const text = await page.textContent(successCheck.selector);
                this.log.info('Found success indicator text', { 
                    actualText: text,
                    expectedText: successCheck.expectedText,
                    matches: text?.includes(successCheck.expectedText)
                });
                
                if (!text?.includes(successCheck.expectedText)) {
                    throw new Error(`Login success check failed: expected "${successCheck.expectedText}" but found "${text}"`);
                }

                // 登录成功，保存页面内容
                const successPageHtml = await page.content();
                await this.keyValueStore.setValue(
                    `login-success-html-${Date.now()}`,
                    successPageHtml
                );
                this.log.info('Login success page saved');

                // 保存成功页面的截图
                const successScreenshot = await page.screenshot({
                    fullPage: true,
                    path: `login-success-${Date.now()}.png`
                });
                await this.keyValueStore.setValue(
                    `login-success-screenshot-${Date.now()}`,
                    successScreenshot
                );
                this.log.info('Login success screenshot saved');
            }

            this.log.info('Login submission successful', {
                finalUrl: page.url()
            });
        } catch (error) {
            // 保存当前页面状态
            try {
                // 保存完整的页面HTML
                const html = await page.content();
                await this.keyValueStore.setValue(
                    `login-error-html-${Date.now()}`,
                    html
                );

                // 获取所有可见的错误信息
                const errorMessages = await page.evaluate(() => {
                    const errorElements = document.querySelectorAll('.error, .alert, [role="alert"], .message');
                    return Array.from(errorElements).map(el => ({
                        text: el.textContent,
                        className: el.className,
                        id: el.id
                    }));
                });

                // 获取当前URL和页面标题
                const diagnosticInfo = {
                    url: page.url(),
                    title: await page.title(),
                    errorMessages,
                    timestamp: new Date().toISOString()
                };

                await this.keyValueStore.setValue(
                    `login-error-diagnostic-${Date.now()}`,
                    diagnosticInfo
                );

                this.log.error('Login submission failed with diagnostic info', {
                    error: error instanceof Error ? error.message : String(error),
                    diagnosticInfo
                });
            } catch (diagnosticError) {
                this.log.error('Failed to collect diagnostic information', {
                    error: diagnosticError instanceof Error ? diagnosticError.message : String(diagnosticError)
                });
            }

            // 检查是否存在错误消息
            const errorMessage = await this.extractLoginError(page);
            throw new Error(errorMessage || (error instanceof Error ? error.message : 'Unknown error'));
        }
    }

    /**
     * 提取登录错误信息
     */
    private async extractLoginError(page: Page): Promise<string> {
        // 扩展错误选择器列表
        const errorSelectors = [
            '.error-message',
            '.alert-danger',
            '[role="alert"]',
            '#error-message',
            '.login-error',
            '.error',
            '.message-error',
            '#loginError',
            '.form-error',
            // 添加网站特定的选择器
            'form[action="takelogin.php"] .warning',
            'form[action="takelogin.php"] .error',
            '.warning'
        ];

        for (const selector of errorSelectors) {
            try {
                const errorElement = await page.$(selector);
                if (errorElement) {
                    const errorText = await errorElement.textContent();
                    if (errorText?.trim()) {
                        this.log.info('Found error message', {
                            selector,
                            text: errorText.trim()
                        });
                        return errorText.trim();
                    }
                }
            } catch (error) {
                this.log.debug(`Failed to check error selector: ${selector}`, {
                    error: error instanceof Error ? error.message : String(error)
                });
                continue;
            }
        }

        // 如果没有找到具体错误消息，记录页面状态
        try {
            const url = page.url();
            const title = await page.title();
            const bodyText = await page.evaluate(() => document.body.innerText);
            
            this.log.error('No specific error message found, page details:', {
                url,
                title,
                bodyPreview: bodyText.substring(0, 500) // 记录页面前500个字符
            });
        } catch (error) {
            this.log.error('Failed to get page details', {
                error: error instanceof Error ? error.message : String(error)
            });
        }

        return 'Unknown login error';
    }

    /**
     * 验证登录状态
     */
    private async validateLoginState(page: Page, successCheck: LoginConfig['successCheck']): Promise<boolean> {
        try {
            // 等待成功标识出现
            await page.waitForSelector(successCheck.selector, { timeout: 10000 });
            
            // 如果需要验证文本内容
            if (successCheck.expectedText) {
                const text = await page.textContent(successCheck.selector);
                const isValid = text?.includes(successCheck.expectedText);
                
                this.log.info('Login state validation', {
                    selector: successCheck.selector,
                    expectedText: successCheck.expectedText,
                    actualText: text,
                    isValid
                });
                
                return isValid ?? false;
            }

            this.log.info('Login state validated successfully');
            return true;
        } catch (error) {
            this.log.error('Login state validation failed', {
                error: error instanceof Error ? error.message : String(error),
                selector: successCheck.selector
            });
            return false;
        }
    }

    /**
     * 保存登录状态
     */
    private async saveLoginState(page: Page, config: LoginConfig): Promise<void> {
        try {
            // 获取所有状态数据
            const state = {
                cookies: await page.context().cookies(),
                localStorage: await page.evaluate(() => {
                    const data: Record<string, string> = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key) {
                            data[key] = localStorage.getItem(key) || '';
                        }
                    }
                    return data;
                }),
                sessionStorage: await page.evaluate(() => {
                    const data: Record<string, string> = {};
                    for (let i = 0; i < sessionStorage.length; i++) {
                        const key = sessionStorage.key(i);
                        if (key) {
                            data[key] = sessionStorage.getItem(key) || '';
                        }
                    }
                    return data;
                }),
                loginState: {
                    isLoggedIn: true,
                    lastLoginTime: Date.now(),
                    username: config.fields.username.value as string
                }
            };

            // 保存到 KeyValueStore
            const stateKey = `login-state-${Date.now()}`;
            await this.keyValueStore.setValue(stateKey, state);

            // 保存成功页面截图
            const screenshot = await page.screenshot({
                fullPage: true,
                path: `login-success-${Date.now()}.png`
            });
            await this.keyValueStore.setValue(
                `${stateKey}-screenshot`,
                screenshot,
                { contentType: 'image/png' }
            );

            // 保存页面 HTML
            const html = await page.content();
            await this.keyValueStore.setValue(
                `${stateKey}-html`,
                html
            );

            this.log.info('Login state saved successfully', {
                stateKey,
                cookiesCount: state.cookies.length,
                localStorageKeys: Object.keys(state.localStorage).length,
                sessionStorageKeys: Object.keys(state.sessionStorage).length
            });
        } catch (error) {
            this.log.error('Failed to save login state', {
                error: error instanceof Error ? error.message : String(error)
            });
            throw error;
        }
    }

    /**
     * 恢复登录状态
     */
    private async restoreLoginState(page: Page): Promise<boolean> {
        try {
            // 获取最新的登录状态
            const state = await this.keyValueStore.getValue<StorageState>('login-state');
            if (!state) {
                this.log.info('No saved login state found');
                return false;
            }

            // 恢复 cookies
            await page.context().addCookies(state.cookies);

            // 恢复 localStorage
            await page.evaluate((data) => {
                localStorage.clear();
                for (const [key, value] of Object.entries(data)) {
                    localStorage.setItem(key, value);
                }
            }, state.localStorage);

            // 恢复 sessionStorage
            await page.evaluate((data) => {
                sessionStorage.clear();
                for (const [key, value] of Object.entries(data)) {
                    sessionStorage.setItem(key, value);
                }
            }, state.sessionStorage);

            this.log.info('Login state restored', {
                username: state.loginState.username,
                lastLoginTime: new Date(state.loginState.lastLoginTime).toISOString()
            });

            return true;
        } catch (error) {
            this.log.error('Failed to restore login state', {
                error: error instanceof Error ? error.message : String(error)
            });
            return false;
        }
    }

    /**
     * 处理登录错误
     */
    private async handleLoginError(error: Error): Promise<void> {
        const crawlerError: CrawlerError = {
            type: CrawlerErrorType.LOGIN_FAILED,
            message: error.message,
            timestamp: Date.now(),
            stack: error.stack,
        };
        await this.keyValueStore.setValue('loginError', crawlerError);
        throw error;
    }

    /**
     * 执行登录前的准备步骤
     */
    private async executePreLoginStep(page: Page, step: PreLoginStep): Promise<void> {
        try {
            switch (step.type) {
                case 'click':
                    await page.click(step.selector);
                    if (step.waitForSelector) {
                        await page.waitForSelector(step.waitForSelector, {
                            timeout: step.timeout || 5000
                        });
                    }
                    if (step.waitForFunction) {
                        await page.waitForFunction(step.waitForFunction, {
                            timeout: step.timeout || 5000
                        });
                    }
                    break;
                case 'wait':
                    await page.waitForSelector(step.selector, {
                        timeout: step.timeout || 5000
                    });
                    break;
                case 'fill':
                    if (step.value) {
                        await page.fill(step.selector, step.value);
                    }
                    break;
            }
        } catch (error) {
            throw new Error(`Pre-login step failed: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
} 