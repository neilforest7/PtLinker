import axios from 'axios';
import { BaseCaptchaService } from './base';
import { CaptchaResult, CaptchaTask, TwoCaptchaConfig } from './types';
import { Log } from '@crawlee/core';

export class TwoCaptchaService extends BaseCaptchaService {
    private readonly baseUrl: string;
    private readonly log: Log;

    constructor(apiKey: string, config?: Partial<TwoCaptchaConfig>) {
        super({ apiKey, ...config });
        this.baseUrl = this.config.apiUrl || 'http://api.2captcha.com';
        this.log = new Log({ prefix: 'TwoCaptchaService' });
    }

    async solveCaptcha(imageBase64: string): Promise<CaptchaResult> {
        try {
            // 1. 创建任务
            const taskId = await this.createTask(imageBase64);
            if (!taskId) {
                return { success: false, error: 'Failed to create captcha task' };
            }

            // 2. 获取结果
            const result = await this.getTaskResult(taskId);
            return result;

        } catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Unknown error'
            };
        }
    }

    private async createTask(imageBase64: string, maxRetries = 5): Promise<string> {
        const requestData = {
            clientKey: this.config.apiKey,
            task: {
                type: 'ImageToTextTask',
                body: imageBase64,
                phrase: false,
                case: false,
                numeric: false,
                math: 0,
                minLength: 0,
                maxLength: 0
            }
        };

        this.log.info('Creating 2captcha task', {
            apiUrl: this.baseUrl,
            imageLength: imageBase64.length
        });

        let retryCount = 0;
        while (retryCount < maxRetries) {
            try {
                const response = await axios.post(`${this.baseUrl}/createTask`, 
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

    private async getTaskResult(taskId: string): Promise<CaptchaResult> {
        const startTime = Date.now();
        const requestData = {
            clientKey: this.config.apiKey,
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

                const response = await axios.post(`${this.baseUrl}/getTaskResult`,
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
                    return {
                        success: true,
                        code: response.data.solution.text,
                        taskId
                    };
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
                    return {
                        success: false,
                        error: response.data.request,
                        taskId
                    };
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

        return {
            success: false,
            error: 'Timeout waiting for captcha result',
            taskId
        };
    }

    async getBalance(): Promise<number> {
        try {
            const formData = new URLSearchParams();
            formData.append('key', this.config.apiKey);
            formData.append('action', 'getbalance');
            formData.append('json', '1');

            const response = await axios.post(`${this.baseUrl}/getBalance`,
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