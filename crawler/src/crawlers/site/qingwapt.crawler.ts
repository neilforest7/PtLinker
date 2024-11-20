import { PlaywrightCrawlingContext } from '@crawlee/playwright';
import { Dataset } from '@crawlee/core';
import { BaseCrawler } from '../base/base-crawler';
import { CrawlerTaskConfig, CrawlResult } from '../../types/crawler';
import { env } from '../../config/env.config';
import { Page } from 'playwright';

export class QingWaptCrawler extends BaseCrawler {
    constructor() {
        // 创建 QingWapt 特定的配置
        const taskConfig: CrawlerTaskConfig = {
            taskId: `qingwapt-${Date.now()}`,
            startUrls: ['https://www.qingwapt.com'],
            extractRules: [
                {
                    name: 'userProfileUrl',
                    selector: 'a.User_Name',
                    type: 'attribute',
                    attribute: 'href',
                    required: true
                },
                {
                    name: 'uid',
                    selector: 'td.rowhead:has-text("用户ID/UID") + td.rowfollow',
                    type: 'text',
                    transform: (value: string) => {
                        const match = value.match(/(\d+)/);
                        if (!match) return null;
                        return parseInt(match[1]);
                    }
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
                },
                {
                    name: 'bonus',
                    selector: 'td.rowhead:has-text("做种积分") + td.rowfollow',
                    type: 'text',
                    transform: (value: string) => {
                        const match = value.match(/([\d,]+\.?\d*)/);
                        if (!match) return null;
                        return parseFloat(match[1].replace(/,/g, ''));
                    }
                },
                {
                    name: 'joinDate',
                    selector: 'td.rowhead:has-text("加入日期") + td.rowfollow',
                    type: 'text',
                    transform: (value: string) => {
                        // 匹配日期格式 YYYY-MM-DD HH:mm:ss
                        const match = value.match(/(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})/);
                        if (!match) return null;

                        try {
                            // 解析日期字符串
                            const date = new Date(match[1]);
                            
                            // 返回 ISO 格式的时间戳
                            return date.toISOString();
                        } catch (error) {
                            return null;
                        }
                    }
                },
                {
                    name: 'ip',
                    selector: 'td.rowhead:has-text("当前IP") + td.rowfollow',
                    type: 'text',
                    transform: (value: string) => {
                        // 直接返回清理后的文本
                        return value.trim();
                    }
                }
            ],
            loginConfig: {
                loginUrl: 'https://www.qingwapt.com/login.php',
                preLoginSteps: [
                    {
                        type: 'click',
                        selector: 'button#login.qw-button',
                        waitForFunction: '() => { const captcha = document.querySelector(\'div[id="captcha"]\'); return captcha && window.getComputedStyle(captcha).opacity === \'1\'; }',
                        timeout: 5000
                    }
                ],
                formSelector: 'form[id="form-login"]',
                fields: {
                    username: {
                        name: 'username',
                        type: 'text',
                        selector: 'input.textbox[name="username"][type="text"]',
                        value: env.LOGIN_USERNAME,
                        required: true
                    },
                    password: {
                        name: 'password',
                        type: 'password',
                        selector: 'input.textbox[name="password"][type="password"]',
                        value: env.LOGIN_PASSWORD,
                        required: true
                    },
                    captcha: {
                        type: 'custom',
                        element: {
                            selector: 'div#captcha',
                            type: 'div',
                            attribute: 'background-image'
                        },
                        input: {
                            name: 'imagestring',
                            type: 'text',
                            selector: 'input#captcha-text.textbox',
                            required: true
                        },
                        hash: {
                            selector: 'input#imagehash[name="imagehash"]',
                            targetField: 'imagehash'
                        },
                        solver: {
                            type: env.CAPTCHA_SKIP_SITES.includes('qingwapt') ? 'skip' : env.CAPTCHA_HANDLE_METHOD,
                            config: {
                                apiKey: env.CAPTCHA_API_KEY,
                                apiUrl: env.CAPTCHA_API_URL,
                                timeout: 30000,
                                retries: 3
                            }
                        },
                        getCaptchaImage: async (page: Page): Promise<Buffer | null> => {
                            await page.waitForTimeout(1000);
                            const imgElement = await page.$('div[id="captcha"]');
                            if (!imgElement) {
                                throw new Error('Captcha element not found');
                            }

                            // 获取背景图片 URL
                            const style = await imgElement.getAttribute('style');
                            if (!style) {
                                throw new Error('No style attribute found');
                            }

                            const urlMatch = style.match(/background-image:\s*url\("([^"]+)"\)/);
                            if (!urlMatch) {
                                throw new Error('Invalid background image format');
                            }

                            // 将相对路径转换为完整 URL
                            const captchaUrl = new URL(urlMatch[1], page.url()).toString();
                            try {
                                // 使用 request 获取图片
                                const response = await page.context().request.get(captchaUrl);
                                const buffer = Buffer.from(await response.body());
                                // 记录验证码获取日志
                                this.log.debug('Captcha image downloaded', {
                                    url: captchaUrl,
                                    size: buffer.length,
                                    contentType: response.headers()['content-type']
                                });
                                return buffer;                                
                            } catch (error) {
                                this.log.error('Failed to download captcha image', {
                                    url: captchaUrl,
                                    error: error instanceof Error ? error.message : String(error)
                                });
                                throw error;
                            }

                        }
                    },
                    other: [
                        {
                            name: 'secret',
                            type: 'hidden',
                            selector: 'input[name="secret"]',
                            value: ''
                        },
                        {
                            name: 'two_step_code',
                            type: 'text',
                            selector: 'input.textbox[name="two_step_code"]',
                            value: ''
                        },
                        {
                            name: 'logout',
                            type: 'checkbox',
                            selector: 'input[name="logout"]',
                            value: false
                        },
                        {
                            name: 'securelogin',
                            type: 'checkbox',
                            selector: 'input[name="securelogin"]',
                            value: false
                        }
                    ]
                },
                successCheck: {
                    selector: '#info_block a.User_Name',
                    expectedText: env.LOGIN_USERNAME
                }
            }
        };

