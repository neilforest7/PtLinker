import axios from 'axios';
import { Dataset, KeyValueStore } from 'crawlee';
import { Logger } from 'winston';
import { BatchProcessor } from './batch-processor';

interface SyncConfig {
    apiUrl: string;
    batchSize: number;
    taskId: string;
    retryTimes: number;
    retryDelay: number;
}

export class DataSyncService {
    private batchProcessor: BatchProcessor;
    private dataset: Dataset;
    private store: KeyValueStore;
    private logger: Logger;
    
    constructor(
        private config: SyncConfig,
        dataset: Dataset,
        store: KeyValueStore,
        logger: Logger
    ) {
        this.dataset = dataset;
        this.store = store;
        this.logger = logger;
        this.batchProcessor = new BatchProcessor(config.batchSize);
    }
    
    async syncData(data: any) {
        await this.batchProcessor.add(data, async (batch) => {
            await this.sendBatch(batch);
        });
    }
    
    private async sendBatch(batch: any[]) {
        let retries = 0;
        while (retries < this.config.retryTimes) {
            try {
                await axios.post(`${this.config.apiUrl}/api/v1/data/batch`, {
                    taskId: this.config.taskId,
                    data: batch
                });
                this.logger.info(`Successfully synced batch of ${batch.length} items`);
                return;
            } catch (error) {
                retries++;
                this.logger.warn(`Sync failed, attempt ${retries}/${this.config.retryTimes}`);
                if (retries < this.config.retryTimes) {
                    await new Promise(resolve => 
                        setTimeout(resolve, this.config.retryDelay)
                    );
                } else {
                    // 存储失败的数据到 KeyValueStore 以便后续重试
                    await this.store.setValue(
                        `failed_batch_${Date.now()}`,
                        batch
                    );
                    throw error;
                }
            }
        }
    }
    
    async processPendingData() {
        // 处理之前失败的数据
        const failedKeys = await this.store.getKeys();
        for (const key of failedKeys) {
            if (key.startsWith('failed_batch_')) {
                const batch = await this.store.getValue(key);
                try {
                    await this.sendBatch(batch);
                    await this.store.deleteKey(key);
                } catch (error) {
                    this.logger.error(
                        `Failed to process pending batch ${key}`,
                        error
                    );
                }
            }
        }
    }
} 