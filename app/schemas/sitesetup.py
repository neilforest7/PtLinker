from datetime import datetime
from typing import Any, Dict, Optional
import json

from pydantic import BaseModel, Field

from schemas.crawlerschemas import CrawlerBase
from schemas.siteconfig import SiteConfigBase
from schemas.crawlerconfig import CrawlerConfigBase
from schemas.crawlercredential import CrawlerCredentialBase
from schemas.browserstate import BrowserState as BrowserStateBase

# 导入 SQLAlchemy 模型用于类型转换
from models.models import (BrowserState, Crawler, CrawlerConfig,
                            CrawlerCredential, SiteConfig)


class SiteSetup(BaseModel):
    """站点配置集合，统一管理站点的所有相关配置"""
    
    site_id: str = Field(..., description="站点ID")
    crawler: Optional[CrawlerBase] = Field(None, description="爬虫配置")
    site_config: Optional[SiteConfigBase] = Field(None, description="站点基础配置")
    crawler_config: Optional[CrawlerConfigBase] = Field(None, description="爬虫配置")
    crawler_credential: Optional[CrawlerCredentialBase] = Field(None, description="爬虫凭证")
    browser_state: Optional[BrowserStateBase] = Field(None, description="浏览器状态")
    
    class Config:
        from_attributes = True
        arbitrary_types_allowed = True

    @classmethod
    def from_orm_models(cls, site_id: str,
                        crawler: Optional[Crawler] = None,
                        site_config: Optional[SiteConfig] = None,
                        crawler_config: Optional[CrawlerConfig] = None,
                        crawler_credential: Optional[CrawlerCredential] = None,
                        browser_state: Optional[BrowserState] = None) -> "SiteSetup":
        """从 SQLAlchemy 模型创建实例"""
        def model_to_dict(model):
            if not model:
                return None
            return {c.name: getattr(model, c.name) for c in model.__table__.columns}

        # 处理site_config的特殊字段
        site_config_dict = None
        if site_config:
            site_config_dict = model_to_dict(site_config)
            # 将JSON字符串转换回字典
            for field in ['login_config', 'extract_rules', 'checkin_config']:
                if site_config_dict.get(field):
                    try:
                        site_config_dict[field] = json.loads(site_config_dict[field])
                    except:
                        site_config_dict[field] = {}

        # 处理browser_state的特殊字段
        browser_state_dict = None
        if browser_state:
            browser_state_dict = model_to_dict(browser_state)
            # 将JSON字符串转换回字典
            for field in ['cookies', 'local_storage', 'session_storage']:
                if browser_state_dict.get(field):
                    try:
                        browser_state_dict[field] = json.loads(browser_state_dict[field])
                    except:
                        browser_state_dict[field] = {}

        return cls(
            site_id=site_id,
            crawler=CrawlerBase.model_validate(model_to_dict(crawler)) if crawler else None,
            site_config=SiteConfigBase.model_validate(site_config_dict) if site_config_dict else None,
            crawler_config=CrawlerConfigBase.model_validate(model_to_dict(crawler_config)) if crawler_config else None,
            crawler_credential=CrawlerCredentialBase.model_validate(model_to_dict(crawler_credential)) if crawler_credential else None,
            browser_state=BrowserStateBase.model_validate(model_to_dict(browser_state)) if browser_state_dict else None
        )
    
    def to_serializable_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典"""
        return {
            "site_id": self.site_id,
            "crawler": self.crawler.model_dump() if self.crawler else None,
            "site_config": self.site_config.model_dump() if self.site_config else None,
            "crawler_config": self.crawler_config.model_dump() if self.crawler_config else None,
            "crawler_credential": self.crawler_credential.model_dump() if self.crawler_credential else None,
            "browser_state": self.browser_state.model_dump() if self.browser_state else None
        }
    
    @classmethod
    def from_serializable_dict(cls, data: Dict[str, Any]) -> "SiteSetup":
        """从可序列化的字典创建实例"""
        return cls(
            site_id=data["site_id"],
            crawler=CrawlerBase.model_validate(data["crawler"]) if data.get("crawler") else None,
            site_config=SiteConfigBase.model_validate(data["site_config"]) if data.get("site_config") else None,
            crawler_config=CrawlerConfigBase.model_validate(data["crawler_config"]) if data.get("crawler_config") else None,
            crawler_credential=CrawlerCredentialBase.model_validate(data["crawler_credential"]) if data.get("crawler_credential") else None,
            browser_state=BrowserStateBase.model_validate(data["browser_state"]) if data.get("browser_state") else None
        )
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_serializable_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> "SiteSetup":
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_serializable_dict(data)
    
    @classmethod
    def create_empty(cls, site_id: str) -> "SiteSetup":
        """创建空的站点配置集合"""
        return cls(
            site_id=site_id,
            crawler=None,
            site_config=None,
            crawler_config=None,
            crawler_credential=None,
            browser_state=None
        )
    
    @classmethod
    def from_dict(cls, site_id: str, data: Dict[str, Any]) -> "SiteSetup":
        """从字典创建站点配置集合"""
        return cls(
            site_id=site_id,
            crawler=CrawlerBase.model_validate(data["crawler"]) if data.get("crawler") else None,
            site_config=SiteConfigBase.model_validate(data["site_config"]) if data.get("site_config") else None,
            crawler_config=CrawlerConfigBase.model_validate(data["crawler_config"]) if data.get("crawler_config") else None,
            crawler_credential=CrawlerCredentialBase.model_validate(data["crawler_credential"]) if data.get("crawler_credential") else None,
            browser_state=BrowserStateBase.model_validate(data["browser_state"]) if data.get("browser_state") else None
        )
    
    def is_complete(self) -> bool:
        """检查配置是否完整"""
        return all([
            self.crawler,
            self.site_config,
            self.crawler_config
        ])
    
    def is_valid(self) -> bool:
        """检查配置是否有效"""
        if not self.is_complete():
            return False
            
        # 检查必要的字段
        if not self.site_config.site_id:
            return False
                
        return True

    def get_crawler(self, key: str, default: Any = None) -> Any:
        """获取爬虫配置值"""
        if not self.crawler:
            return default
        return getattr(self.crawler, key, default)

    def get_site_config(self, key: str, default: Any = None) -> Any:
        """获取站点配置值"""
        if not self.site_config:
            return default
        return getattr(self.site_config, key, default)
    
    def get_crawler_config(self, key: str, default: Any = None) -> Any:
        """获取爬虫配置值"""
        if not self.crawler_config:
            return default
        return getattr(self.crawler_config, key, default)
    
    def get_credential(self, key: str, default: Any = None) -> Any:
        """获取凭证值"""
        if not self.crawler_credential:
            return default
        return getattr(self.crawler_credential, key, default)
    
    def get_browser_state(self, key: str, default: Any = None) -> Any:
        """获取浏览器状态值"""
        if not self.browser_state:
            return default
        return getattr(self.browser_state, key, default)

class BaseResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None
    metadata: Optional[Dict] = None