        super(taskConfig);
    }

    // 实现从 BaseCrawler 继承的方法
    public async getProgress(): Promise<any> {
        try {
            const dataset = await Dataset.open(this.taskConfig.taskId);
            const info = await dataset.getInfo();
            
            return {
                itemCount: info?.itemCount ?? 0,  // 使用可选链和空值合并
                timestamp: Date.now(),
                datasetId: info?.id ?? this.taskConfig.taskId
            };
        } catch (error) {
            this.log.error('Failed to get progress', {
                error: error instanceof Error ? error.message : String(error)
            });
            return {
                itemCount: 0,
                timestamp: Date.now(),
                error: error instanceof Error ? error.message : 'Unknown error'
            };
        }
    }

    public async getCrawledData(): Promise<{ items: any[] }> {
        const dataset = await Dataset.open(this.taskConfig.taskId);
        const { items } = await dataset.getData();
        return { items };
    }

    protected async saveData(data: CrawlResult): Promise<void> {
        await this.dataHandler.saveData(data);
    }

    protected async extractData(page: any, rules: any[], url: string): Promise<CrawlResult> {
        return this.dataHandler.extractData(page, rules, url);
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
                // 先提取基本数据
                const result = await this.extractData(
                    page,
                    this.taskConfig.extractRules.filter(rule => rule.name !== 'userProfileUrl'),
                    request.loadedUrl || request.url
                );

                // 在用户主页，点击显示按钮获取做种统计
                await page.click('a[href*="getusertorrentlistajax"][href*="seeding"]');
                
                // 等待数据加载
                await page.waitForSelector('#ka1[data-type="seeding"]', { 
                    state: 'visible',
                    timeout: 10000 
                });

                // 提取做种统计数据
                const seedingStats = await page.$eval('#ka1[data-type="seeding"]', (el) => {
                    const text = el.textContent || '';
                    const countMatch = text.match(/(\d+)\s*条记录/);
                    const sizeMatch = text.match(/总大小：([\d.]+)\s*(TB|GB|MB)/);
                    
                    return {
                        count: countMatch ? parseInt(countMatch[1]) : 0,
                        size: sizeMatch ? {
                            value: parseFloat(sizeMatch[1]),
                            unit: sizeMatch[2]
                        } : null
                    };
                });

                // 转换大小为 GB
                let totalSizeGB = 0;
                if (seedingStats.size) {
                    switch (seedingStats.size.unit) {
                        case 'TB':
                            totalSizeGB = seedingStats.size.value * 1024;
                            break;
                        case 'GB':
                            totalSizeGB = seedingStats.size.value;
                            break;
                        case 'MB':
                            totalSizeGB = seedingStats.size.value / 1024;
                            break;
                    }
                }

                // 合并所有数据
                const enrichedData = {
                    ...result,
                    data: {
                        ...result.data,  // 包含了 uid 和其他基本数据
                        seedingTotalCount: seedingStats.count,
                        seedingTotalSize: totalSizeGB
                    }
                };
                
                await this.saveData(enrichedData);
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