import { ExampleCrawler } from './crawlers/site/example-crawler';
import { CrawlerTaskConfig } from './types/crawler';
import { env, validateEnv } from './config/env.config';

async function runTest() {
    // 验证环境变量
    validateEnv();

    // 测试配置
    const taskConfig: CrawlerTaskConfig = {
        taskId: `test-${Date.now()}`,
        startUrls: ['https://hdfans.org'],
        extractRules: [
            {
                name: 'title',
                selector: 'h1',
                type: 'text',
                required: true
            },
            {
                name: 'content',
                selector: '.content',
                type: 'text'
            }
        ],
        loginConfig: {
            loginUrl: 'https://hdfans.org/login.php',
            formSelector: 'form[action="takelogin.php"]',
            credentials: {
                username: env.LOGIN_USERNAME,
                password: env.LOGIN_PASSWORD
            },
            successCheck: {
                selector: 'a.User_Name',
                expectedText: env.LOGIN_USERNAME
            },
            captcha: {
                imageSelector: 'img[src*="image.php?action=regimage"]',
                inputSelector: 'input[name="imagestring"]',
                handleMethod: env.CAPTCHA_HANDLE_METHOD,
                serviceConfig: {
                    apiKey: env.CAPTCHA_API_KEY,
                    apiUrl: env.CAPTCHA_API_URL
                }
            }
        }
    };

    try {
        console.log('Starting crawler...');
        const crawler = new ExampleCrawler(taskConfig);
        
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