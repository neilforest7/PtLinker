import { CaptchaServiceConfig, ICaptchaService } from './types';

export abstract class BaseCaptchaService implements ICaptchaService {
    protected config: CaptchaServiceConfig;

    constructor(config: CaptchaServiceConfig) {
        this.config = {
            timeout: 120000,
            pollingInterval: 5000,
            ...config
        };
    }

    abstract solve(image: Buffer): Promise<string>;
} 