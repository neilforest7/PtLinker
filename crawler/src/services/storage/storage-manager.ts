import { Dataset, KeyValueStore, Log } from '@crawlee/core';
import { StorageState, StorageOptions, CrawlData, ErrorRecord } from './types';
import { resolve } from 'path';
import { STORAGE_CONFIG } from '../../config/crawler.config';

export class StorageManager {
    private readonly dataset: Dataset;
    private readonly keyValueStore: KeyValueStore;
    private readonly log: Log;
    private readonly options: StorageOptions;
    private readonly storageBasePath: string;

    constructor(
        dataset: Dataset,
        keyValueStore: KeyValueStore,
        options: StorageOptions
    ) {
        this.options = options;
        this.log = new Log({ prefix: `Storage:${options.siteId}` });
        this.storageBasePath = this.getStoragePath();

        // 确保目录存在
        const fs = require('fs');
        [
            this.storageBasePath,
            this.getDatasetPath(),
            this.getKeyValueStorePath(),
            this.getRequestQueuePath()
        ].forEach(dir => {
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
        });

        // 初始化存储
        this.dataset = dataset;
        this.keyValueStore = keyValueStore;

        // 设置存储路径
        process.env.CRAWLEE_STORAGE_DIR = this.storageBasePath;
    }

    /**
     * 获取站点特定的存储路径
     */
    private getStoragePath(): string {
        return this.options.baseDir || STORAGE_CONFIG.storageDir;
    }

    /**
     * 获取站点特定的数据集路径
     */
    private getDatasetPath(): string {
        return resolve(this.storageBasePath, 'datasets');
    }

    /**
     * 获取站点特定的 KeyValueStore 路径
     */
    private getKeyValueStorePath(): string {
        return resolve(this.storageBasePath, 'key_value_stores');
    }

    /**
     * 获取站点特定的请求队列路径
     */
    private getRequestQueuePath(): string {
        return resolve(this.storageBasePath, 'request_queues');
    }

    /**
     * 获取 cookies 文件路径
     */
    private getCookiesPath(): string {
        return resolve(this.storageBasePath, 'cookies.json');
    }

