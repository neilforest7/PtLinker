import axios from 'axios';
import { BaseCaptchaService } from './base';
import { CaptchaResult, CaptchaServiceConfig, ICaptchaService } from './types';
import { Log } from '@crawlee/core';

export class TwoCaptchaService extends BaseCaptchaService implements ICaptchaService {
    private readonly log = new Log({ prefix: '2CaptchaService' });
    private readonly apiKey: string;

    constructor(config: CaptchaServiceConfig) {
        if (!config.apiKey) {
            throw new Error('2Captcha API key is required');
        }
        super(config);
        this.apiKey = config.apiKey;
    }

    async solve(image: Buffer): Promise<string> {
        const taskId = await this.createTask(image);
        return this.getTaskResult(taskId);
    }

    private async createTask(image: Buffer, maxRetries = 5): Promise<string> {
        const requestData = {
            clientKey: this.apiKey,
            task: {
                type: 'ImageToTextTask',
                body: image.toString('base64'),
                phrase: false,
                case: false,
                numeric: false,
                math: 0,
                minLength: 0,
                maxLength: 0
            }
        };

        this.log.info('Creating 2captcha task', {
            apiUrl: this.config.apiUrl,
            imageLength: image.length,
            imageBase64Length: image.toString('base64').length
        });
        let retryCount = 0;
        while (retryCount < maxRetries) {
            try {
                const response = await axios.post(`${this.config.apiUrl || 'http://api.2captcha.com'}/createTask`, 
                    requestData,
                    {
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    }
                );

                this.log.info('2captcha response:', response.data);

                if (response.data.errorId === 0 && response.data.taskId) {
                    return response.data.taskId;
                }

                if (response.data.errorId === 2 && 
                    response.data.errorCode === 'ERROR_NO_SLOT_AVAILABLE') {
                    retryCount++;
                    this.log.info(`Server is overloaded, retrying (${retryCount}/${maxRetries})...`);
                    await new Promise(resolve => setTimeout(resolve, 1000)); // 等待1秒
                    continue;
                }

                throw new Error(response.data.errorDescription || 'Failed to create task');
            } catch (error) {
                if (axios.isAxiosError(error)) {
                    this.log.error('2captcha API error', {
                        status: error.response?.status,
                        data: error.response?.data,
                        headers: error.response?.headers,
                        url: error.config?.url,
                        requestData: requestData,
                        retryCount
                    });
                }
                throw error;
            }
        }

        throw new Error(`Failed to create task after ${maxRetries} retries: Server is overloaded`);
    }

    private async getTaskResult(taskId: string): Promise<string> {
        const startTime = Date.now();
        const requestData = {
            clientKey: this.apiKey,
            taskId: taskId
        };
        
        let pollCount = 0;
        while (Date.now() - startTime < this.config.timeout!) {
            try {
                pollCount++;
                this.log.info(`Polling attempt ${pollCount} for task ${taskId}...`);

                // 添加延迟，避免请求过于频繁
                if (pollCount > 3) {
                    const delay = Math.min(pollCount * 1000, 5000); // 逐步增加延迟，最大5秒
                    this.log.info(`Waiting ${delay}ms before next poll...`);
                    await new Promise(resolve => setTimeout(resolve, delay));
                }

                const response = await axios.post(`${this.config.apiUrl || 'http://api.2captcha.com'}/getTaskResult`,
                    requestData,
                    {
                        headers: {
                            'Content-Type': 'application/json',
                            'Connection': 'close'
                        },
                        // 添加请求超时设置
                        timeout: 30000,
                        // 添加重试配置
                        validateStatus: function (status) {
                            return status >= 200 && status < 300; // 只接受2xx的响应
                        },
                        // 添加代理配置（如果需要）
                        proxy: false,
                    }
                );

                this.log.info(`Poll response for attempt ${pollCount}:`, {
                    data: response.data,
                    status: response.status,
                    headers: response.headers
                });

                if (response.data.status === "ready") {
                    this.log.info('Task completed successfully', {
                        taskId,
                        pollCount,
                        totalTime: Date.now() - startTime
                    });
                    return response.data.solution.text;
                }

                if (response.data.status === "processing") {
                    this.log.info(`Task is still processing, waiting for next poll (attempt ${pollCount})...`);
                    await new Promise(resolve => setTimeout(resolve, this.config.pollingInterval));
                    continue;
                }

                if (response.data.request !== 'CAPCHA_NOT_READY') {
                    this.log.error('Task failed with error', {
                        taskId,
                        error: response.data.request,
                        pollCount
                    });
                    throw new Error(response.data.request);
                }

                this.log.info(`Task not ready, waiting for next poll (attempt ${pollCount})...`);
                await new Promise(resolve => setTimeout(resolve, this.config.pollingInterval));
                
            } catch (error) {
                if (axios.isAxiosError(error)) {
                    this.log.error('Poll request failed', {
                        taskId,
                        pollCount,
                        status: error.response?.status,
                        data: error.response?.data,
                        headers: error.response?.headers,
                        url: error.config?.url,
                        requestData: requestData,
                        errorCode: error.code,
                        errorMessage: error.message
                    });

                    // 如果是连接重置错误，增加等待时间并继续
                    if (error.code === 'ECONNRESET' || error.code === 'ETIMEDOUT') {
                        const retryDelay = Math.min(pollCount * 2000, 10000); // 指数退避，最大10秒
                        this.log.info(`Connection error (${error.code}), waiting ${retryDelay}ms before retry...`);
                        await new Promise(resolve => setTimeout(resolve, retryDelay));
                        continue;
                    }
                }
                throw error;
            }
        }

        this.log.error('Task timeout', {
            taskId,
            pollCount,
            totalTime: Date.now() - startTime
        });

        throw new Error('Timeout waiting for captcha result');
    }

    async getBalance(): Promise<number> {
        try {
            const formData = new URLSearchParams();
            formData.append('key', this.apiKey);
            formData.append('action', 'getbalance');
            formData.append('json', '1');

            const response = await axios.post(`${this.config.apiUrl || 'http://api.2captcha.com'}/getBalance`,
                formData,
                {
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }
                }
            );

            if (response.data.status === 1) {
                return response.data.request;
            }
            throw new Error(response.data.request);
        } catch (error) {
            throw new Error(`Failed to get balance: ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
    }
} 