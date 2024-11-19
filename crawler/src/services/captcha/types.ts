export interface CaptchaServiceConfig {
    apiKey: string;
    apiUrl?: string;
    timeout?: number;
    pollingInterval?: number;
}

export interface TwoCaptchaConfig extends CaptchaServiceConfig {
    softId?: string;
    defaultTimeout?: number;
    recaptchaTimeout?: number;
    pollingInterval?: number;
    apiDomain?: string;
}

export interface CaptchaResult {
    success: boolean;
    code?: string;
    error?: string;
    taskId?: string;
}

export interface CaptchaTask {
    taskId: string;
    status: 'pending' | 'processing' | 'ready' | 'failed';
    solution?: string;
    error?: string;
    cost?: number;
    createTime: number;
} 