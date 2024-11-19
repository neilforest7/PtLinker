import { Dictionary } from '@crawlee/utils';

// 存储配置
export interface StorageConfig {
    // 存储目录
    storageDir: string;
    // 数据集配置
    dataset?: {
        // 数据集名称
        name: string;
        // 数据集配置
        options?: Dictionary;
    };
    // KV存储配置
    keyValueStore?: {
        // 存储名称
        name: string;
        // 存储配置
        options?: Dictionary;
    };
}

// 存储结果
export interface StorageResult {
    // 是否成功
    success: boolean;
    // 存储ID
    id?: string;
    // 错误信息
    error?: string;
} 