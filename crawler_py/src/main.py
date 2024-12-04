import argparse
import asyncio
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

from crawlers.site.site_crawler import SiteCrawler
from crawlers.site_config.audiences import AudiencesConfig
from crawlers.site_config.btschool import BTSchoolConfig
from crawlers.site_config.carpt import CarptConfig
from crawlers.site_config.frds import FrdsConfig
from crawlers.site_config.haidan import HaidanConfig
from crawlers.site_config.hdatoms import HdatomsConfig
from crawlers.site_config.hdfans import HDFansConfig
from crawlers.site_config.hdhome import HDHomeConfig
from crawlers.site_config.kylin import KylinConfig
from crawlers.site_config.nicept import NicePTConfig
from crawlers.site_config.ourbits import OurBitsConfig
from crawlers.site_config.qingwapt import QingwaPTConfig
from crawlers.site_config.rousi import RousiConfig
from crawlers.site_config.u2 import U2Config
from crawlers.site_config.ubits import UBitsConfig
from crawlers.site_config.zmpt import ZMPTConfig
from crawlers.site_config.iloli import IloliConfig
from crawlers.site_config.hdpt import HdptConfig
from dotenv import load_dotenv
from DrissionPage import ChromiumOptions
from storage.browser_state_manager import BrowserStateManager
from storage.storage_manager import get_storage_manager
from utils.logger import get_logger, setup_logger

# 站点配置映射
SITE_CONFIGS = {
    'ubits': UBitsConfig,
    'ourbits': OurBitsConfig,
    'qingwapt': QingwaPTConfig,
    'hdfans': HDFansConfig,
    'frds': FrdsConfig,
    'hdhome': HDHomeConfig,
    'audiences': AudiencesConfig,
    'rousi': RousiConfig,
    'kylin': KylinConfig,
    'hdatoms': HdatomsConfig,
    'haidan': HaidanConfig,
    'nicept': NicePTConfig,
    'btschool': BTSchoolConfig,
    'carpt': CarptConfig,
    'zmpt': ZMPTConfig,
    'u2': U2Config,
    'iloli': IloliConfig,
    'hdpt': HdptConfig,
    # 其他站点配置可以在这里添加
}

def init_drissionpage():
    """初始化DrissionPage配置"""
    setup_logger()
    main_logger = get_logger(__name__, "Main")
    chrome_path = os.getenv('CHROME_PATH')
    if chrome_path and Path(chrome_path).exists():
        try:
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
    setup_logger()
    crawler_logger = get_logger(__name__, site_id=site)
    try:
        crawler_logger.info(f"开始爬取 {site} 站点数据...")
        
        # 初始化管理器
        storage_manager = get_storage_manager()
        browser_manager = BrowserStateManager(storage_manager)
        
        # 使用统一的SiteCrawler
        crawler = SiteCrawler(task_config, browser_manager=browser_manager)
        asyncio.run(crawler.start())
        
        # 更新站点状态
        asyncio.run(storage_manager.update_site_status(site))
        crawler_logger.info(f"已更新 {site} 的状态信息")
        
        crawler_logger.success(f"完成爬取 {site} 站点数据")
        return True
    except Exception as e:
        crawler_logger.error(f"{site} 爬取失败: {str(e)}")
        return False

async def generate_summary(sites: Optional[list] = None):
    """生成所有站点的状态汇总"""
    storage_manager = get_storage_manager()
    browser_manager = BrowserStateManager(storage_manager)
    main_logger.info("开始扫描所有站点状态...")
    
    # 使用 force_scan=True 强制扫描所有站点
    summary = await storage_manager.get_all_sites_status(force_scan=True)
    main_logger.info("=================== 站点状态汇总 ===================")
    main_logger.info(f"更新时间: {datetime.fromtimestamp(summary.last_updated)}")
    main_logger.info(f"站点数量: {len(summary.sites)}")
    
    for site_id, status in summary.sites.items():
        if (sites) and (not site_id in sites) and (site_id != 'all'):
            continue
        main_logger.info(f"站点: {site_id}")
        main_logger.info(f"最后运行时间: {datetime.fromtimestamp(status.last_run_time)}")
        main_logger.info(f"最后任务ID: {status.last_task}")
        
        # 获取最新的浏览器状态
        browser_state = await browser_manager.restore_state(site_id)
        if browser_state and browser_state.login_state.is_logged_in:
            main_logger.info(f"登录状态: 已登录")
            if browser_state.login_state.username:
                main_logger.info(f"登录用户: {browser_state.login_state.username}")
        else:
            main_logger.info("登录状态: 未登录")
        
        if status.last_error:
            main_logger.error(f"最后错误: {status.last_error.message}")
        
        # 显示最后任务数据
        if hasattr(status, 'last_task_data') and status.last_task_data:
            main_logger.info("最后任务数据:")
            if isinstance(status.last_task_data, list):
                main_logger.info(f"数据条数: {len(status.last_task_data)}")
                if len(status.last_task_data) > 0:
                    main_logger.info("最新数据示例:")
                    for item in status.last_task_data[:3]:  # 只显示前3条
                        main_logger.info(f"  - {str(item)}")
            else:
                main_logger.info(str(status.last_task_data))
        main_logger.info("-------------------------------------------")

