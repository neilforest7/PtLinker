import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger, setup_logger
from models.models import (BrowserState, Crawler, CrawlerConfig,
                           CrawlerCredential, SiteConfig)
from schemas.browserstate import BrowserState as BrowserStateBase
from schemas.crawlerconfig import CrawlerConfigBase
from schemas.crawlercredential import CrawlerCredentialBase
from schemas.crawlerschemas import CrawlerBase
from schemas.siteconfig import SiteConfigBase
from schemas.sitesetup import SiteSetup
from services.managers.setting_manager import settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class SiteManager:
    """站点配置管理器，负责加载和管理站点配置"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SiteManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._sites = {}
            # setup_logger()
            self.logger = get_logger(name=__name__, site_id="site_manager")
            self._initialized = True
            
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def _load_site_setup(self, db: AsyncSession) -> Dict[str, SiteSetup]:
        """加载所有站点配置
        
        Returns:
            Dict[str, SiteSetup]: 以site_id为键的站点配置字典
        """
        site_setups = {}
        
        # 加载所有配置
        crawler = await self._load_crawlers(db)
        site_configs = await self._load_site_configs(db)
        crawler_configs = await self._load_crawler_configs(db)
        credentials = await self._load_credentials(db)
        browser_states = await self._load_browser_states(db)
        
        # 合并配置
        for site_id in site_configs.keys():
            # 使用 from_orm_models 创建 SiteSetup 实例
            # TODO: 考虑简化from_orm_models方法
            site_setups[site_id] = SiteSetup.from_orm_models(
                site_id=site_id,
                crawler=crawler.get(site_id),
                site_config=site_configs.get(site_id),
                crawler_config=crawler_configs.get(site_id),
                crawler_credential=credentials.get(site_id),
                browser_state=browser_states.get(site_id)
            )
            
        # 检查是否有本地配置文件但数据库中没有的站点
        config_dir = await settings.get_setting("crawler_config_path")
        if config_dir and Path(config_dir).exists():
            for site_dir in Path(config_dir).iterdir():
                if site_dir.is_dir() or site_dir.name.startswith('_'):
                    continue
                    
                site_id = site_dir.name.replace(".json", "")
                if site_id not in site_setups:
                    # 从本地加载配置
                    self.logger.info(f"从本地加载配置: {site_id}")
                    local_setup = await self._load_local_site_setup(site_id)
                    if local_setup and local_setup.is_valid():
                        site_setups[site_id] = local_setup
                        self.logger.info(f"从本地加载配置成功: {site_id}")
                        
                        # 保存到数据库
                        try:
                            # 首先创建 Crawler 记录
                            crawler = Crawler(
                                site_id=site_id,
                                is_logged_in=False,
                                total_tasks=0
                            )
                            db.add(crawler)
                            await db.flush()  # 确保 crawler 记录被创建
                            
                            if local_setup.site_config:
                                # 转换配置数据，确保URL是字符串，字典转为JSON
                                site_config_data = local_setup.site_config.model_dump()
                                site_config_data['login_config'] = json.dumps(site_config_data['login_config'])
                                site_config_data['extract_rules'] = json.dumps(site_config_data['extract_rules'])
                                site_config_data['checkin_config'] = json.dumps(site_config_data['checkin_config'])
                                db.add(SiteConfig(**site_config_data))
                            if local_setup.crawler_config:
                                db.add(CrawlerConfig(**local_setup.crawler_config.model_dump()))
                            if local_setup.crawler_credential:
                                db.add(CrawlerCredential(**local_setup.crawler_credential.model_dump()))
                            if local_setup.browser_state:
                                db.add(BrowserState(**local_setup.browser_state.model_dump()))
                            await db.commit()
                            self.logger.info(f"保存本地配置到数据库成功: {site_id}")
                        except Exception as e:
                            self.logger.error(f"保存本地配置到数据库失败: {site_id}: {str(e)}")
                            await db.rollback()
            
        return site_setups
        
    async def initialize(self, db: AsyncSession):
        """初始化站点管理器"""
        # 加载所有站点配置
        self._sites = await self._load_site_setup(db)
        self.logger.info(f"站点管理器初始化成功，共加载 {len(self._sites)} 个站点")
            
    async def get_available_sites(self) -> Dict[str, SiteSetup]:
        """获取所有可用的站点配置"""
        return self._sites
        
    async def get_site_setup(self, site_id: str) -> SiteSetup|None:
        """获取站点配置"""
        return self._sites.get(site_id)
        
    async def update_site_setup(self, db: AsyncSession, site_id: str, 
                                new_crawler: Optional[Crawler] = None,
                                new_site_config: Optional[SiteConfig] = None,
                                new_crawler_config: Optional[CrawlerConfig] = None,
                                new_crawler_credential: Optional[CrawlerCredential] = None,
                                new_browser_state: Optional[BrowserState] = None) -> bool:
        """更新站点配置"""
        try:
            # 检查 crawler 记录是否存在
            stmt = select(Crawler).where(Crawler.site_id == site_id)
            result = await db.execute(stmt)
            existing_crawler = result.scalar_one_or_none()
            
            if not existing_crawler and not new_crawler:
                # 如果不存在 crawler 记录且没有提供新的记录，创建一个新的
                new_crawler = Crawler(
                    site_id=site_id,
                    is_logged_in=False,
                    total_tasks=0
                )
                self.logger.info(f"创建新的 crawler 记录: {site_id}")
            
            # 更新指定部分的新配置
            if new_crawler:
                if existing_crawler:
                    # 更新现有记录
                    for key, value in new_crawler.__dict__.items():
                        if not key.startswith('_'):
                            setattr(existing_crawler, key, value)
                else:
                    # 添加新记录
                    db.add(new_crawler)
                    existing_crawler = new_crawler
                
                self._sites[site_id].crawler = CrawlerBase.model_validate(new_crawler)
            
            # 确保先提交 crawler 记录
            await db.flush()
            
            if new_site_config:
                self._sites[site_id].site_config = SiteConfigBase.model_validate(new_site_config)
                db.add(new_site_config)
                    
            if new_crawler_config:
                self._sites[site_id].crawler_config = CrawlerConfigBase.model_validate(new_crawler_config)
                db.add(new_crawler_config)

            if new_crawler_credential:
                self._sites[site_id].crawler_credential = CrawlerCredentialBase.model_validate(new_crawler_credential)
                db.add(new_crawler_credential)

            if new_browser_state:
                self._sites[site_id].browser_state = BrowserStateBase.model_validate(new_browser_state)
                db.add(new_browser_state)
                    
            # 提交所有更改
            await db.commit()
            self.logger.info(f"更新站点配置成功: {site_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"更新站点配置失败 {site_id}: {str(e)}")
            await db.rollback()
            return False
        
    async def _load_crawlers(self, db: AsyncSession) -> Dict[str, Crawler]:
        """加载所有爬虫配置"""
        result = await db.execute(select(Crawler))
        return {cr.site_id: cr for cr in result.scalars().all()}
        
    async def _load_site_configs(self, db: AsyncSession) -> Dict[str, SiteConfig]:
        """加载所有站点配置"""
        result = await db.execute(select(SiteConfig))
        return {config.site_id: config for config in result.scalars().all()}
        
    async def _load_crawler_configs(self, db: AsyncSession) -> Dict[str, CrawlerConfig]:
        """加载所有爬虫配置"""
        result = await db.execute(select(CrawlerConfig))
        return {config.site_id: config for config in result.scalars().all()}
        
    async def _load_credentials(self, db: AsyncSession) -> Dict[str, CrawlerCredential]:
        """加载所有凭证配置"""
        result = await db.execute(select(CrawlerCredential))
        return {cred.site_id: cred for cred in result.scalars().all()}
        
    async def _load_browser_states(self, db: AsyncSession) -> Dict[str, BrowserState]:
        """加载所有浏览器状态"""
        result = await db.execute(select(BrowserState))
        return {state.site_id: state for state in result.scalars().all()}
            
    async def _load_local_site_setup(self, site_id: str) -> Optional[SiteSetup]:
        """从本地JSON文件加载站点配置
        
        Args:
            site_id: 站点ID
            
        Returns:
            Optional[SiteSetup]: 站点配置集合，如果未找到则返回None
        """
        try:
            config_dir = await settings.get_setting("crawler_config_path")
            self.logger.info(f"获取到crawler_config_path: {config_dir}")
            if not config_dir:
                self.logger.error("crawler_config_path 未找到")
                config_dir = os.path.join(os.path.dirname(__file__), "../..", "sites", "implementations")
                if os.path.exists(config_dir):
                    self.logger.info(f"使用默认 crawler_config_path: {config_dir}")
                else:
                    self.logger.error("默认 crawler_config_path 未找到")
                    return None
            
            if not os.path.exists(config_dir):
                self.logger.warning(f"站点目录未找到: {config_dir}")
                return None
                
            # 读取site_config.json
            site_config_path = os.path.join(config_dir, f"{site_id}.json")
            if not os.path.exists(site_config_path):
                self.logger.warning(f"{site_id}.json 未找到")
                return None
            else:
                with open(site_config_path, 'r', encoding='utf-8') as f:
                    site_config_data = json.load(f)
                self.logger.info(f"成功加载站点配置文件: {site_config_path}")
                
            # 读取crawler_credential.json
            credential_dir = await settings.get_setting("crawler_credential_path")
            credential_path = os.path.join(credential_dir, "credentials.json")
            credential_data = {}
            if os.path.exists(credential_path):
                with open(credential_path, 'r', encoding='utf-8') as f:
                    all_credentials = json.load(f)
                    # 优先使用站点特定凭证，如果没有则使用全局凭证
                    if site_id in all_credentials and all_credentials[site_id].get("enabled", True):
                        credential_data = all_credentials[site_id]
                        self.logger.info(f"{site_id} 使用站点特别凭证")
                    elif "global" in all_credentials and all_credentials["global"].get("enabled", True):
                        credential_data = all_credentials["global"]
                        self.logger.info(f"{site_id} 使用全局凭证")
                    else:
                        self.logger.warning(f"未找到站点可用凭证: {site_id}")
            else:
                self.logger.warning(f"Credentials file not found: {credential_path}")
                
            # 构造配置数据
            setup_data = {
                "site_id": site_id,
                "crawler": {
                    "site_id": site_id,
                    "is_logged_in": False
                },
                "site_config": {
                    "site_id": site_id,
                    "site_url": site_config_data.get("site_url", ""),
                    "login_config": site_config_data.get("login_config", {}),
                    "extract_rules": {"rules": site_config_data.get("extract_rules", [])},
                    "checkin_config": site_config_data.get("checkin_config", {})
                },
                "crawler_config": {
                    "site_id": site_id,
                    "enabled": True
                },
                "crawler_credential": {
                    "site_id": site_id,
                    "username": credential_data.get("username", ""),
                    "password": credential_data.get("password", ""),
                    "authorization": credential_data.get("authorization", ""),
                    "apikey": credential_data.get("apikey", ""),
                    "enabled": True,
                    "manual_cookies": credential_data.get("manual_cookies", "")
                },
                "browser_state": {
                    "site_id": site_id,
                    "cookies": {},
                    "local_storage": {},
                    "session_storage": {},
                }
            }
            
            # 使用 model_validate 直接创建 SiteSetup 实例
            site_setup = SiteSetup.model_validate(setup_data)
            self.logger.debug(f"成功创建站点配置: {site_id}")
            return site_setup
            
        except Exception as e:
            self.logger.error(f"从本地加载站点配置失败: {site_id}: {str(e)}")
            return None
            
    async def _persist_site_setup(self, db: AsyncSession, site_setup: SiteSetup) -> bool:
        """将站点配置永久化到数据库
        
        Args:
            db: 数据库会话
            site_setup: 站点配置
            
        Returns:
            bool: 是否成功
        """
        try:
            # 1. 首先检查并确保 crawler 记录存在
            stmt = select(Crawler).where(Crawler.site_id == site_setup.site_id)
            result = await db.execute(stmt)
            existing_crawler = result.scalar_one_or_none()
            
            if not existing_crawler:
                if site_setup.crawler:
                    db.add(site_setup.crawler)
                else:
                    # 如果没有提供 crawler，创建一个新的
                    crawler = Crawler(
                        site_id=site_setup.site_id,
                        is_logged_in=False,
                        total_tasks=0
                    )
                    db.add(crawler)
                # 确保 crawler 记录被创建
                await db.flush()
            elif site_setup.crawler:
                # 更新现有记录
                for key, value in site_setup.crawler.__dict__.items():
                    if not key.startswith('_'):
                        setattr(existing_crawler, key, value)
                await db.flush()
            
            # 2. 更新或插入其他配置
            if site_setup.site_config:
                db.add(site_setup.site_config)
            if site_setup.crawler_config:
                db.add(site_setup.crawler_config)
            if site_setup.crawler_credential:
                db.add(site_setup.crawler_credential)
            if site_setup.browser_state:
                db.add(site_setup.browser_state)
                
            # 3. 提交所有更改
            await db.commit()
            self.logger.info(f"保存站点配置到数据库成功: {site_setup.site_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存站点配置到数据库失败: {site_setup.site_id}: {str(e)}")
            await db.rollback()
            return False