import { Page } from 'playwright';
import { Dataset, KeyValueStore, Log } from '@crawlee/core';
import { 
    ExtractRule, 
    CrawlResult, 
    CrawlerError, 
    CrawlerErrorType 
} from '../../types/crawler';

export class DataHandler {
    private readonly dataset: Dataset;
    private readonly keyValueStore: KeyValueStore;
    private readonly log: Log;
    private readonly taskId: string;

    constructor(dataset: Dataset, keyValueStore: KeyValueStore, log: Log, taskId: string) {
        this.dataset = dataset;
        this.keyValueStore = keyValueStore;
        this.log = log;
        this.taskId = taskId;
    }

    /**
     * 执行数据提取
     */
    public async extractData(page: Page, rules: ExtractRule[], url: string): Promise<CrawlResult> {
        const data: Record<string, any> = {};
        const errors: string[] = [];

        for (const rule of rules) {
            try {
                const value = await this.extractByRule(page, rule);
                if (value !== null) {
                    data[rule.name] = value;
                } else {
                    errors.push(`No data found for rule: ${rule.name}`);
                }
            } catch (error) {
                this.log.error('Extraction error', { 
                    rule: rule.name, 
                    error: error.message 
                });
                errors.push(`${rule.name}: ${error.message}`);
            }
        }

        // 如果所有规则都失败了，抛出错误
        if (Object.keys(data).length === 0) {
            throw new Error(`Data extraction failed: ${errors.join('; ')}`);
        }

        const result: CrawlResult = {
            url,
            data,
            timestamp: Date.now(),
            taskId: this.taskId,
            // 添加部分失败的错误信息
            errors: errors.length > 0 ? errors : undefined
        };

        await this.saveData(result);
        return result;
    }

    /**
     * 根据规则提取数据
     */
    private async extractByRule(page: Page, rule: ExtractRule): Promise<any> {
        const elements = await page.$$(rule.selector);
        
        if (elements.length === 0) {
            return null;
        }

        // 处理多个元素的情况
        const values = await Promise.all(elements.map(async (element) => {
            let value: string;
            
            switch (rule.type) {
                case 'text':
                    value = (await element.textContent() || '').trim();
                    break;
                case 'attribute':
                    if (!rule.attribute) {
                        throw new Error(`Attribute not specified for rule: ${rule.name}`);
                    }
                    value = (await element.getAttribute(rule.attribute) || '').trim();
                    break;
                case 'html':
                    value = (await element.innerHTML() || '').trim();
                    break;
                default:
                    throw new Error(`Unknown extraction type: ${rule.type}`);
            }

            // 应用转换函数
            if (rule.transform && value) {
                try {
                    return rule.transform(value);
                } catch (error) {
                    this.log.error('Transform error', { 
                        rule: rule.name, 
                        value, 
                        error: error.message 
                    });
                    throw error;
                }
            }

            return value;
        }));

        // 过滤空值
        const filteredValues = values.filter(v => v !== null && v !== '');
        
        // 根据提取到的元素数量返回单个值或数组
        return filteredValues.length === 1 ? filteredValues[0] : filteredValues;
    }

    /**
     * 保存数据
     */
    private async saveData(result: CrawlResult): Promise<void> {
        try {
            // 保存到Dataset
            await this.dataset.pushData(result);

            // 保存原始HTML快照（可选）
            if (result.saveSnapshot) {
                await this.keyValueStore.setValue(
                    `snapshot-${result.taskId}-${Date.now()}`,
                    result.snapshot
                );
            }

            this.log.info('Data saved successfully', { 
                url: result.url,
                fields: Object.keys(result.data)
            });

        } catch (error) {
            const crawlerError: CrawlerError = {
                type: CrawlerErrorType.STORAGE_ERROR,
                message: error.message,
                url: result.url,
                timestamp: Date.now(),
                stack: error.stack,
            };
            await this.keyValueStore.setValue(`storage-error-${Date.now()}`, crawlerError);
            throw error;
        }
    }

    /**
     * 验证提取的数据
     */
    public validateData(data: Record<string, any>, rules: ExtractRule[]): string[] {
        const errors: string[] = [];

        for (const rule of rules) {
            if (rule.required && !data[rule.name]) {
                errors.push(`Missing required field: ${rule.name}`);
            }

            if (rule.validator && data[rule.name]) {
                try {
                    const isValid = rule.validator(data[rule.name]);
                    if (!isValid) {
                        errors.push(`Validation failed for field: ${rule.name}`);
                    }
                } catch (error) {
                    errors.push(`Validation error for ${rule.name}: ${error.message}`);
                }
            }
        }

        return errors;
    }
} 