import axios from 'axios';
import { SiteConfigResponse, CrawlerConfigResponse, SettingsResponse, CrawlerCredentialResponse, TaskResponse } from '../types/api';

const BASE_URL = '/api/v1';

export const siteConfigApi = {
    // 获取站点配置
    getSiteConfig: async (siteId: string): Promise<SiteConfigResponse> => {
        const response = await axios.get(`${BASE_URL}/site-configs/${siteId}`);
        return response.data;
    },

    // 获取爬虫配置
    getCrawlerConfig: async (siteId: string): Promise<CrawlerConfigResponse> => {
        const response = await axios.get(`${BASE_URL}/crawler-configs`, {
            params: { site_id: siteId }
        });
        return response.data[0]; // 返回第一个配置
    },

    // 获取全局设置
    getGlobalSettings: async (): Promise<SettingsResponse> => {
        const response = await axios.get(`${BASE_URL}/settings`);
        return response.data;
    },

    // 获取站点凭证
    getCredential: async (siteId: string): Promise<CrawlerCredentialResponse> => {
        const response = await axios.get(`${BASE_URL}/credentials/${siteId}`);
        return response.data;
    },

    // 更新站点凭证
    updateCredential: async (siteId: string, credential: Partial<CrawlerCredentialResponse>): Promise<CrawlerCredentialResponse> => {
        // 移除所有未定义或空值的字段
        const cleanCredential = Object.fromEntries(
            Object.entries(credential)
                .filter(([_, value]) => value !== undefined && value !== null)
        );
        
        const response = await axios.put(`${BASE_URL}/credentials/${siteId}`, {
            site_id: siteId,
            ...cleanCredential
        });
        return response.data;
    },

    // 更新站点配置
    updateSiteConfig: async (siteId: string, config: Partial<SiteConfigResponse>): Promise<SiteConfigResponse> => {
        // 移除所有未定义或空值的字段
        const cleanConfig = Object.fromEntries(
            Object.entries(config)
                .filter(([_, value]) => value !== undefined && value !== null)
        );
        
        const response = await axios.put(`${BASE_URL}/site-configs/${siteId}`, {
            site_id: siteId,
            ...cleanConfig
        });
        return response.data;
    },

    // 更新爬虫配置
    updateCrawlerConfig: async (siteId: string, config: Partial<CrawlerConfigResponse>): Promise<CrawlerConfigResponse> => {
        // 移除所有未定义或空值的字段
        const cleanConfig = Object.fromEntries(
            Object.entries(config)
                .filter(([_, value]) => value !== undefined && value !== null)
        );
        
        const response = await axios.put(`${BASE_URL}/crawler-configs/${siteId}`, {
            site_id: siteId,
            ...cleanConfig
        });
        return response.data;
    },

    // 获取所有站点配置
    getAllSiteConfigs: async (): Promise<SiteConfigResponse[]> => {
        const response = await axios.get(`${BASE_URL}/site-configs`);
        return response.data;
    },

    // 获取站点统计数据
    getSiteStatistics: async (siteId?: string) => {
        const response = await axios.get(`${BASE_URL}/statistics`, {
            params: {
                site_id: siteId,
                metrics: ['daily_results'],
                time_unit: 'day',
                calculation: 'last'
            }
        });
        return response.data;
    },

    // 获取站点任务列表
    getSiteTasks: async (siteId: string, limit: number = 1): Promise<TaskResponse[]> => {
        const response = await axios.get(`${BASE_URL}/tasks/`, {
            params: {
                site_id: siteId,
                limit
            }
        });
        return response.data;
    },

    // 获取所有站点的最新任务
    getAllSitesTasks: async (limit: number = 30): Promise<TaskResponse[]> => {
        const response = await axios.get(`${BASE_URL}/tasks/`, {
            params: { limit }
        });
        return response.data;
    },

    // 创建任务（可选指定站点或为所有站点创建）
    createTasks: async (createForAllSites: boolean = true, siteId?: string): Promise<TaskResponse[]> => {
        const response = await axios.post(`${BASE_URL}/tasks`, null, {
            params: {
                site_id: siteId,
                create_for_all_sites: createForAllSites
            }
        });
        return response.data;
    },

    // 重试失败的任务
    retryFailedTasks: async (): Promise<TaskResponse[]> => {
        const response = await axios.post(`${BASE_URL}/tasks/retry-failed`);
        return response.data;
    },

    // 启动所有待处理任务
    startQueueTasks: async (): Promise<any> => {
        const response = await axios.post(`${BASE_URL}/queue/start`);
        return response.data;
    },

    // 清除待处理任务队列
    clearPendingTasks: async (siteId?: string): Promise<any> => {
        const response = await axios.delete(`${BASE_URL}/queue/clear`, {
            params: { site_id: siteId }
        });
        return response.data;
    },
}; 