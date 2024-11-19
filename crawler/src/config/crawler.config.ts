import { Configuration } from '@crawlee/core';

export const DEFAULT_CRAWLER_CONFIG: Configuration = {
    // 最大并发请求数
    maxConcurrency: 10,
    // 请求间隔(ms)
    maxRequestRetries: 3,
    // 请求超时时间(ms)
    requestHandlerTimeoutSecs: 30,
    // 是否遵循robots.txt
    respectRobotsTxt: true,
    // 默认等待时间(ms)
    minDelayBetweenRequestsMillis: 500,
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