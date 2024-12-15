from typing import Dict, Optional, Any, ClassVar

from core.logger import get_logger
from services.managers.site_manager import SiteManager
from schemas.sitesetup import SiteSetup
from models.models import SiteConfig, CrawlerConfig, CrawlerCredential, BrowserState


class BaseTaskConfig:
    """爬虫任务基础配置类"""
    
    _task_config: ClassVar[Dict[str, SiteSetup]] = {}  # 任务配置缓存
    _site_manager: ClassVar[Optional[SiteManager]] = None  # 站点管理器实例
    
    def __init__(self, site_id: str):
        self.site_id = site_id
        # 配置属性
        self.site_config: Optional[SiteConfig] = None
        self.crawler_config: Optional[CrawlerConfig] = None
        self.crawler_credential: Optional[CrawlerCredential] = None
        self.browser_state: Optional[BrowserState] = None
        self.logger = get_logger(name=__name__, site_id="taskconf")
        self.load_config()
        
    @classmethod
    def set_site_manager(cls, site_manager: SiteManager):
        """设置站点管理器实例"""
        cls._site_manager = site_manager
        # 更新任务配置缓存
        cls._task_config = site_manager.get_available_sites()
        
    @classmethod
    def get_task_config(cls, site_id: str) -> Optional[SiteSetup]:
        """获取站点的任务配置"""
        return cls._task_config.get(site_id)
        
    async def load_config(self) -> None:
        """加载配置"""
        if not self._site_manager:
            raise RuntimeError("Site manager not set. Please call set_site_manager first.")
            
        # 从任务配置缓存中获取配置
        site_setup = self._task_config.get(self.site_id)
        if not site_setup:
            self.logger.warning(f"Site setup not found for {self.site_id}")
            return
            
        if not site_setup.is_valid():
            self.logger.warning(f"Invalid site setup for {self.site_id}")
            return
            
        # 保存配置到实例属性
        self.site_config = site_setup.site_config if site_setup.site_config else None
        self.crawler_config = site_setup.crawler_config if site_setup.crawler_config else None
        self.crawler_credential = site_setup.crawler_credential if site_setup.crawler_credential else None
        self.browser_state = site_setup.browser_state if site_setup.browser_state else None
        
    @property
    def site_config(self):
        """获取站点配置"""
        return self.site_setup.site_config if self.site_setup else None
        
    @property
    def crawler_config(self):
        """获取爬虫配置"""
        return self.site_setup.crawler_config if self.site_setup else None
        
    @property
    def crawler_credential(self):
        """获取爬虫凭证"""
        return self.site_setup.crawler_credential if self.site_setup else None
        
    @property
    def browser_state(self):
        """获取浏览器状态"""
        return self.site_setup.browser_state if self.site_setup else None