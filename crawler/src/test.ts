import { HDFansCrawler } from './crawlers/site/hdfans.crawler';
import { QingWaptCrawler } from './crawlers/site/qingwapt.crawler';
import { validateEnv } from './config/env.config';
import { HDHomeCrawler } from './crawlers/site/hdhome.crawler';

async function runTest() {
    // 验证环境变量
    validateEnv();

    try {
        console.log('Starting crawler...');
        // const crawler = new HDFansCrawler();
        // const crawler = new QingWaptCrawler();
        const crawler = new HDHomeCrawler();
        
        // 监听进度
        const progressInterval = setInterval(async () => {
            const progress = await crawler.getProgress();
            console.log('Progress:', progress);
        }, 1000);

        // 开始爬取
        await crawler.start();

        // 清除进度监听
        clearInterval(progressInterval);

        // 爬取完成后，查看结果
        const crawledData = await crawler.getCrawledData();
        if (crawledData && Array.isArray(crawledData.items)) {
            console.log('Crawled data:', crawledData.items);
            console.log(`Total items: ${crawledData.items.length}`);
        } else {
            console.log('No data was crawled');
        }

    } catch (error) {
        if (error instanceof Error) {
            console.error('Crawler failed:', error.message);
        } else {
            console.error('Crawler failed with unknown error');
        }
    }
}

// 运行测试
runTest().catch(error => {
    if (error instanceof Error) {
        console.error('Test failed:', error.message);
    } else {
        console.error('Test failed with unknown error');
    }
}); 