import { Page } from 'playwright';
import { LoginConfig, CrawlerError, CrawlerErrorType } from '../../types/crawler';
import { KeyValueStore } from '@crawlee/core';
import { Log } from '@crawlee/core';
import { CaptchaServiceFactory } from '../../services/captcha/factory';

export class LoginHandler {
    private readonly keyValueStore: KeyValueStore;
    private readonly log: Log;

    constructor(keyValueStore: KeyValueStore, log: Log) {
        this.keyValueStore = keyValueStore;
        this.log = log;
    }

    /**
     * 执行登录流程
     */
    public async performLogin(page: Page, loginConfig: LoginConfig): Promise<void> {
        try {
            // 添加页面错误监听
            page.on('pageerror', error => {
                this.log.error('Page error', { error: error.message });
            });

            // 添加请求失败监听
            page.on('requestfailed', request => {
                this.log.error('Request failed', { 
                    url: request.url(),
                    error: request.failure()?.errorText 
                });
            });

            // 添加响应监听
            page.on('response', response => {
                const status = response.status();
                if (status >= 300 && status < 400) {
                    // 3xx 状态码表示重定向，这是正常的
                    this.log.info('Response redirect', {
                        url: response.url(),
                        status,
                        statusText: response.statusText(),
                        location: response.headers()['location']
                    });
                } else if (!response.ok()) {
                    // 其他非成功状态码才报告错误
                    this.log.error('Response error', {
                        url: response.url(),
                        status,
                        statusText: response.statusText()
                    });
                }
            });

            this.log.info('Starting login process...', { url: loginConfig.loginUrl });
            
            // 导航到登录页面
            await page.goto(loginConfig.loginUrl, { 
                waitUntil: 'networkidle',
                timeout: 30000 
            });

            // 保存登录页面截图
            try {
                const loginPageScreenshot = await page.screenshot({
                    fullPage: true,
                    path: `login-page-${Date.now()}.png`
                });
                await this.keyValueStore.setValue(
                    `login-page-screenshot-${Date.now()}`,
                    loginPageScreenshot
                );
                this.log.info('Login page screenshot saved');
            } catch (screenshotError) {
                this.log.error('Failed to save login page screenshot', {
                    error: screenshotError instanceof Error ? screenshotError.message : String(screenshotError)
                });
            }
            
            // 等待并填写表单
            await this.fillLoginForm(page, loginConfig.formSelector, loginConfig.credentials, loginConfig.captcha);
            
            // 处理登录提交
            await this.handleLoginSubmission(page, loginConfig.formSelector, loginConfig.successCheck);
            
            // 保存登录状态
            await this.saveLoginState(page);
            
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
     * 处理验证码
     */
    private async handleCaptcha(
        page: Page,
        captchaImg: any,
        captchaInput: any,
        captchaConfig?: LoginConfig['captcha']
    ): Promise<void> {
        this.log.info('Captcha detected, handling...');
        
        try {
            // 获取验证码图片的 src 属性
            const imgSrc = await captchaImg.getAttribute('src');
            this.log.info('Captcha image src:', { src: imgSrc });

            // 从 URL 中提取 imagehash 参数
            const imageHashMatch = imgSrc.match(/imagehash=([^&]+)/);
            const imageHash = imageHashMatch ? imageHashMatch[1] : '';
            this.log.info('Extracted imagehash:', { imageHash });

            // 使用 JavaScript 直接设置 imagehash 值
            await page.evaluate((hash) => {
                const imageHashInput = document.querySelector('input[name="imagehash"]');
                if (imageHashInput) {
                    (imageHashInput as HTMLInputElement).value = hash;
                }
            }, imageHash);
            this.log.info('Set imagehash value via JavaScript');

            // 保存验证码图片前的页面状态
            const beforeCaptchaScreenshot = await page.screenshot({
                fullPage: true,
                path: `before-captcha-${Date.now()}.png`
            });
            await this.keyValueStore.setValue(
                `before-captcha-screenshot-${Date.now()}`,
                beforeCaptchaScreenshot
            );
            this.log.info('Before-captcha screenshot saved');

            const buffer = await captchaImg.screenshot({
                type: 'png'
            });
            const captchaBase64 = buffer.toString('base64');

            // 保存验证码图片
            await this.keyValueStore.setValue(
                `captcha-image-${Date.now()}`,
                buffer
            );
            this.log.info('Captcha image saved');

            let captchaCode: string;

            if (captchaConfig?.handleMethod !== 'manual') {
                try {
                    const captchaService = CaptchaServiceFactory.createService(
                        captchaConfig?.handleMethod || 'manual',
                        {
                            apiKey: captchaConfig?.serviceConfig?.apiKey || '',
                            apiUrl: captchaConfig?.serviceConfig?.apiUrl
                        }
                    );

                    this.log.info(`Using ${captchaConfig?.handleMethod} service to solve captcha...`);
                    const result = await captchaService.solveCaptcha(captchaBase64);
                    
                    if (!result.success || !result.code) {
                        throw new Error(`Failed to solve captcha: ${result.error}`);
                    }

                    captchaCode = result.code;
                    this.log.info('Captcha solved successfully', { code: captchaCode });

                } catch (error) {
                    this.log.error('Captcha service failed, falling back to manual input', {
                        error: error instanceof Error ? error.message : String(error)
                    });
                    captchaCode = await this.waitForCaptchaInput(captchaBase64);
                }
            } else {
                captchaCode = await this.waitForCaptchaInput(captchaBase64);
            }

            // 填写验证码前保存页面状态
            const beforeFillCaptchaScreenshot = await page.screenshot({
                fullPage: true,
                path: `before-fill-captcha-${Date.now()}.png`
            });
            await this.keyValueStore.setValue(
                `before-fill-captcha-screenshot-${Date.now()}`,
                beforeFillCaptchaScreenshot
            );
            this.log.info('Before filling captcha screenshot saved');

            // 填写验证码
            await captchaInput.fill(captchaCode);
            this.log.info('Captcha filled', { code: captchaCode, imageHash });

            // 保存填写验证码后的页面截图
            const afterCaptchaScreenshot = await page.screenshot({
                fullPage: true,
                path: `after-captcha-${Date.now()}.png`
            });
            await this.keyValueStore.setValue(
                `after-captcha-screenshot-${Date.now()}`,
                afterCaptchaScreenshot
            );
            this.log.info('After-captcha screenshot saved');

        } catch (error) {
            this.log.error('Error in captcha handling', {
                error: error instanceof Error ? error.message : String(error)
            });
            throw error;
        }
    }

    /**
     * 填写登录表单
     */
    private async fillLoginForm(
        page: Page, 
        formSelector: string, 
        credentials: LoginConfig['credentials'],
        captchaConfig?: LoginConfig['captcha']
    ): Promise<void> {
        this.log.info('Waiting for form...', { selector: formSelector });
        await page.waitForSelector(formSelector, { timeout: 10000 });
        this.log.info('Form found');

        // 验证输入字段是否存在
        const usernameInput = await page.$(`${formSelector} input[name="username"]`);
        const passwordInput = await page.$(`${formSelector} input[name="password"]`);
        const submitButton = await page.$(`${formSelector} [type="submit"]`);
        const imageHashInput = await page.$(`${formSelector} input[name="imagehash"]`);
        const captchaInput = await page.$(`${formSelector} input[name="imagestring"]`);
        
        if (!usernameInput || !passwordInput || !submitButton || !imageHashInput || !captchaInput) {
            throw new Error('Login form elements not found');
        }

        // 清除可能的现有输入
        await page.evaluate((selector) => {
            const form = document.querySelector(selector);
            const inputs = form?.querySelectorAll('input');
            inputs?.forEach(input => {
                if (input.type !== 'submit') input.value = '';
            });
        }, formSelector);

        // 填写凭证
        this.log.info('Filling credentials...', { username: credentials.username });
        await usernameInput.fill(credentials.username);
        await passwordInput.fill(credentials.password);

        // 保存填写凭证后的截图
        const afterCredentialsScreenshot = await page.screenshot({
            fullPage: true,
            path: `after-credentials-${Date.now()}.png`
        });
        await this.keyValueStore.setValue(
            `after-credentials-screenshot-${Date.now()}`,
            afterCredentialsScreenshot
        );
        this.log.info('Credentials filled and screenshot saved');

        // 检查并处理验证码
        if (captchaConfig?.imageSelector && captchaConfig?.inputSelector) {
            // 添加更多日志来帮助调试
            this.log.info('Looking for captcha elements...');
            
            // 获取页面上所有的图片元素
            const allImages = await page.$$('img');
            this.log.info(`Found ${allImages.length} images on page`);
            
            // 获取所有图片的信息
            const imageInfo = await Promise.all(allImages.map(async img => {
                const src = await img.getAttribute('src');
                const id = await img.getAttribute('id');
                const className = await img.getAttribute('class');
                return { src, id, className };
            }));
            this.log.info('Image elements found:', { images: imageInfo });

            // 获取所有输入框
            const allInputs = await page.$$('input');
            this.log.info(`Found ${allInputs.length} input elements`);
            
            // 获取所有输入框的信息
            const inputInfo = await Promise.all(allInputs.map(async input => {
                const name = await input.getAttribute('name');
                const type = await input.getAttribute('type');
                const id = await input.getAttribute('id');
                return { name, type, id };
            }));
            this.log.info('Input elements found:', { inputs: inputInfo });

            // 尝试使用多个可能的选择器
            const possibleImageSelectors = [
                'img[alt=\"CAPTCHA\"]',
                'img[src*=\"image.php?action=regimage\"]',
                'img[src*=\"vcode\"]',
                'img[src*=\"captcha\"]',
                'img.captcha',
                '#captcha_img'
            ];

            const possibleInputSelectors = [
                'input[name=\"imagestring\"]',
                'input[name=\"vcode\"]',
                'input[name=\"captcha\"]',
                'input[name=\"verify\"]',
                '#captcha_input',
                '.captcha-input'
            ];

            // 记录当前页面的 HTML 结构
            const pageHtml = await page.content();
            await this.keyValueStore.setValue(
                `page-html-${Date.now()}`,
                pageHtml
            );

            // 尝试所有可能的选择器
            for (const imgSelector of possibleImageSelectors) {
                const img = await page.$(imgSelector);
                if (img) {
                    this.log.info(`Found captcha image with selector: ${imgSelector}`);
                    for (const inputSelector of possibleInputSelectors) {
                        const input = await page.$(inputSelector);
                        if (input) {
                            this.log.info(`Found captcha input with selector: ${inputSelector}`);
                            await this.handleCaptcha(page, img, input, {
                                ...captchaConfig,
                                imageSelector: imgSelector,
                                inputSelector: inputSelector
                            });
                            return;
                        }
                    }
                }
            }

            this.log.error('Could not find captcha elements with any known selectors', {
                imageSelectors: possibleImageSelectors,
                inputSelectors: possibleInputSelectors
            });
        }

        this.log.info('Form filled completely');

        // 保存表单填写完成后的截图
        const formFilledScreenshot = await page.screenshot({
            fullPage: true,
            path: `form-filled-${Date.now()}.png`
        });
        await this.keyValueStore.setValue(
            `form-filled-screenshot-${Date.now()}`,
            formFilledScreenshot
        );
        this.log.info('Final form state screenshot saved');
    }

    // 等待验证码输入
    private async waitForCaptchaInput(captchaBase64: string): Promise<string> {
        // 这里实现等待用户输入的逻辑
        // 示例使用 readline
        const readline = require('readline').createInterface({
            input: process.stdin,
            output: process.stdout
        });

        return new Promise((resolve) => {
            readline.question('请输入验证码: ', (answer: string) => {
                readline.close();
                resolve(answer.trim());
            });
        });
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
     * 保存登录状态
     */
    private async saveLoginState(page: Page): Promise<void> {
        // 保存cookies
        const cookies = await page.context().cookies();
        await this.keyValueStore.setValue('cookies', cookies);

        // 保存localStorage
        const localStorage = await page.evaluate(() => {
            const items: Record<string, string> = {};
            for (let i = 0; i < window.localStorage.length; i++) {
                const key = window.localStorage.key(i);
                if (key) {
                    items[key] = window.localStorage.getItem(key) || '';
                }
            }
            return items;
        });
        await this.keyValueStore.setValue('localStorage', localStorage);

        // 保存sessionStorage
        const sessionStorage = await page.evaluate(() => {
            const items: Record<string, string> = {};
            for (let i = 0; i < window.sessionStorage.length; i++) {
                const key = window.sessionStorage.key(i);
                if (key) {
                    items[key] = window.sessionStorage.getItem(key) || '';
                }
            }
            return items;
        });
        await this.keyValueStore.setValue('sessionStorage', sessionStorage);
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
} 