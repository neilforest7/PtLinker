import { ExampleCrawler } from './crawlers/site/example-crawler';
import { CrawlerTaskConfig } from './types/crawler';

async function runTest() {
    // 测试配置
    const taskConfig: CrawlerTaskConfig = {
        taskId: `test-${Date.now()}`,
        startUrls: ['https://example.com'], // 替换为你要测试的网址
        extractRules: [
            {
                name: 'title',
                selector: 'h1', // 替换为实际的选择器
                type: 'text',
                required: true
            },
            {
                name: 'content',
                selector: '.content', // 替换为实际的选择器
                type: 'text'
            },
            // 可以添加更多规则
        ],
        // 如果需要登录，添加登录配置
        loginConfig: {
            loginUrl: 'https://example.com/login',
            formSelector: 'form#login',
            credentials: {
                username: 'your-username',
                password: 'your-password'
            },
            successCheck: {
                selector: '.user-profile',
                expectedText: 'Welcome'
            }
        }
    };

    try {
        const crawler = new ExampleCrawler(taskConfig);
        
        // 监听进度
        setInterval(async () => {
            const progress = await crawler.getProgress();
            console.log('Progress:', progress);
        }, 1000);

        // 开始爬取
        await crawler.start();

        // 爬取完成后，查看结果
        const dataset = await crawler.dataset.getData();
        console.log('Crawled data:', dataset);

    } catch (error) {
        console.error('Crawler failed:', error);
    }
}

// 运行测试
runTest().catch(console.error); 