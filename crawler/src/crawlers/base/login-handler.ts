import { Page } from 'playwright';
import { LoginConfig, CrawlerError, CrawlerErrorType } from '../../types/crawler';
import { KeyValueStore } from '@crawlee/core';
import { Log } from '@crawlee/core';

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
        const { loginUrl, formSelector, credentials, successCheck } = loginConfig;

        try {
            this.log.info('Starting login process...', { url: loginUrl });
            
            // 检查是否已经登录
            if (await this.isAlreadyLoggedIn(page, successCheck)) {
                this.log.info('Already logged in, skipping login process');
                return;
            }

            // 导航到登录页面
            await page.goto(loginUrl, { waitUntil: 'networkidle' });
            
            // 等待并填写表单
            await this.fillLoginForm(page, formSelector, credentials);
            
            // 处理登录提交
            await this.handleLoginSubmission(page, formSelector, successCheck);
            
            // 保存登录状态
            await this.saveLoginState(page);
            
            this.log.info('Login successful');
            
        } catch (error) {
            this.log.error('Login failed', { error: error.message });
            await this.handleLoginError(error);
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
     * 填写登录表单
     */
    private async fillLoginForm(
        page: Page, 
        formSelector: string, 
        credentials: LoginConfig['credentials']
    ): Promise<void> {
        await page.waitForSelector(formSelector);

        // 清除可能的现有输入
        await page.evaluate((selector) => {
            const form = document.querySelector(selector);
            const inputs = form?.querySelectorAll('input');
            inputs?.forEach(input => {
                if (input.type !== 'submit') input.value = '';
            });
        }, formSelector);

        // 填写凭证
        await page.fill(`${formSelector} input[name="username"]`, credentials.username);
        await page.fill(`${formSelector} input[name="password"]`, credentials.password);
    }

    /**
     * 处理登录提交
     */
    private async handleLoginSubmission(
        page: Page,
        formSelector: string,
        successCheck: LoginConfig['successCheck']
    ): Promise<void> {
        // 提交表单
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle' }),
            page.click(`${formSelector} [type="submit"]`),
        ]);

        // 等待成功标识
        try {
            await page.waitForSelector(successCheck.selector, { timeout: 10000 });
            
            if (successCheck.expectedText) {
                const text = await page.textContent(successCheck.selector);
                if (!text?.includes(successCheck.expectedText)) {
                    throw new Error('Login success check failed: text mismatch');
                }
            }
        } catch (error) {
            // 检查是否存在错误消息
            const errorMessage = await this.extractLoginError(page);
            throw new Error(errorMessage || error.message);
        }
    }

    /**
     * 提取登录错误信息
     */
    private async extractLoginError(page: Page): Promise<string> {
        // 常见的错误消息选择器
        const errorSelectors = [
            '.error-message',
            '.alert-danger',
            '[role="alert"]',
            '#error-message',
            '.login-error'
        ];

        for (const selector of errorSelectors) {
            try {
                const errorElement = await page.$(selector);
                if (errorElement) {
                    const errorText = await errorElement.textContent();
                    if (errorText?.trim()) {
                        return errorText.trim();
                    }
                }
            } catch {
                continue;
            }
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