import { PlaywrightCrawlingContext } from '@crawlee/playwright';
import { BaseCrawler } from '../base/base-crawler';
import { CrawlerTaskConfig } from '../../types/crawler';
import { env } from '../../config/env.config';

export class HDFansCrawler extends BaseCrawler {
    constructor() {
        // 创建 HDFans 特定的配置
        const taskConfig: CrawlerTaskConfig = {
            taskId: `hdfans-${Date.now()}`,
            startUrls: ['https://hdfans.org'],
            extractRules: [
                {
                    name: 'userProfileUrl',
                    selector: 'a.User_Name',
                    type: 'attribute',
                    attribute: 'href',
                    required: true
                },
                {
                    name: 'ratio',
                    selector: 'td.rowfollow',
                    type: 'text',
                    transform: (value: string) => {
                        const match = value.match(/分享率.*?(\d+\.?\d*)/);
                        if (!match) return null;
                        return parseFloat(match[1]);
                    }
                },
                {
                    name: 'uploaded',
                    selector: 'td.rowfollow',
                    type: 'text',
                    transform: (value: string) => {
                        const match = value.match(/上传量.*?(\d+\.?\d*)\s*(TB|GB|MB)/);
                        if (!match) return null;
                        const [, size, unit] = match;
                        const num = parseFloat(size);
                        switch (unit) {
                            case 'TB': return num * 1024;
                            case 'GB': return num;
                            case 'MB': return num / 1024;
                            default: return num;
                        }
                    }
                },
                {
                    name: 'downloaded',
                    selector: 'td.rowfollow',
                    type: 'text',
                    transform: (value: string) => {
                        const match = value.match(/下载量.*?(\d+\.?\d*)\s*(TB|GB|MB)/);
                        if (!match) return null;
                        const [, size, unit] = match;
                        const num = parseFloat(size);
                        switch (unit) {
                            case 'TB': return num * 1024;
                            case 'GB': return num;
                            case 'MB': return num / 1024;
                            default: return num;
                        }
                    }
                },
                {
                    name: 'seeding',
                    selector: 'td.rowfollow',
                    type: 'text',
                    transform: (value: string) => {
                        const match = value.match(/当前做种.*?(\d+)/);
                        if (!match) return null;
                        return parseInt(match[1]);
                    }
                },
                {
                    name: 'leeching',
                    selector: 'td.rowfollow',
                    type: 'text',
                    transform: (value: string) => {
                        const match = value.match(/当前下载.*?(\d+)/);
                        if (!match) return null;
                        return parseInt(match[1]);
                    }
                },
                {
                    name: 'bonus',
                    selector: 'td.rowhead:has-text("魔力值") + td.rowfollow',
                    type: 'text',
                    transform: (value: string) => {
                        const match = value.match(/([\d,]+\.?\d*)/);
                        if (!match) return null;
                        return parseFloat(match[1].replace(/,/g, ''));
                    }
                }
            ],
            loginConfig: {
                loginUrl: 'https://hdfans.org/login.php',
                formSelector: 'form[action="takelogin.php"]',
                credentials: {
                    username: env.LOGIN_USERNAME,
                    password: env.LOGIN_PASSWORD
                },
                successCheck: {
                    selector: 'a.User_Name',
                    expectedText: env.LOGIN_USERNAME
                },
                captcha: {
                    imageSelector: 'img[src*="image.php?action=regimage"]',
                    inputSelector: 'input[name="imagestring"]',
                    handleMethod: env.CAPTCHA_HANDLE_METHOD,
                    serviceConfig: {
                        apiKey: env.CAPTCHA_API_KEY,
                        apiUrl: env.CAPTCHA_API_URL
                    }
                }
            }
        };

        super(taskConfig);
    }

    protected async handleRequest(context: PlaywrightCrawlingContext): Promise<void> {
        const { page, request } = context;
        
        try {
            await page.waitForLoadState('networkidle');
            
            if (request.url === this.taskConfig.startUrls[0]) {
                const userProfileUrl = await page.$eval('a.User_Name', el => el.getAttribute('href'));
                if (userProfileUrl) {
                    await this.crawler.addRequests([userProfileUrl]);
                    await this.saveData({
                        url: request.url,
                        data: { userProfileUrl },
                        timestamp: Date.now(),
                        taskId: this.taskConfig.taskId
                    });
                }
            } else {
                const result = await this.extractData(
                    page,
                    this.taskConfig.extractRules.filter(rule => rule.name !== 'userProfileUrl'),
                    request.loadedUrl || request.url
                );
                
                await this.saveData(result);
            }
            
            this.log.info('Data extracted successfully', { 
                url: request.url,
                isProfilePage: request.url !== this.taskConfig.startUrls[0]
            });
            
        } catch (error) {
            const errorMessage = error instanceof Error 
                ? error.message 
                : 'Unknown error occurred';

            this.log.error('Data extraction failed', { 
                url: request.url,
                error: errorMessage
            });

            throw error instanceof Error ? error : new Error(errorMessage);
        }
    }
} 