import { createWorker } from 'tesseract.js';
import { BaseCaptchaService } from './base';
import { CaptchaResult, CaptchaServiceConfig } from './types';
import { Log } from '@crawlee/core';

export class TesseractService extends BaseCaptchaService {
    private worker: Tesseract.Worker | null = null;
    private readonly log: Log;

    constructor(config: CaptchaServiceConfig) {
        super(config);
        this.log = new Log({ prefix: 'TesseractService' });
    }

    async solveCaptcha(imageBase64: string): Promise<CaptchaResult> {
        try {
            this.log.info('Initializing Tesseract worker...');
            
            if (!this.worker) {
                this.worker = await createWorker('eng');
                this.log.info('Tesseract worker initialized');
            }

            this.log.info('Starting OCR recognition...');
            const { data: { text, confidence } } = await this.worker.recognize(
                Buffer.from(imageBase64, 'base64')
            );

            this.log.info('OCR completed', {
                rawText: text,
                confidence: confidence
            });

            // 清理识别结果（移除空格和特殊字符）
            const cleanedText = text.replace(/[^a-zA-Z0-9]/g, '');
            
            this.log.info('Text cleaned', {
                originalText: text,
                cleanedText: cleanedText
            });

            if (!cleanedText) {
                throw new Error('OCR result is empty after cleaning');
            }

            return {
                success: true,
                code: cleanedText,
            };
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown OCR error';
            this.log.error('OCR failed', { error: errorMessage });
            
            return {
                success: false,
                error: errorMessage
            };
        }
    }

    async getBalance(): Promise<number> {
        return 0; // OCR 是本地服务，没有余额概念
    }

    async terminate(): Promise<void> {
        if (this.worker) {
            this.log.info('Terminating Tesseract worker...');
            await this.worker.terminate();
            this.worker = null;
            this.log.info('Tesseract worker terminated');
        }
    }
} 