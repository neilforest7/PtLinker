import { Dictionary } from '@crawlee/utils';

// 存储状态
export interface StorageState {
    cookies: any[];
    localStorage: Record<string, string>;
    sessionStorage: Record<string, string>;
    loginState: {
        isLoggedIn: boolean;
        lastLoginTime: number;
        username: string;
    };
}

// 爬取数据
export interface CrawlData {
    url: string;
    data: Dictionary;
    timestamp: number;
    taskId: string;
    siteId: string;  // 站点标识
}

// 错误记录
export interface ErrorRecord {
    type: string;
    message: string;
    url?: string;
    timestamp: number;
    stack?: string;
    screenshot?: Buffer;
    html?: string;
}

// 存储配置
export interface StorageOptions {
    siteId: string;  // 站点标识
    taskId: string;  // 任务ID
    baseDir?: string;  // 基础目录
} 