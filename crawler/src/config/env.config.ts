import * as dotenv from 'dotenv';
import { resolve } from 'path';

// 加载环境变量
dotenv.config({ path: resolve(__dirname, '../../.env') });

export interface EnvConfig {
    // Crawler Configuration
    CRAWLER_HEADLESS: boolean;
    CRAWLER_MAX_CONCURRENCY: number;

    // Captcha Configuration
    CAPTCHA_HANDLE_METHOD: 'api' | 'ocr' | 'manual';
    CAPTCHA_API_KEY: string;
    CAPTCHA_API_URL: string;

    // Login Credentials
    LOGIN_USERNAME: string;
    LOGIN_PASSWORD: string;
}

export const env: EnvConfig = {
    // Crawler Configuration
    CRAWLER_HEADLESS: process.env.CRAWLER_HEADLESS === 'true',
    CRAWLER_MAX_CONCURRENCY: Number(process.env.CRAWLER_MAX_CONCURRENCY || 10),

    // Captcha Configuration
    CAPTCHA_HANDLE_METHOD: (process.env.CAPTCHA_HANDLE_METHOD || 'manual') as 'api' | 'ocr' | 'manual',
    CAPTCHA_API_KEY: process.env.CAPTCHA_API_KEY || '',
    CAPTCHA_API_URL: process.env.CAPTCHA_API_URL || 'http://api.2captcha.com',

    // Login Credentials
    LOGIN_USERNAME: process.env.LOGIN_USERNAME || '',
    LOGIN_PASSWORD: process.env.LOGIN_PASSWORD || ''
};

// 验证必需的环境变量
export function validateEnv(): void {
    const requiredEnvVars = [
        'CAPTCHA_API_KEY',
        'LOGIN_USERNAME',
        'LOGIN_PASSWORD'
    ];

    const missingEnvVars = requiredEnvVars.filter(
        varName => !process.env[varName]
    );

    if (missingEnvVars.length > 0) {
        throw new Error(
            `Missing required environment variables: ${missingEnvVars.join(', ')}`
        );
    }
} 