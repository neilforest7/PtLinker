import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from DrissionPage import ChromiumOptions
from loguru import logger
from pathlib import Path
from crawlers.site.hdhome_crawler import HDHomeCrawler
from crawlers.site.ourbits_crawler import OurBitsCrawler
from crawlers.site.qingwapt_crawler import QingWaptCrawler
from crawlers.site.hdfans_crawler import HDFansCrawler
from config.sites import SITE_URLS, SITE_CONFIGS, EXTRACT_RULES
import argparse
import json


def init_drissionpage():
    """初始化DrissionPage配置"""
    chrome_path = os.getenv('CHROME_PATH')
    if chrome_path and Path(chrome_path).exists():
        try:
            logger.info(f"设置Chrome路径: {chrome_path}")
            ChromiumOptions().set_browser_path(chrome_path).save()
            return True
        except Exception as e:
            logger.error(f"设置Chrome路径失败: {str(e)}")
            return False
    logger.warning(f"Chrome路径无效或不存在: {chrome_path}")
    return False


# 加载环境变量
load_dotenv()

# 初始化DrissionPage配置
init_drissionpage()

# 爬虫映射
CRAWLERS = {
    'hdhome': HDHomeCrawler,
    'ourbits': OurBitsCrawler,
    'qingwapt': QingWaptCrawler,
    'hdfans': HDFansCrawler
}

async def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='PT站点数据爬取工具')
    parser.add_argument('site', choices=CRAWLERS.keys(), help='要爬取的站点')
    args = parser.parse_args()
    
    # 创建爬虫配置
    task_config = {
        'task_id': f'{args.site}-{int(datetime.now().timestamp())}',
        'site_id': args.site,
        'start_urls': [SITE_URLS[args.site]],
        'login_config': SITE_CONFIGS.get(args.site),
        'extract_rules': EXTRACT_RULES.get(args.site, []),
        'username': os.getenv('LOGIN_USERNAME'),
        'password': os.getenv('LOGIN_PASSWORD')
    }
    
    # 创建并启动爬虫
    crawler_class = CRAWLERS[args.site]
    crawler = crawler_class(task_config)
    
    try:
        print(f"开始爬取 {args.site} 站点数据...")
        await crawler.start()
        print(f"爬取完成")
            
    except Exception as e:
        print(f"爬取过程中出现错误: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 