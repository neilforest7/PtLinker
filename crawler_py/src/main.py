import argparse
import asyncio
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

from config.sites import EXTRACT_RULES, SITE_CONFIGS
from crawlers.site.frds_crawler import FrdsCrawler
from crawlers.site.hdfans_crawler import HDFansCrawler
from crawlers.site.hdhome_crawler import HDHomeCrawler
from crawlers.site.ourbits_crawler import OurBitsCrawler
from crawlers.site.qingwapt_crawler import QingWaptCrawler
from crawlers.site.ubits_crawler import UBitsCrawler
from dotenv import load_dotenv
from DrissionPage import ChromiumOptions
from loguru import logger
from utils.logger import get_logger, setup_logger


def init_drissionpage():
    """初始化DrissionPage配置"""
    chrome_path = os.getenv('CHROME_PATH')
    if chrome_path and Path(chrome_path).exists():
        try:
            main_logger = get_logger(__name__, "Main")
            main_logger.info(f"设置Chrome路径: {chrome_path}")
            ChromiumOptions().set_browser_path(chrome_path).save()
            return True
        except Exception as e:
            main_logger.error(f"设置Chrome路径失败: {str(e)}")
            return False
    main_logger.warning(f"Chrome路径无效或不存在: {chrome_path}")
    return False

def run_crawler(site: str, task_config: dict):
    """在独立进程中运行爬虫"""
    try:
        crawler_logger = get_logger(__name__, site)
        crawler_logger.info(f"开始爬取 {site} 站点数据...")
        crawler_class = CRAWLERS[site]
        crawler = crawler_class(task_config)
        asyncio.run(crawler.start())
        crawler_logger.info(f"完成爬取 {site} 站点数据")
        return True
    except Exception as e:
        crawler_logger.error(f"{site} 爬取失败: {str(e)}")
        return False

# 加载环境变量
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# 设置日志记录器
setup_logger()
main_logger = get_logger(__name__, "Main")

# 初始化DrissionPage配置
init_drissionpage()

# 爬虫映射
CRAWLERS = {
    'hdhome': HDHomeCrawler,
    'ourbits': OurBitsCrawler,
    'qingwapt': QingWaptCrawler,
    'hdfans': HDFansCrawler,
    'ubits': UBitsCrawler,
    'frds': FrdsCrawler
}

def main():
    # 修改命令行参数解析器以接受多个站点
    parser = argparse.ArgumentParser(description='PT站点数据爬取工具')
    parser.add_argument('sites', nargs='+', choices=CRAWLERS.keys(), help='要爬取的站点，可指定多个')
    parser.add_argument('--concurrent', '-c', type=int, default=3, 
                        help='同时执行的最大爬虫数量(默认: 3)')
    args = parser.parse_args()
    
    # 创建任务配置列表
    tasks = []
    for site in args.sites:
        # 创建爬虫配置
        task_config = {
            'task_id': f'{site}-{int(datetime.now().timestamp())}',
            'site_id': site,
            'site_url': [SITE_CONFIGS[site]['site_url']],
            'login_config': SITE_CONFIGS.get(site),
            'extract_rules': EXTRACT_RULES.get(site, []),
            'username': os.getenv('LOGIN_USERNAME'),
            'password': os.getenv('LOGIN_PASSWORD')
        }
        tasks.append((site, task_config))
    
    try:
        # 使用进程池执行爬虫任务
        with ProcessPoolExecutor(max_workers=args.concurrent) as executor:
            main_logger.info(f"开始并行爬取 {len(args.sites)} 个站点的数据...")
            
            # 提交所有任务到进程池
            futures = [
                executor.submit(run_crawler, site, task_config)
                for site, task_config in tasks
            ]
            
            # 等待所有任务完成
            for site, future in zip(args.sites, futures):
                try:
                    success = future.result()
                    if success:
                        main_logger.info(f"{site} 爬取完成")
                    else:
                        main_logger.error(f"{site} 爬取失败")
                except Exception as e:
                    main_logger.error(f"{site} 爬取过程发生错误: {str(e)}")
                
    except Exception as e:
        main_logger.error(f"执行过程中出现错误: {str(e)}")
    
    main_logger.info("所有站点爬取任务已完成")

if __name__ == "__main__":
    main() 