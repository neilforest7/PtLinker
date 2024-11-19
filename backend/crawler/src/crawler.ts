import { PlaywrightCrawler, Dataset, KeyValueStore, RequestQueue, EventManager } from 'crawlee';
import { PlaywrightCrawlingContext } from 'crawlee/playwright';
import { Router } from 'crawlee';
import { DataSyncService } from './services/sync';
import { createLogger } from './utils/logger';

export interface CrawlerConfig {
    startUrls: string[];
    selectors: Record<string, string>;
    maxRequestsPerCrawl?: number;
    maxConcurrency?: number;
}

export class PTCrawler extends EventManager {
    private crawler: PlaywrightCrawler;
    private router: Router;
    private taskId: string;
    private config: CrawlerConfig;
    private dataset: Dataset;
    private store: KeyValueStore;
    private queue: RequestQueue;
    private syncService: DataSyncService;
    private logger: ReturnType<typeof createLogger>;
    private processedUrls: number = 0;

    constructor(taskId: string, config: CrawlerConfig) {
        super();
        this.taskId = taskId;
        this.config = config;
        this.logger = createLogger(taskId);
        this.router = Router.create();
        this.setupRouter();
    }

    private async setupRouter() {
        // 处理列表页
        this.router.addHandler('LIST', async ({ request, page, log }) => {
            log.info(`Processing list page ${request.url}`);
            const data = await this.extractData(page);
            
            // 同步数据到 API
            await this.syncService.syncData({
                url: request.url,
                data,
                timestamp: new Date().toISOString()
            });
            
            // 更新进度
            this.processedUrls++;
            const progress = Math.floor(
                (this.processedUrls / (this.config.maxRequestsPerCrawl || 1)) * 100
            );
            
            // 发送进度事件
            this.emit('progress', progress);
            
            // 发送日志事件
            this.emit('log', `Processed ${request.url}`, 'info');
            
            // 查找并添加详情页链接
            const detailLinks = await this.extractDetailLinks(page);
            for (const url of detailLinks) {
                await this.queue.addRequest({
                    url,
                    userData: {
                        label: 'DETAIL'
                    }
                });
            }
        });

        // 处理详情页
        this.router.addHandler('DETAIL', async ({ request, page, log }) => {
            log.info(`Processing detail page ${request.url}`);
            const data = await this.extractData(page);
            
            await this.syncService.syncData({
                url: request.url,
                data,
                timestamp: new Date().toISOString()
            });
            
            this.processedUrls++;
            const progress = Math.floor(
                (this.processedUrls / (this.config.maxRequestsPerCrawl || 1)) * 100
            );
            this.emit('progress', progress);
        });
    }

    private async extractDetailLinks(page: Page): Promise<string[]> {
        // 这里可以根据配置提取详情页链接
        const links: string[] = [];
        if (this.config.selectors.detailLink) {
            const elements = await page.$$(this.config.selectors.detailLink);
            for (const element of elements) {
                const href = await element.getAttribute('href');
                if (href) {
                    links.push(new URL(href, page.url()).toString());
                }
            }
        }
        return links;
    }

    private async extractData(page: Page) {
        const data: Record<string, string> = {};
        for (const [key, selector] of Object.entries(this.config.selectors)) {
            if (key === 'detailLink') continue;  // 跳过链接选择器
            try {
                const element = await page.$(selector);
                if (element) {
                    data[key] = await element.textContent() || '';
                }
            } catch (error) {
                this.emit('log', `Error extracting ${key}: ${error}`, 'error');
            }
        }
        return data;
    }

    public async initialize() {
        // 初始化存储和队列
        this.dataset = await Dataset.open(`task-${this.taskId}`);
        this.store = await KeyValueStore.open(`store-${this.taskId}`);
        this.queue = await RequestQueue.open(`queue-${this.taskId}`);

        this.syncService = new DataSyncService(
            {
                apiUrl: process.env.API_URL || 'http://localhost:8000',
                batchSize: 50,
                taskId: this.taskId,
                retryTimes: 3,
                retryDelay: 1000
            },
            this.dataset,
            this.store,
            this.logger
        );

        // 初始化爬虫
        this.crawler = new PlaywrightCrawler({
            requestQueue: this.queue,
            maxRequestsPerCrawl: this.config.maxRequestsPerCrawl,
            maxConcurrency: this.config.maxConcurrency,
            requestHandler: this.router,
            preNavigationHooks: [
                async ({ page, request }) => {
                    await page.setExtraHTTPHeaders({
                        'User-Agent': 'Mozilla/5.0 ...'
                    });
                    this.emit('log', `Navigating to ${request.url}`, 'info');
                }
            ],
            failedRequestHandler: async ({ request, error }) => {
                this.emit('log', `Failed to process ${request.url}: ${error}`, 'error');
                await this.store.setValue(`failed_${Date.now()}`, {
                    url: request.url,
                    error: error.message
                });
            }
        });

        // 处理之前失败的数据
        await this.syncService.processPendingData();
    }

    public async start() {
        try {
            // 添加起始URL到队列
            for (const url of this.config.startUrls) {
                await this.queue.addRequest({
                    url,
                    userData: {
                        label: 'LIST'
                    }
                });
            }

            // 开始爬取
            await this.crawler.run();
            
            // 确保所有数据都已同步
            await this.syncService.processPendingData();
            
            this.emit('log', 'Crawling completed successfully', 'info');
            
        } catch (error) {
            this.emit('log', `Crawling failed: ${error}`, 'error');
            throw error;
        }
    }

    public async stop() {
        await this.crawler.stop();
        await this.syncService.processPendingData();
        this.emit('log', 'Crawler stopped', 'info');
    }
} 