    /**
     * 生成站点特定的键名
     * 确保键名符合 KeyValueStore 的要求：
     * - 最多 256 字符
     * - 只包含 a-zA-Z0-9!-_.'()
     */
    private getKeyWithPrefix(key: string): string {
        // 移除任何不允许的字符
        const sanitizedKey = key.replace(/[^a-zA-Z0-9!_.'()-]/g, '_');
        
        // 构建键名
        const prefix = `${this.options.siteId}`;
        const fullKey = `${prefix}_${sanitizedKey}`;
        
        // 如果键名太长，截断它但保持唯一性
        if (fullKey.length > 256) {
            const hash = require('crypto')
                .createHash('md5')
                .update(fullKey)
                .digest('hex')
                .substring(0, 8);
            
            const maxPrefixLength = 236; // 256 - 8(hash) - 12(分隔符和后缀)
            const truncatedPrefix = prefix.substring(0, maxPrefixLength);
            return `${truncatedPrefix}_${hash}_${sanitizedKey.substring(0, 10)}`;
        }

        return fullKey;
    }

    /**
     * 保存浏览器状态
     */
    async saveBrowserState(state: Partial<StorageState>): Promise<void> {
        try {
            const timestamp = Date.now();
            const stateKey = this.getKeyWithPrefix('browser_state');
            
            // 保存最新状态
            await this.keyValueStore.setValue(stateKey, {
                ...state,
                timestamp,
                siteId: this.options.siteId
            });

            // 保存历史记录
            const historyKey = this.getKeyWithPrefix(`browser_state_history_${timestamp}`);
            await this.keyValueStore.setValue(historyKey, {
                ...state,
                timestamp,
                siteId: this.options.siteId
            });

            this.log.info('Browser state saved', { 
                siteId: this.options.siteId,
                timestamp 
            });
        } catch (error) {
            this.log.error('Failed to save browser state', {
                siteId: this.options.siteId,
                error: error instanceof Error ? error.message : String(error)
            });
            throw error;
        }
    }

    /**
     * 获取最新的浏览器状态
     */
    async getLatestBrowserState(): Promise<StorageState | null> {
        try {
            const stateKey = this.getKeyWithPrefix('browser_state');
            const state = await this.keyValueStore.getValue<StorageState>(stateKey);
            
            if (!state) {
                this.log.info('No browser state found', {
                    siteId: this.options.siteId
                });
                return null;
            }

            this.log.info('Retrieved browser state', {
                siteId: this.options.siteId,
                timestamp: state.loginState?.lastLoginTime
            });

            return state;
        } catch (error) {
            this.log.error('Failed to get browser state', {
                siteId: this.options.siteId,
                error: error instanceof Error ? error.message : String(error)
            });
            throw error;
        }
    }

    /**
     * 保存爬取数据
     */
    async saveCrawlData(data: CrawlData): Promise<void> {
        try {
            const enrichedData = {
                ...data,
                siteId: this.options.siteId,
                timestamp: Date.now()
            };

            // 保存到 Dataset
            await this.dataset.pushData(enrichedData);

            // 备份到 KeyValueStore
            const backupKey = this.getKeyWithPrefix(`data_${Date.now()}`);
            await this.keyValueStore.setValue(backupKey, enrichedData);

            this.log.info('Crawl data saved', { 
                siteId: this.options.siteId,
                url: data.url,
                fields: Object.keys(data.data),
                datasetPath: this.getDatasetPath(),
                keyValueStorePath: this.getKeyValueStorePath()
            });
        } catch (error) {
            this.log.error('Failed to save crawl data', {
                siteId: this.options.siteId,
                error: error instanceof Error ? error.message : String(error),
                data
            });
            throw error;
        }
    }

    /**
     * 保存错误记录
     */
    async saveError(error: ErrorRecord): Promise<void> {
        try {
            const errorKey = this.getKeyWithPrefix(`error_${Date.now()}`);
            const enrichedError = {
                ...error,
                siteId: this.options.siteId,
                timestamp: Date.now()
            };

            await this.keyValueStore.setValue(errorKey, enrichedError);

            // 如果有截图，单独保存
            if (error.screenshot) {
                const screenshotKey = this.getKeyWithPrefix(`error_screenshot_${Date.now()}`);
                await this.keyValueStore.setValue(screenshotKey, error.screenshot, {
                    contentType: 'image/png'
                });
            }

            this.log.info('Error record saved', { 
                siteId: this.options.siteId,
                type: error.type,
                message: error.message
            });
        } catch (error) {
            this.log.error('Failed to save error record', {
                siteId: this.options.siteId,
                error: error instanceof Error ? error.message : String(error)
            });
            throw error;
        }
    }

    /**
     * 清理过期数据
     */
    async cleanupOldData(maxAge: number = 7 * 24 * 60 * 60 * 1000): Promise<void> {
        try {
            const now = Date.now();
            const prefix = this.getKeyWithPrefix('');

            // 获取所有数据
            const { items } = await this.dataset.getData();
            
            // 找出过期的数据
            const expiredItems = items.filter((item: any) => {
                return item.timestamp && (now - item.timestamp > maxAge);
            });

            // 创建新的数据集来存储未过期的数据
            if (expiredItems.length > 0) {
                const validItems = items.filter((item: any) => {
                    return !item.timestamp || (now - item.timestamp <= maxAge);
                });

                // 创建新的数据集
                const newDataset = await Dataset.open(`${this.options.taskId}-cleaned`);
                
                // 保存未过期的数据
                for (const item of validItems) {
                    await newDataset.pushData(item);
                }

                // 记录清理操作
                this.log.info('Dataset cleaned up', {
                    originalCount: items.length,
                    expiredCount: expiredItems.length,
                    remainingCount: validItems.length
                });
            }

            // 清理 KeyValueStore 中的历史数据
            const historyPattern = new RegExp(`^${prefix}.*-history-`);
            const cleanupPromises: Promise<void>[] = [];

            await this.keyValueStore.forEachKey(async (key: string) => {
                if (historyPattern.test(key)) {
                    const timestamp = parseInt(key.split('-').pop() || '0', 10);
                    if (now - timestamp > maxAge) {
                        cleanupPromises.push(this.keyValueStore.setValue(key, null));
                    }
                }
            });

            await Promise.all(cleanupPromises);

            this.log.info('Old data cleaned up', {
                siteId: this.options.siteId,
                expiredItemsCount: expiredItems.length,
                cleanupPromisesCount: cleanupPromises.length
            });
        } catch (error) {
            this.log.error('Failed to cleanup old data', {
                siteId: this.options.siteId,
                error: error instanceof Error ? error.message : String(error)
            });
            throw error;
        }
    }

    /**
     * 保存 cookies 到本地文件和 KeyValueStore
     */
    async saveCookies(cookies: any[]): Promise<void> {
        try {
            // 同时保存到固定位置的文件
            const fs = require('fs');
            const path = require('path');

            // 确保目录存在
            if (!fs.existsSync(this.storageBasePath)) {
                fs.mkdirSync(this.storageBasePath, { recursive: true });
            }

            // 保存 cookies 到固定位置
            const cookiesPath = this.getCookiesPath();
            fs.writeFileSync(
                cookiesPath,
                JSON.stringify(cookies, null, 2),
                'utf8'
            );

            this.log.info('Cookies saved successfully', {
                siteId: this.options.siteId,
                count: cookies.length,
                filePath: cookiesPath
            });
        } catch (error) {
            this.log.error('Failed to save cookies', {
                siteId: this.options.siteId,
                error: error instanceof Error ? error.message : String(error)
            });
            throw error;
        }
    }

    /**
     * 验证 cookies 是否有效
     */
    async validateCookies(page: any): Promise<boolean> {
        try {
            const cookies = await this.getCookies();
            if (!cookies) return false;

            // 设置 cookies
            await page.context().addCookies(cookies);

            // 从 taskConfig 的 startUrls 获取正确的 URL
            const baseUrl = this.options.siteId.includes('.')
                ? this.options.siteId
                : `${this.options.siteId}.org`;  // 添加默认域名
            const url = baseUrl.startsWith('http')
                ? baseUrl
                : `https://${baseUrl}`;

            // 访问首页验证登录状态
            await page.goto(url, {
                waitUntil: 'networkidle'
            });

            // 检查登录状态
            const isLoggedIn = await page.$('a.User_Name');

            // 如果登录成功，更新 cookies
            if (isLoggedIn) {
                const newCookies = await page.context().cookies();
                // 只有当新的 cookies 与旧的不同时才更新
                if (JSON.stringify(newCookies) !== JSON.stringify(cookies)) {
                    await this.saveCookies(newCookies);
                    this.log.info('Cookies updated after validation');
                }
            }

            this.log.info('Cookies validation result', {
                siteId: this.options.siteId,
                isValid: !!isLoggedIn,
                url,
                cookiesCount: cookies.length
            });

            return !!isLoggedIn;
        } catch (error) {
            this.log.error('Failed to validate cookies', {
                siteId: this.options.siteId,
                error: error instanceof Error ? error.message : String(error)
            });
            return false;
        }
    }

    /**
     * 获取本地存储的 cookies
     */
    async getCookies(): Promise<any[] | null> {
        try {
            const cookiesPath = this.getCookiesPath();
            const fs = require('fs');

            if (fs.existsSync(cookiesPath)) {
                const cookiesData = JSON.parse(
                    fs.readFileSync(cookiesPath, 'utf8')
                );
                
                // 检查 cookies 是否过期
                const isExpired = cookiesData.some((cookie: any) => {
                    return cookie.expires && Date.now() > cookie.expires * 1000;
                });

                if (!isExpired) {
                    this.log.info('Cookies loaded from file system', {
                        siteId: this.options.siteId,
                        path: cookiesPath,
                        count: cookiesData.length
                    });
                    return cookiesData;
                } else {
                    this.log.info('Cookies from file system are expired', {
                        siteId: this.options.siteId
                    });
                    // 删除过期的 cookies 文件
                    fs.unlinkSync(cookiesPath);
                }
            }

            this.log.info('No valid cookies found', {
                siteId: this.options.siteId
            });
            return null;

        } catch (error) {
            this.log.error('Failed to get cookies', {
                siteId: this.options.siteId,
                error: error instanceof Error ? error.message : String(error)
            });
            return null;
        }
    }

    /**
     * 删除过期的 cookies
     */
    async cleanupExpiredCookies(): Promise<void> {
        try {
            const cookiesKey = this.getKeyWithPrefix('cookies');
            const data = await this.keyValueStore.getValue<{
                cookies: any[];
                timestamp: number;
                siteId: string;
            }>(cookiesKey);

            if (!data) return;

            const maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days
            if (Date.now() - data.timestamp > maxAge) {
                await this.keyValueStore.setValue(cookiesKey, null);
                this.log.info('Expired cookies cleaned up', {
                    siteId: this.options.siteId
                });
            }
        } catch (error) {
            this.log.error('Failed to cleanup expired cookies', {
                siteId: this.options.siteId,
                error: error instanceof Error ? error.message : String(error)
            });
        }
    }
} 