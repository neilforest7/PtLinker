import { CaptchaServiceConfig, CaptchaResult } from './types';

export abstract class BaseCaptchaService {
    protected config: CaptchaServiceConfig;

    constructor(config: CaptchaServiceConfig) {
        this.config = {
            timeout: 120000, // 默认2分钟超时
            pollingInterval: 5000, // 默认5秒轮询一次
            ...config
        };
    }

    abstract solveCaptcha(imageBase64: string): Promise<CaptchaResult>;
    abstract getBalance(): Promise<number>;
} 