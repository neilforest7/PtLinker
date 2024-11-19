import { PlaywrightCrawlerOptions } from '@crawlee/playwright';

export const DEFAULT_CRAWLER_CONFIG: PlaywrightCrawlerOptions = {
    maxConcurrency: 10,
    maxRequestRetries: 3,
    requestHandlerTimeoutSecs: 30,
    navigationTimeoutSecs: 30,
};

// 浏览器配置
export const BROWSER_CONFIG = {
    // 是否使用无头模式
    headless: false,
    // 超时设置
    timeout: 30000,
    // 视窗大小
    viewport: {
        width: 1280,
        height: 720
    }
};

// 存储配置
export const STORAGE_CONFIG = {
    // 存储根目录
    storageDir: './storage',
    // 数据集目录
    datasetsDir: './storage/datasets',
    // Key-Value存储目录
    kvStoreDir: './storage/key_value',
}; 