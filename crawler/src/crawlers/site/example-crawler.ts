import { PlaywrightCrawlingContext } from '@crawlee/playwright';
import { BaseCrawler } from '../base/base-crawler';

export class ExampleCrawler extends BaseCrawler {
    protected async handleRequest(context: PlaywrightCrawlingContext): Promise<void> {
        const { page, request } = context;
        
        try {
            // 等待页面加载完成
            await page.waitForLoadState('networkidle');
            
            // 使用数据处理器提取数据
            const result = await this.extractData(
                page,
                this.taskConfig.extractRules,
                request.loadedUrl || request.url
            );
            
            // 保存数据
            await this.saveData(result);
            
            this.log.info('Data extracted successfully', { 
                url: request.url,
                fields: Object.keys(result.data)
            });
            
        } catch (error) {
            const errorMessage = error instanceof Error 
                ? error.message 
                : 'Unknown error occurred';

            this.log.error('Data extraction failed', { 
                url: request.url,
                error: errorMessage
            });

            throw error instanceof Error ? error : new Error(errorMessage);
        }
    }
} 