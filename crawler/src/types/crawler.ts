import { Dictionary } from '@crawlee/utils';
import { Page } from 'playwright';

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

// 表单字段配置
export interface FormField {
    name: string;           // 字段名称
    type: 'text' | 'password' | 'checkbox' | 'radio' | 'hidden' | 'submit';  // 字段类型
    selector: string;       // 字段选择器
    value?: string | boolean;  // 字段值
    required?: boolean;     // 是否必填
    validation?: {         // 字段验证规则
        pattern?: string;   // 正则表达式
        message?: string;   // 错误消息
    };
}

// 登录配置
export interface LoginConfig {
    loginUrl: string;
    formSelector: string;
    // 表单字段映射
    fields: {
        // 基础字段
        username: FormField;     
        password: FormField;     
        // 验证码相关字段（可选）
        captcha?: CaptchaConfig;
        other?: FormField[];
    };
    // 登录前的准备步骤
    preLoginSteps?: PreLoginStep[];
    // 登录成功检查
    successCheck: {
        selector: string;
        expectedText?: string;
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

// 验证码配置
export interface CaptchaConfig {
    // 验证码类型
    type: 'custom';
    // 验证码元素配置
    element: {
        selector: string;  // 验证码元素选择器
        type: 'img' | 'div' | 'iframe';  // 元素类型
        attribute?: string;  // 图片URL属性（如 src, background-image）
    };
    // 输入字段配置
    input: FormField;
    // 验证码hash配置（如果有）
    hash?: {
        selector: string;  // hash元素选择器
        targetField: string;  // 目标字段名
    };
    // 处理方法
    solver: {
        type: 'ocr' | 'api' | 'custom' | 'skip';  // 添加 'skip' 类型
        config?: {
            apiKey?: string;
            apiUrl?: string;
            timeout?: number;
            retries?: number;
        };
    };
    // 添加自定义验证码获取方法
    getCaptchaImage?: (page: Page) => Promise<Buffer | null>;
}

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

export interface PreLoginStep {
    type: 'click' | 'wait' | 'fill';
    selector: string;
    value?: string;
    waitForSelector?: string;
    waitForFunction?: string;
    timeout?: number;
} 