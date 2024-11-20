export type CaptchaServiceType = 'api' | 'ocr' | 'custom';

export interface CaptchaServiceConfig {
    type: CaptchaServiceType;
    apiKey: string;
    apiUrl?: string;
    timeout?: number;
    retries?: number;
    pollingInterval?: number;
    customHandler?: (image: Buffer) => Promise<string>;
    options?: Record<string, any>;
}

export interface CaptchaResult {
    text: string;
    taskId?: string;
    error?: string;
}

export interface ICaptchaService {
    solve(image: Buffer): Promise<string>;
    reportError?(taskId: string): Promise<void>;
    getBalance?(): Promise<number>;
}

export enum CaptchaErrorType {
    NETWORK_ERROR = 'NETWORK_ERROR',
    INVALID_IMAGE = 'INVALID_IMAGE',
    BALANCE_ERROR = 'BALANCE_ERROR',
    TIMEOUT_ERROR = 'TIMEOUT_ERROR',
    API_ERROR = 'API_ERROR'
}

export class CaptchaError extends Error {
    constructor(
        public type: CaptchaErrorType,
        message: string,
        public details?: any
    ) {
        super(message);
        this.name = 'CaptchaError';
    }
} 