import { program } from 'commander';
import { PTCrawler, CrawlerConfig } from './crawler';
import * as fs from 'fs';

program
    .option('-c, --config <path>', 'Path to config file')
    .option('-t, --task-id <id>', 'Task ID')
    .parse(process.argv);

const options = program.opts();

async function main() {
    try {
        // 读取配置文件
        const configPath = options.config;
        const taskId = options.taskId;
        
        if (!configPath || !taskId) {
            throw new Error('Missing required parameters');
        }
        
        const config: CrawlerConfig = JSON.parse(
            fs.readFileSync(configPath, 'utf-8')
        );
        
        // 创建并初始化爬虫
        const crawler = new PTCrawler(taskId, config);
        await crawler.initialize();
        
        // 设置进度报告
        crawler.on('progress', (progress: number) => {
            console.log(JSON.stringify({
                type: 'progress',
                progress
            }));
        });
        
        // 设置日志报告
        crawler.on('log', (message: string, level: string = 'info') => {
            console.log(JSON.stringify({
                type: 'log',
                message,
                level,
                timestamp: new Date().toISOString()
            }));
        });
        
        // 启动爬虫
        await crawler.start();
        
    } catch (error) {
        console.error(error);
        process.exit(1);
    }
}

main(); 