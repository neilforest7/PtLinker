import json
import os
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
from DrissionPage import Chromium, ChromiumOptions

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
        
        # 初始化ChromiumOptions
        self.chrome_options = ChromiumOptions().auto_port()
        self.browser: Optional[Chromium] = None
        self.logger = logger.bind(task_id=task_config['task_id'], site_id=self.site_id)

    @abstractmethod
    def _get_site_id(self) -> str:
        """返回站点ID"""
        pass

    async def start(self):
        """启动爬虫"""
        try:
            # 使用ChromiumOptions初始化浏览器
            self.browser = Chromium(self.chrome_options)
            self.logger.debug(f"创建新的浏览器实例，端口: {self.chrome_options}")
            
            try:
                # 尝试恢复登录状态或执行登录
                if await self.login_handler.restore_browser_state(self.browser):
                    self.logger.info("成功恢复登录状态")
                else:
                    self.logger.info("无法恢复登录状态，执行登录流程")
                    await self.login_handler.perform_login(self.browser, self.task_config.login_config)

                # 开始爬取
                await self._crawl(self.browser)

            finally:
                # 清理浏览器资源
                if self.browser:
                    self.logger.debug("关闭浏览器实例")
                    self.browser.quit()

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
    async def _check_login(self, browser: Chromium) -> bool:
        """检查是否已登录"""
        pass

    @abstractmethod
    async def _crawl(self, browser: Chromium):
        """爬取数据的主要逻辑"""
        pass