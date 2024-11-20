import { PlaywrightCrawlingContext } from '@crawlee/playwright';
import { Dataset } from '@crawlee/core';
import { BaseCrawler } from '../base/base-crawler';
import { CrawlerTaskConfig, CrawlResult } from '../../types/crawler';
import { env } from '../../config/env.config';
import { Page } from 'playwright';

export class HDHomeCrawler extends BaseCrawler {
    constructor() {
        // 创建 HDHome 特定的配置
        const taskConfig: CrawlerTaskConfig = {
            taskId: `hdhome-${Date.now()}`,
            startUrls: ['https://hdhome.org'],
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
                    selector: 'td.bottom span.medium',
                    type: 'text',
                    transform: (value: string) => {
                        const match = value.match(/UID:\s*(\d+)/);
                        if (!match) return null;
                        return parseInt(match[1]);
                    }
                },
                {
                    name: 'joinDate',
                    selector: 'td.rowhead:has-text("加入日期") + td.rowfollow',
                    type: 'text',
                    transform: (value: string) => {
                        const match = value.match(/(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})/);
                        if (!match) return null;
                        return new Date(match[1]).toISOString();
                    }
                },
                {
                    name: 'currentIP',
                    selector: 'td.rowhead:has-text("当前IP") + td.rowfollow',
                    type: 'text',
                    transform: (value: string) => value.trim()
                },
                {
                    name: 'uploaded',
                    selector: 'td.rowhead:has-text("传输") + td.rowfollow td.embedded:has-text("上传量")',
                    type: 'text',
                    transform: (value: string) => {
                        const match = value.match(/上传量.*?(\d+\.?\d*)\s*(TB|GB|MB|KB)/);
                        if (!match) return null;
                        const [, size, unit] = match;
                        const num = parseFloat(size);
                        switch (unit) {
                            case 'TB': return num * 1024;
                            case 'GB': return num;
                            case 'MB': return num / 1024;
                            case 'KB': return num / (1024 * 1024);
                            default: return num;
                        }
                    }
                },
                {
                    name: 'downloaded',
                    selector: 'td.rowhead:has-text("传输") + td.rowfollow td.embedded:has-text("下载量")',
                    type: 'text',
                    transform: (value: string) => {
                        const match = value.match(/下载量.*?(\d+\.?\d*)\s*(TB|GB|MB|KB)/);
                        if (!match) return null;
                        const [, size, unit] = match;
                        const num = parseFloat(size);
                        switch (unit) {
                            case 'TB': return num * 1024;
                            case 'GB': return num;
                            case 'MB': return num / 1024;
                            case 'KB': return num / (1024 * 1024);
                            default: return num;
                        }
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
                    name: 'seedBonus',
                    selector: 'td.rowhead:has-text("做种积分") + td.rowfollow',
                    type: 'text',
                    transform: (value: string) => {
                        const match = value.match(/([\d,]+\.?\d*)/);
                        if (!match) return null;
                        return parseFloat(match[1].replace(/,/g, ''));
                    }
                }
            ],
            loginConfig: {
                loginUrl: 'https://hdhome.org/login.php',
                formSelector: 'form[action="takelogin.php"]',
                fields: {
                    username: {
                        name: 'username',
                        type: 'text',
                        selector: 'input[name="username"]',
                        value: env.LOGIN_USERNAME,
                        required: true
                    },
                    password: {
                        name: 'password',
                        type: 'password',
                        selector: 'input[name="password"]',
                        value: env.LOGIN_PASSWORD,
                        required: true
                    },
                    captcha: {
                        type: 'custom',
                        element: {
                            selector: 'img[src*="image.php?action=regimage"]',
                            type: 'img'
                        },
                        input: {
                            name: 'imagestring',
                            type: 'text',
                            selector: 'input[name="imagestring"]',
                            required: true
                        },
                        hash: {
                            selector: 'input[name="imagehash"]',
                            targetField: 'imagehash'
                        },
                        solver: {
                            type: env.CAPTCHA_SKIP_SITES.includes('hdhome') ? 'skip' : env.CAPTCHA_HANDLE_METHOD,
                            config: {
                                apiKey: env.CAPTCHA_API_KEY,
                                apiUrl: env.CAPTCHA_API_URL,
                                timeout: 30000,
                                retries: 3
                            }
                        },
                        // 添加自定义的验证码获取方法
                        getCaptchaImage: async (page: Page): Promise<Buffer | null> => {
                            const imgElement = await page.$('img[src*="image.php?action=regimage"]');
                            if (!imgElement) {
                                throw new Error('Captcha image not found');
                            }

                            // 获取图片的 src 属性
                            const imgSrc = await imgElement.getAttribute('src');
                            if (!imgSrc) {
                                throw new Error('Image src not found');
                            }

                            // 将相对路径转换为完整 URL
                            const captchaUrl = new URL(imgSrc, page.url()).toString();

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
                            selector: 'input[name="two_step_code"]',
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
                    selector: 'a.User_Name',
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
            this.log.info('Starting page processing', { 
                url: request.url,
                isStartUrl: request.url === this.taskConfig.startUrls[0]
            });

            await page.waitForLoadState('networkidle');
            
            if (request.url === this.taskConfig.startUrls[0]) {
                this.log.debug('Processing start URL', { url: request.url });
                
                // 检查页面状态
                const pageTitle = await page.title();
                const pageContent = await page.content();
                this.log.debug('Page info', { 
                    title: pageTitle,
                    contentLength: pageContent.length,
                    url: page.url()
                });

                // 尝试获取用户名链接
                const userProfileElement = await page.$('a.User_Name');
                if (!userProfileElement) {
                    this.log.error('User profile link not found', {
                        selector: 'a.User_Name',
                        url: request.url
                    });
                    throw new Error('User profile link not found');
                }

                const userProfilePath = await userProfileElement.getAttribute('href');
                this.log.info('Found user profile path', { userProfilePath });

                if (userProfilePath) {
                    // 构建完整的用户资料页面URL
                    const userProfileUrl = new URL(userProfilePath, this.taskConfig.startUrls[0]).toString();
                    this.log.info('Constructed full profile URL', { userProfileUrl });

                    await this.crawler.addRequests([userProfileUrl]);
                    await this.saveData({
                        url: request.url,
                        data: { userProfileUrl },
                        timestamp: Date.now(),
                        taskId: this.taskConfig.taskId
                    });
                }
            } else {
                this.log.debug('Processing user profile page', { url: request.url });

                // 等待页面加载完成
                try {
                    await page.waitForSelector('table.main', { timeout: 10000 });
                } catch (error) {
                    this.log.error('Failed to find main table', {
                        error: error instanceof Error ? error.message : String(error),
                        url: request.url
                    });
                    throw error;
                }

                // 记录页面状态
                const pageState = {
                    url: page.url(),
                    title: await page.title(),
                    hasMainTable: await page.$('table.main') !== null,
                    hasUserInfo: await page.$('td.rowhead:has-text("用户ID/UID")') !== null
                };
                this.log.debug('Page state before extraction', pageState);

                // 提取数据前记录所有规则
                this.log.debug('Extraction rules to be applied', {
                    rules: this.taskConfig.extractRules.map(rule => ({
                        name: rule.name,
                        selector: rule.selector
                    }))
                });

                // 先提取基本数据
                const result = await this.extractData(
                    page,
                    this.taskConfig.extractRules.filter(rule => rule.name !== 'userProfileUrl'),
                    request.loadedUrl || request.url
                );

                // 添加 UID 提取验证日志
                this.log.debug('Extracted UID', { 
                    uid: result.data.uid,
                    rawText: await page.$eval('td.bottom span.medium', el => el.textContent)
                });

                // 记录提取结果
                this.log.debug('Data extraction result', {
                    url: request.url,
                    extractedFields: Object.keys(result.data),
                    hasErrors: result.errors && result.errors.length > 0,
                    errors: result.errors
                });

                // 在用户主页，点击显示按钮获取做种统计
                try {
                    await page.click('a[href*="getusertorrentlistajax"][href*="seeding"]');
                    this.log.debug('Clicked seeding stats button');
                    
                    // 等待数据加载
                    await page.waitForSelector('#ka1', { 
                        state: 'visible',
                        timeout: 10000 
                    });
                    this.log.debug('Seeding stats loaded');

                    // 提取做种统计数据
                    const seedingStats = await page.$eval('#ka1', (el) => {
                        const text = el.textContent || '';
                        
                        // 提取做种数量
                        const countMatch = text.match(/^(\d+)条记录/);
                        
                        // 提取总大小
                        const sizeMatch = text.match(/Total:\s*([\d.]+)\s*(TB|GB|MB)/);
                        
                        // 提取官种体积
                        const officialSizeMatch = text.match(/官种体积：([\d.]+)\s*(TB|GB|MB)/);
                        
                        return {
                            count: countMatch ? parseInt(countMatch[1]) : 0,
                            size: sizeMatch ? {
                                value: parseFloat(sizeMatch[1]),
                                unit: sizeMatch[2]
                            } : null,
                            officialSize: officialSizeMatch ? {
                                value: parseFloat(officialSizeMatch[1]),
                                unit: officialSizeMatch[2]
                            } : null
                        };
                    });

                    this.log.debug('Extracted seeding stats', { seedingStats });

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
                            ...result.data,
                            ratio: result.data.uploaded / result.data.downloaded,
                            seedingTotalCount: seedingStats.count,
                            seedingTotalSize: totalSizeGB
                        }
                    };
                    
                    await this.saveData(enrichedData);
                    this.log.info('Data saved successfully', { 
                        url: request.url,
                        dataFields: Object.keys(enrichedData.data)
                    });
                } catch (error) {
                    this.log.error('Failed to get seeding stats', {
                        error: error instanceof Error ? error.message : String(error),
                        url: request.url
                    });
                    // 即使获取做种统计失败，也保存基本数据
                    await this.saveData(result);
                }
            }
        } catch (error) {
            const errorMessage = error instanceof Error 
                ? error.message 
                : 'Unknown error occurred';

            // 保存页面快照
            try {
                const screenshot = await page.screenshot({
                    fullPage: true,
                    path: `error-screenshot-${Date.now()}.png`
                });
                await this.keyValueStore?.setValue(
                    `error-screenshot-${Date.now()}`,
                    screenshot
                );

                const html = await page.content();
                await this.keyValueStore?.setValue(
                    `error-html-${Date.now()}`,
                    html
                );
            } catch (screenshotError) {
                this.log.error('Failed to save error evidence', {
                    error: screenshotError instanceof Error ? screenshotError.message : String(screenshotError)
                });
            }

            this.log.error('Request handling failed', { 
                url: request.url,
                error: errorMessage,
                stack: error instanceof Error ? error.stack : undefined
            });

            throw error instanceof Error ? error : new Error(errorMessage);
        }
    }
} 