def main():
    # 修改命令行参数解析器以接受多个站点
    parser = argparse.ArgumentParser(description='PT站点数据爬取工具')
    parser.add_argument('sites', nargs='*', choices=list(SITE_CONFIGS.keys()) + ['all'], help='要爬取的站点，可指定多个或全部')
    parser.add_argument('--concurrent', '-c', type=int, default=8, help='同时执行的最大爬虫数量(默认: 8)')
    parser.add_argument('--summary', action='store_true', help='生成站点状态汇总报告')
    args = parser.parse_args()
    
    # 如果指定了--summary参数，只生成汇总报告
    if args.summary:
        asyncio.run(generate_summary())
        return
    
    # 如果没有指定站点或指定了'all'，使用所有站点
    if not args.sites or 'all' in args.sites:
        args.sites = list(SITE_CONFIGS.keys())
    
    # 创建任务配置列表
    tasks = []
    for site in args.sites:
        try:
            # 获取站点配置类
            config_class = SITE_CONFIGS[site]
            
            # 创建任务配置
            task_config = config_class.create_task_config()
            tasks.append((site, task_config.dict()))
            
        except Exception as e:
            main_logger.error(f"创建 {site} 的任务配置失败: {str(e)}")
            continue
    
    if not tasks:
        main_logger.error("没有有效的任务配置，退出程序")
        return
    # 用于存储爬虫结果
    results = {
        'success': [],
        'failed': [],
        'error': []
    }
    
    try:
        # 使用进程池执行爬虫任务
        with ProcessPoolExecutor(max_workers=args.concurrent) as executor:
            main_logger.info(f"开始并行爬取 {len(tasks)} 个站点的数据...")
            
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
                        results['success'].append(site)
                    else:
                        main_logger.error(f"{site} 爬取失败")
                        results['failed'].append(site)
                except Exception as e:
                    main_logger.error(f"{site} 爬取过程发生错误: {str(e)}")
                    results['error'].append((site, str(e)))
                
    except Exception as e:
        main_logger.error(f"执行过程中出现错误: {str(e)}")
    
    # 打印爬虫结果汇总
    main_logger.info("=================== 爬虫任务执行结果汇总 ===================")
    main_logger.info(f"总计划任务数: {len(args.sites)}")
    main_logger.success(f"成功任务数: {len(results['success'])}")
    if results['success']:
        main_logger.success(f"成功站点: {', '.join(results['success'])}")
    
    if results['failed']:
        main_logger.error(f"失败任务数: {len(results['failed'])}")
        main_logger.error(f"失败站点: {', '.join(results['failed'])}")
    
    if results['error']:
        main_logger.error(f"错误任务数: {len(results['error'])}")
        for site, error in results['error']:
            main_logger.error(f"站点 {site} 错误信息: {error}")
    
    success_rate = len(results['success']) / len(args.sites) * 100
    main_logger.info(f"任务成功率: {success_rate:.1f}%")
    main_logger.info("==========================================================")
    
    # 在所有任务完成后生成汇总报告
    asyncio.run(generate_summary(args.sites))

if __name__ == "__main__":
    # 加载环境变量
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)

    # 设置日志记录器
    setup_logger()
    main_logger = get_logger(__name__, "Main")

    # 初始化DrissionPage配置
    init_drissionpage()
    main() 