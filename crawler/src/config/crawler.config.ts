import { PlaywrightCrawlerOptions } from '@crawlee/playwright';

export const DEFAULT_CRAWLER_CONFIG: PlaywrightCrawlerOptions = {
    maxConcurrency: 1,
    maxRequestRetries: 5,
    requestHandlerTimeoutSecs: 60,
    navigationTimeoutSecs: 60,
    preNavigationHooks: [
        async ({ page }) => {
            await page.setExtraHTTPHeaders({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            });
        }
    ]
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
}; 