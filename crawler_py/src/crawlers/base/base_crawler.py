from playwright.async_api import Browser, Page, async_playwright
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path
import os
import json
import traceback
from datetime import datetime
from loguru import logger
from handlers.login import LoginHandler
from models.crawler import CrawlerTaskConfig

class BaseCrawler(ABC):
    def __init__(self, task_config: Dict[str, Any]):
        self.task_config = CrawlerTaskConfig(**task_config)
        self.storage_dir = Path(os.getenv('STORAGE_DIR', 'storage'))
        self.site_id = self._get_site_id()
        
        # 任务数据存储路径
        self.task_storage_path = self.storage_dir / 'tasks' / self.site_id / str(task_config['task_id'])
        self.task_storage_path.mkdir(parents=True, exist_ok=True)
        
        # 初始化登录处理器
        self.login_handler = LoginHandler(self.task_config)
        
        self.browser: Optional[Browser] = None
        self.context = None
        self.page: Optional[Page] = None
        self.logger = logger.bind(task_id=task_config['task_id'], site_id=self.site_id)

    @abstractmethod
    def _get_site_id(self) -> str:
        """返回站点ID"""
        pass

    async def start(self):
        """启动爬虫"""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()

            try:
                # 尝试恢复登录状态
                if await self.login_handler.restore_browser_state(self.page):
                    self.logger.info("成功恢复登录状态")
                    # 验证登录状态是否有效
                    await self.page.goto(self.task_config.start_urls[0])
                    if not await self._check_login():
                        self.logger.warning("登录状态已失效，需要重新登录")
                        await self.login_handler.perform_login(self.page, self.task_config.login_config)
                else:
                    self.logger.info("无法恢复登录状态，执行登录流程")
                    await self.login_handler.perform_login(self.page, self.task_config.login_config)

                # 开始爬取
                await self._crawl()

            finally:
                # 清理浏览器资源
                if self.page:
                    await self.page.close()
                if self.context:
                    await self.context.close()
                if self.browser:
                    await self.browser.close()
                await playwright.stop()

        except Exception as e:
            error_info = {
                'type': 'CRAWLER_ERROR',
                'message': str(e),
                'timestamp': datetime.now().isoformat(),
                'traceback': traceback.format_exc()
            }
            await self._save_error(error_info)
            raise e

    async def _save_data(self, data: Dict[str, Any]):
        """保存爬取的数据到任务目录"""
        data_file = self.task_storage_path / f'data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    async def _save_error(self, error: Dict[str, Any]):
        """保存错误信息到任务目录"""
        error_file = self.task_storage_path / f'error_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        error_file.write_text(json.dumps(error, ensure_ascii=False, indent=2))

    @abstractmethod
    async def _check_login(self) -> bool:
        """检查是否已登录"""
        pass

    @abstractmethod
    async def _crawl(self):
        """爬取数据的主要逻辑"""
        pass