import { PlaywrightCrawler } from '@crawlee/playwright';
import { Dataset, KeyValueStore, Log } from '@crawlee/core';
import { LoginHandler } from './login-handler';
import { DataHandler } from './data-handler';
import { CrawlerTaskConfig, CrawlResult } from '../../types/crawler';
import { DEFAULT_CRAWLER_CONFIG } from '../../config/crawler.config';
import { StorageManager } from '../../services/storage/storage-manager';
import { resolve } from 'path';
import { STORAGE_CONFIG } from '../../config/crawler.config';

export abstract class BaseCrawler {
    protected readonly crawler: PlaywrightCrawler;
    protected readonly taskConfig: CrawlerTaskConfig;
    protected dataset!: Dataset;
    protected keyValueStore!: KeyValueStore;
    protected readonly log: Log;
    protected loginHandler!: LoginHandler;
    protected dataHandler!: DataHandler;
    protected storageManager!: StorageManager;

    constructor(taskConfig: CrawlerTaskConfig) {
        this.taskConfig = taskConfig;
        this.log = new Log({ prefix: `Crawler:${taskConfig.taskId}` });

        // 设置存储路径
        const siteId = this.getSiteId();
        const storageBasePath = resolve(STORAGE_CONFIG.storageDir, siteId);

        // 设置环境变量以配置存储路径
        process.env.CRAWLEE_STORAGE_DIR = storageBasePath;

        // 初始化爬虫
        this.crawler = new PlaywrightCrawler({
            ...DEFAULT_CRAWLER_CONFIG,
            // 添加预导航钩子
            preNavigationHooks: [
                async ({ page, request }) => {
                    // 检查并恢复浏览器状态
                    if (this.storageManager) {
                        const state = await this.storageManager.getLatestBrowserState();
                        if (state?.cookies) {
                            await page.context().addCookies(state.cookies);
                        }
                    }
                }
            ],
            requestHandler: this.handleRequest.bind(this)
        });

        // 初始化存储
        Promise.all([
            Dataset.open(this.taskConfig.taskId),
            KeyValueStore.open(this.taskConfig.taskId)
        ]).then(([dataset, store]) => {
            this.dataset = dataset;
            this.keyValueStore = store;
            
            this.storageManager = new StorageManager(
                dataset,
                store,
                {
                    siteId,
                    taskId: taskConfig.taskId,
                    baseDir: storageBasePath
                }
            );

            // 初始化登录处理器，注入存储管理器
            this.loginHandler = new LoginHandler(store, this.log);

            // 初始化数据处理器
            this.dataHandler = new DataHandler(dataset, store, this.log, taskConfig.taskId);
        });
    }

    // 获取站点ID的辅助方法
    private getSiteId(): string {
        const url = this.taskConfig.startUrls[0];
        try {
            const hostname = new URL(url).hostname;
            return hostname.split('.')[0];  // 例如从 hdfans.org 获取 hdfans
        } catch {
            return 'unknown-site';
        }
    }

    // 抽象方法，由子类实现
    protected abstract handleRequest(context: any): Promise<void>;

    // 启动爬虫
    public async start(): Promise<void> {
        try {
            // 检查登录状态
            const state = await this.storageManager?.getLatestBrowserState();
            const needLogin = !state?.loginState?.isLoggedIn;

            if (needLogin && this.taskConfig.loginConfig) {
                // 使用 browserPool 获取页面
                const browserController = this.crawler.browserPool;
                if (!browserController) {
                    throw new Error('Browser pool not initialized');
                }

                const page = await browserController.newPage();
                if (!page) {
                    throw new Error('Failed to get browser instance');
                }

                // 先尝试使用已保存的 cookies
                const cookiesValid = await this.storageManager?.validateCookies(page);
                
                if (!cookiesValid) {
                    // cookies 无效，执行登录流程
                    this.log.info('Cookies invalid or expired, performing login...');
                    await this.loginHandler.performLogin(page, this.taskConfig.loginConfig);

                    // 登录成功后保存新的 cookies
                    const cookies = await page.context().cookies();
                    await this.storageManager?.saveCookies(cookies);
                } else {
                    this.log.info('Using saved cookies, skipping login');
                }

                // 保存登录状态
                await this.storageManager?.saveBrowserState({
                    cookies: await page.context().cookies(),
                    localStorage: await page.evaluate(() => ({ ...localStorage })),
                    sessionStorage: await page.evaluate(() => ({ ...sessionStorage })),
                    loginState: {
                        isLoggedIn: true,
                        lastLoginTime: Date.now(),
                        username: this.taskConfig.loginConfig.credentials.username
                    }
                });

                await page.close();
            }

            // 开始爬取
            await this.crawler.run(this.taskConfig.startUrls);

        } catch (error) {
            await this.storageManager?.saveError({
                type: 'CRAWLER_ERROR',
                message: error instanceof Error ? error.message : String(error),
                timestamp: Date.now(),
                stack: error instanceof Error ? error.stack : undefined
            });
            throw error;
        }
    }
} 