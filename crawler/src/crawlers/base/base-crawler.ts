import { PlaywrightCrawler, Dataset, KeyValueStore, Log } from '@crawlee/playwright';
import { PlaywrightCrawlingContext } from '@crawlee/playwright';
import { Page } from 'playwright';
import { 
    CrawlerTaskConfig, 
    LoginConfig,
    CrawlResult,
    CrawlerError,
    CrawlerErrorType,
    ExtractRule 
} from '../../types/crawler';
import { TaskStatus, TaskProgress } from '../../types/utils';
import { DEFAULT_CRAWLER_CONFIG, BROWSER_CONFIG } from '../../config/crawler.config';
import { LoginHandler } from './login-handler';
import { DataHandler } from './data-handler';
import { BrowserPool } from 'crawlee';

export abstract class BaseCrawler {
    protected crawler!: PlaywrightCrawler;
    protected dataset!: Dataset;
    protected keyValueStore!: KeyValueStore;
    protected taskConfig: CrawlerTaskConfig;
    protected progress: TaskProgress;
    protected log: Log;
    protected loginHandler!: LoginHandler;
    protected dataHandler!: DataHandler;
    protected browserPool!: BrowserPool;

    constructor(taskConfig: CrawlerTaskConfig) {
        this.taskConfig = taskConfig;
        this.log = new Log({ prefix: `Crawler:${taskConfig.taskId}` });
        
        // 初始化进度
        this.progress = {
            taskId: taskConfig.taskId,
            status: TaskStatus.PENDING,
            progress: 0,
            timestamp: Date.now()
        };

        // 立即初始化
        this.initializeAsync().catch(error => {
            this.log.error('Initialization failed', { 
                error: error instanceof Error ? error.message : String(error) 
            });
        });
    }

    /**
     * 异步初始化
     */
    private async initializeAsync(): Promise<void> {
        // 初始化存储
        this.dataset = await Dataset.open(`task-${this.taskConfig.taskId}`);
        this.keyValueStore = await KeyValueStore.open(`state-${this.taskConfig.taskId}`);
        
        // 初始化处理器
        this.loginHandler = new LoginHandler(this.keyValueStore, this.log);
        this.dataHandler = new DataHandler(
            this.dataset,
            this.keyValueStore,
            this.log,
            this.taskConfig.taskId
        );

        // 创建爬虫实例
        this.crawler = new PlaywrightCrawler({
            ...DEFAULT_CRAWLER_CONFIG,
            browserPoolOptions: {
                useFingerprints: true,
            },
            preNavigationHooks: [
                async (crawlingContext) => {
                    await this.preNavigationHook(
                        crawlingContext.page,
                        crawlingContext.request
                    );
                },
            ],
            postNavigationHooks: [
                async (crawlingContext) => {
                    await this.postNavigationHook(
                        crawlingContext.page,
                        crawlingContext.request
                    );
                },
            ],
            requestHandler: this.handleRequest.bind(this),
            failedRequestHandler: async ({ request, error: crawlerError }) => {
                // 确保错误是 Error 类型
                const error = crawlerError instanceof Error 
                    ? crawlerError 
                    : new Error(String(crawlerError));
                await this.handleFailedRequest(request, error);
            },
        });
    }

    /**
     * 开始爬取
     */
    public async start(): Promise<void> {
        try {
            await this.initializeAsync();
            
            // 如果需要登录,先进行登录
            if (this.taskConfig.loginConfig) {
                await this.login(this.taskConfig.loginConfig);
            }

            this.progress.status = TaskStatus.RUNNING;
            await this.keyValueStore.setValue('progress', this.progress);

            // 添加起始URL到队列
            await this.crawler.addRequests(this.taskConfig.startUrls);
            
            // 运行爬虫
            await this.crawler.run();

            this.progress.status = TaskStatus.COMPLETED;
            this.progress.progress = 100;
            
        } catch (error) {
            this.progress.status = TaskStatus.FAILED;
            if (error instanceof Error) {
                this.progress.error = error.message;
            } else {
                this.progress.error = String(error);
            }
            throw error;
        } finally {
            await this.keyValueStore.setValue('progress', this.progress);
        }
    }

