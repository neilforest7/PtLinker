import { TwoCaptchaService } from './2captcha';
import { TesseractService } from './tesseract';
import { BaseCaptchaService } from './base';
import { CaptchaServiceConfig } from './types';

export class CaptchaServiceFactory {
    static createService(method: string, config: CaptchaServiceConfig): BaseCaptchaService {
        switch (method) {
            case 'api':
                return new TwoCaptchaService(config.apiKey, config);
            case 'ocr':
                return new TesseractService(config);
            default:
                throw new Error(`Unsupported captcha handle method: ${method}`);
        }
    }
} 