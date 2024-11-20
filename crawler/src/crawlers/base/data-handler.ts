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
     * 保存爬取数据
     */
    public async saveData(data: CrawlResult): Promise<void> {
        try {
            // 保存到 Dataset
            await this.dataset.pushData({
                ...data,
                timestamp: Date.now()
            });

            // 同时保存一份到 KeyValueStore 作为备份
            await this.keyValueStore.setValue(
                `data-${Date.now()}`,
                data
            );

            this.log.info('Data saved successfully', {
                url: data.url,
                fields: Object.keys(data.data)
            });
        } catch (error) {
            this.log.error('Failed to save data', {
                error: error instanceof Error ? error.message : String(error),
                data
            });
            throw error;
        }
    }

    /**
     * 执行数据提取
     */
    public async extractData(page: Page, rules: ExtractRule[], url: string): Promise<CrawlResult> {
        const data: Record<string, any> = {};
        const errors: string[] = [];

        for (const rule of rules) {
            try {
                const elements = await page.$$(rule.selector);
                if (elements.length === 0) {
                    errors.push(`No data found for rule: ${rule.name}`);
                    continue;
                }

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

                    if (rule.transform && value) {
                        try {
                            return rule.transform(value);
                        } catch (error) {
                            this.log.error('Transform error', {
                                rule: rule.name,
                                value,
                                error: error instanceof Error ? error.message : String(error)
                            });
                            throw error;
                        }
                    }

                    return value;
                }));

                // 过滤空值和null
                const filteredValues = values.filter(v => v !== null && v !== '');
                
                if (filteredValues.length > 0) {
                    data[rule.name] = rule.multiple ? filteredValues : filteredValues[0];
                }

            } catch (error) {
                const errorMessage = error instanceof Error ? error.message : String(error);
                errors.push(`${rule.name}: ${errorMessage}`);
                this.log.error('Extraction error', {
                    rule: rule.name,
                    error: errorMessage
                });
            }
        }

        return {
            url,
            data,
            timestamp: Date.now(),
            taskId: this.taskId,
            errors: errors.length > 0 ? errors : undefined
        };
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
                    const errorMessage = error instanceof Error 
                        ? error.message 
                        : 'Unknown validation error';
                    errors.push(`Validation error for ${rule.name}: ${errorMessage}`);
                }
            }
        }

        return errors;
    }
} 