import { PlaywrightCrawlingContext } from '@crawlee/playwright';
import { BaseCrawler } from '../base/base-crawler';
import { CrawlResult } from '../../types/crawler';

export class ExampleCrawler extends BaseCrawler {
    protected async handleRequest(context: PlaywrightCrawlingContext): Promise<void> {
        const { page, request } = context;
        
        // 等待页面加载完成
        await page.waitForLoadState('networkidle');
        
        try {
            // 使用数据处理器提取数据
            const result = await this.extractData(
                page,
                this.taskConfig.extractRules,
                request.url
            );
            
            this.log.info('Data extracted successfully', { 
                url: request.url,
                fields: Object.keys(result.data)
            });
            
        } catch (error) {
            this.log.error('Data extraction failed', { 
                url: request.url,
                error: error.message 
            });
            throw error;
        }
    }
} 