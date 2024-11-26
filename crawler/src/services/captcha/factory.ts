import { ICaptchaService, CaptchaServiceConfig, CaptchaError, CaptchaErrorType } from './types';
import { TesseractService } from './tesseract';
import { TwoCaptchaService } from './2captcha';
import { Log } from '@crawlee/core';

export class CaptchaServiceFactory {
    private static readonly log = new Log({ prefix: 'CaptchaFactory' });
    private static readonly services = new Map<string, new (config: CaptchaServiceConfig) => ICaptchaService>();

    /**
     * 注册验证码服务
     */
    static registerService(type: string, ServiceClass: new (config: CaptchaServiceConfig) => ICaptchaService): void {
        this.services.set(type, ServiceClass);
        this.log.info(`Registered captcha service: ${type}`);
    }

    /**
     * 创建验证码服务实例
     */
    static createService(config: CaptchaServiceConfig): ICaptchaService {
        // 验证配置
        this.validateConfig(config);

        // 获取服务类
        const ServiceClass = this.services.get(config.type);
        if (!ServiceClass) {
            throw new CaptchaError(
                CaptchaErrorType.API_ERROR,
                `Unsupported captcha service type: ${config.type}`
            );
        }

        try {
            // 创建服务实例
            const service = new ServiceClass(config);
            this.log.info(`Created captcha service instance`, { type: config.type });
            return service;
        } catch (error) {
            throw new CaptchaError(
                CaptchaErrorType.API_ERROR,
                `Failed to create captcha service: ${error instanceof Error ? error.message : String(error)}`,
                { type: config.type }
            );
        }
    }

    /**
     * 验证配置
     */
    private static validateConfig(config: CaptchaServiceConfig): void {
        if (!config.type) {
            throw new CaptchaError(
                CaptchaErrorType.API_ERROR,
                'Captcha service type is required'
            );
        }

        switch (config.type) {
            case 'api':
            case 'turnstile':
                if (!config.apiKey) {
                    throw new CaptchaError(
                        CaptchaErrorType.API_ERROR,
                        `${config.type} requires an API key`
                    );
                }
                break;
            case 'custom':
                if (!config.customHandler) {
                    throw new CaptchaError(
                        CaptchaErrorType.API_ERROR,
                        'Custom captcha service requires a handler function'
                    );
                }
                break;
            case 'ocr':
                break;
            case 'skip':
                break;
            default:
                throw new CaptchaError(
                    CaptchaErrorType.API_ERROR,
                    `Unsupported captcha service type: ${config.type}`
                );
        }
    }
}

// 注册内置服务
CaptchaServiceFactory.registerService('ocr', TesseractService);
CaptchaServiceFactory.registerService('api', TwoCaptchaService);
CaptchaServiceFactory.registerService('turnstile', TwoCaptchaService); 