    /**
     * 登录处理
     */
    protected async login(loginConfig: LoginConfig): Promise<void> {
        try {
            // 使用 browserPool 获取页面
            const browserController = this.crawler.browserPool;
            if (!browserController) {
                throw new Error('Browser pool not initialized');
            }

            // 创建一个新的浏览器实例
            const browser = await browserController.newPage();
            if (!browser) {
                throw new Error('Failed to get browser instance');
            }
            
            try {
                // 使用登录处理器执行登录
                await this.loginHandler.performLogin(browser, loginConfig);
            } finally {
                // 确保关闭页面
                await browser.close();
            }
        } catch (error) {
            const errorMessage = error instanceof Error 
                ? error.message 
                : 'Unknown login error';
            this.log.error('Login failed', { error: errorMessage });
            throw error;
        }
    }

    /**
     * 导航前钩子
     */
    protected async preNavigationHook(page: Page, request: any): Promise<void> {
        // 恢复所有存储的状态
        await this.restoreState(page);
    }

    /**
     * 恢复浏览器状态
     */
    private async restoreState(page: Page): Promise<void> {
        // 恢复 cookies
        const cookies = await this.keyValueStore.getValue<any[]>('cookies');
        if (cookies && Array.isArray(cookies)) {
            await page.context().addCookies(cookies);
        }

        // 恢复 localStorage
        const localStorage = await this.keyValueStore.getValue<Record<string, string>>('localStorage');
        if (localStorage) {
            await page.evaluate((storage) => {
                for (const [key, value] of Object.entries(storage)) {
                    window.localStorage.setItem(key, value);
                }
            }, localStorage);
        }

        // 恢复 sessionStorage
        const sessionStorage = await this.keyValueStore.getValue<Record<string, string>>('sessionStorage');
        if (sessionStorage) {
            await page.evaluate((storage) => {
                for (const [key, value] of Object.entries(storage)) {
                    window.sessionStorage.setItem(key, value);
                }
            }, sessionStorage);
        }
    }

    /**
     * 导航后钩子
     */
    protected async postNavigationHook(page: Page, request: any): Promise<void> {
        // 可以在这里添加通用的页面处理逻辑
    }

    /**
     * 请求处理器
     */
    protected abstract handleRequest(context: PlaywrightCrawlingContext): Promise<void>;

    /**
     * 失败请求处理器
     */
    protected async handleFailedRequest(request: any, error: Error): Promise<void> {
        const crawlerError: CrawlerError = {
            type: CrawlerErrorType.NETWORK_ERROR,
            message: error.message,
            url: request.url,
            timestamp: Date.now(),
            stack: error.stack,
        };
        await this.keyValueStore.setValue(`error-${Date.now()}`, crawlerError);
        this.log.error('Request failed', { url: request.url, error: error.message });
    }

    /**
     * 保存数据
     */
    protected async saveData(result: CrawlResult): Promise<void> {
        await this.dataset.pushData(result);
        
        // 更新进度
        this.progress.timestamp = Date.now();
        await this.keyValueStore.setValue('progress', this.progress);
    }

    /**
     * 提取数据
     */
    protected async extractData(
        page: Page,
        rules: ExtractRule[],
        url: string
    ): Promise<CrawlResult> {
        return this.dataHandler.extractData(page, rules, url);
    }

    /**
     * 获取任务进度
     */
    public async getProgress(): Promise<TaskProgress> {
        return this.progress;
    }

    /**
     * 获取爬取的数据
     */
    public async getCrawledData(): Promise<any> {
        if (!this.dataset) {
            throw new Error('Dataset not initialized');
        }
        return this.dataset.getData();
    }
} 