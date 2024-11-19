import { Dictionary } from '@crawlee/utils';

// 爬虫任务配置
export interface CrawlerTaskConfig {
    // 任务ID
    taskId: string;
    // 起始URL
    startUrls: string[];
    // 登录配置
    loginConfig?: LoginConfig;
    // 数据提取规则
    extractRules: ExtractRule[];
    // 自定义配置
    customConfig?: Dictionary;
}

// 登录配置
export interface LoginConfig {
    // 登录页面URL
    loginUrl: string;
    // 登录表单选择器
    formSelector: string;
    // 登录凭证
    credentials: {
        username: string;
        password: string;
    };
    // 登录成功检查
    successCheck: {
        // 成功标识选择器
        selector: string;
        // 期望的文本内容(可选)
        expectedText?: string;
    };
    // 验证码配置
    captcha?: {
        // 验证码图片选择器
        imageSelector: string;
        // 验证码输入框选择器
        inputSelector: string;
        // 验证码处理方式：'manual' | 'ocr' | 'api'
        handleMethod: string;
        // 验证码服务配置（如果使用第三方服务）
        serviceConfig?: {
            apiKey?: string;
            apiUrl?: string;
        };
    };
}

// 数据提取规则
export interface ExtractRule {
    // 规则名称
    name: string;
    // 选择器
    selector: string;
    // 提取类型
    type: 'text' | 'attribute' | 'html';
    // 属性名(当type为attribute时必填)
    attribute?: string;
    // 数据处理函数
    transform?: (value: string) => any;
    required?: boolean;
    validator?: (value: any) => boolean;
    multiple?: boolean;
}

// 爬取结果
export interface CrawlResult {
    // URL
    url: string;
    // 提取的数据
    data: Dictionary;
    // 时间戳
    timestamp: number;
    // 任务ID
    taskId: string;
    errors?: string[];
    saveSnapshot?: boolean;
    snapshot?: string;
}

// 错误类型
export enum CrawlerErrorType {
    NETWORK_ERROR = 'NETWORK_ERROR',
    LOGIN_FAILED = 'LOGIN_FAILED',
    EXTRACTION_FAILED = 'EXTRACTION_FAILED',
    VALIDATION_FAILED = 'VALIDATION_FAILED',
    STORAGE_ERROR = 'STORAGE_ERROR',
}

// 错误详情
export interface CrawlerError {
    type: CrawlerErrorType;
    message: string;
    url?: string;
    timestamp: number;
    stack?: string;
} 