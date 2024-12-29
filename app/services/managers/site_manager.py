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
from schemas.crawlerschemas import CrawlerBase, CrawlerCreate
from schemas.siteconfig import SiteConfigBase
from schemas.sitesetup import SiteSetup
from services.managers.setting_manager import SettingManager
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
            self.logger = get_logger(name=__name__, site_id="SiteMgr")
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
        config_dir = await SettingManager.get_instance().get_setting("crawler_config_path")
        if config_dir and Path(config_dir).exists():
            for site_conf in Path(config_dir).iterdir():
                if site_conf.is_dir() or site_conf.name.startswith('_'):
                    continue
                    
                site_id = site_conf.stem
                if site_id not in site_setups:
                    # 从本地加载配置
                    self.logger.info(f"从本地加载配置: {site_id}")
                    local_setup = await self._load_local_site_setup(site_id)
                    if local_setup and local_setup.is_valid():
                        site_setups[site_id] = local_setup
                        self.logger.info(f"从本地加载 {site_id} 配置到site_setups成功")
                        
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
                                new_crawler: Optional[CrawlerBase] = None,
                                new_site_config: Optional[SiteConfigBase] = None,
                                new_crawler_config: Optional[CrawlerConfigBase] = None,
                                new_crawler_credential: Optional[CrawlerCredentialBase] = None,
                                new_browser_state: Optional[BrowserStateBase] = None) -> bool:
        """更新站点配置"""
        try:
            self.logger.debug(f"开始更新站点配置: {site_id}")
            self.logger.debug(f"传入参数: new_crawler={new_crawler is not None}, "
                            f"new_site_config={new_site_config is not None}, "
                            f"new_crawler_config={new_crawler_config is not None}, "
                            f"new_crawler_credential={new_crawler_credential is not None}, "
                            f"new_browser_state={new_browser_state is not None}")
            
            # 检查 crawler 记录是否存在
            stmt = select(Crawler).where(Crawler.site_id == site_id)
            result = await db.execute(stmt)
            existing_crawler = result.scalar_one_or_none()
            self.logger.debug(f"现有crawler记录: {existing_crawler is not None}")
            
            if not existing_crawler and not new_crawler:
                # 如果不存在 crawler 记录且没有提供新的记录，创建一个新的
                new_crawler = CrawlerCreate(
                    site_id=site_id,
                    is_logged_in=False,
                    total_tasks=0
                )
                self.logger.debug(f"创建新的默认crawler记录: {new_crawler.model_dump()}")
            
            # 更新指定部分的新配置
            if new_crawler:
                if existing_crawler:
                    # 更新现有记录
                    crawler_data = new_crawler.model_dump()
                    self.logger.debug(f"更新现有crawler记录: {crawler_data}")
                    for key, value in crawler_data.items():
                        if not key.startswith('_'):
                            self.logger.debug(f"  设置crawler属性: {key} = {value}")
                            setattr(existing_crawler, key, value)
                else:
                    # 添加新记录
                    db_crawler = Crawler(**new_crawler.model_dump())
                    self.logger.debug(f"添加新crawler记录: {new_crawler.model_dump()}")
                    db.add(db_crawler)
                    existing_crawler = db_crawler
                
                # 确保站点在_sites字典中存在
                if site_id not in self._sites:
                    self.logger.debug(f"在_sites字典中创建新站点记录: {site_id}")
                    self._sites[site_id] = SiteSetup(site_id=site_id)
                
                self._sites[site_id].crawler = new_crawler
                self.logger.debug("更新内存中的crawler记录完成")
            
            # 确保先提交 crawler 记录
            await db.flush()
            self.logger.debug("提交crawler记录完成")
            
            if new_site_config:
                self.logger.debug("开始处理site_config")
                # 转换配置数据为字典
                site_config_data = new_site_config.model_dump()
                # 将需要JSON序列化的字段转换为字符串
                site_config_data['login_config'] = json.dumps(site_config_data.get('login_config'))
                site_config_data['extract_rules'] = json.dumps(site_config_data.get('extract_rules'))
                site_config_data['checkin_config'] = json.dumps(site_config_data.get('checkin_config'))
                self.logger.debug("JSON序列化完成")
                
                # 检查是否存在现有配置
                stmt = select(SiteConfig).where(SiteConfig.site_id == site_id)
                result = await db.execute(stmt)
                existing_site_config = result.scalar_one_or_none()
                self.logger.debug(f"现有site_config记录: {existing_site_config is not None}")
                
                if existing_site_config:
                    # 更新现有记录
                    for key, value in site_config_data.items():
                        if not key.startswith('_'):
                            self.logger.debug(f"- 设置site_config属性: {key} = {value[:100] if isinstance(value, str) else value}...")
                            setattr(existing_site_config, key, value)
                else:
                    # 添加新记录
                    self.logger.debug("添加新site_config记录")
                    db_site_config = SiteConfig(**site_config_data)
                    db.add(db_site_config)
                
                # 确保站点在_sites字典中存在
                if site_id not in self._sites:
                    self.logger.debug(f"在_sites字典中创建新站点记录: {site_id}")
                    self._sites[site_id] = SiteSetup(site_id=site_id)
                
                self._sites[site_id].site_config = new_site_config
                self.logger.debug("更新内存中的site_config记录完成")
                    
            if new_crawler_config:
                self.logger.debug("开始处理crawler_config")
                # 检查是否存在现有配置
                stmt = select(CrawlerConfig).where(CrawlerConfig.site_id == site_id)
                result = await db.execute(stmt)
                existing_crawler_config = result.scalar_one_or_none()
                self.logger.debug(f"现有crawler_config记录: {existing_crawler_config is not None}")
                
                if existing_crawler_config:
                    # 更新现有记录
                    crawler_config_data = new_crawler_config.model_dump()
                    self.logger.debug(f"更新现有crawler_config记录: {crawler_config_data}")
                    for key, value in crawler_config_data.items():
                        if not key.startswith('_'):
                            self.logger.debug(f"- 设置crawler_config属性: {key} = {value}")
                            setattr(existing_crawler_config, key, value)
                else:
                    # 添加新记录
                    self.logger.debug("添加新crawler_config记录")
                    db_crawler_config = CrawlerConfig(**new_crawler_config.model_dump())
                    db.add(db_crawler_config)
                
                # 确保站点在_sites字典中存在
                if site_id not in self._sites:
                    self.logger.debug(f"在_sites字典中创建新站点记录: {site_id}")
                    self._sites[site_id] = SiteSetup(site_id=site_id)
                
                self._sites[site_id].crawler_config = new_crawler_config
                self.logger.debug("更新内存中的crawler_config记录完成")

            if new_crawler_credential:
                self.logger.debug("开始处理crawler_credential")
                # 检查是否存在现有配置
                stmt = select(CrawlerCredential).where(CrawlerCredential.site_id == site_id)
                result = await db.execute(stmt)
                existing_crawler_credential = result.scalar_one_or_none()
                self.logger.debug(f"现有crawler_credential记录: {existing_crawler_credential is not None}")
                
                if existing_crawler_credential:
                    # 更新现有记录
                    crawler_credential_data = new_crawler_credential.model_dump()
                    self.logger.debug("更新现有crawler_credential记录")
                    for key, value in crawler_credential_data.items():
                        if not key.startswith('_'):
                            self.logger.debug(f"- 设置crawler_credential属性: {key} = {'***' if key in ['password', 'apikey'] else value}")
                            setattr(existing_crawler_credential, key, value)
                else:
                    # 添加新记录
                    self.logger.debug("添加新crawler_credential记录")
                    db_crawler_credential = CrawlerCredential(**new_crawler_credential.model_dump())
                    db.add(db_crawler_credential)
                
                # 确保站点在_sites字典中存在
                if site_id not in self._sites:
                    self.logger.debug(f"在_sites字典中创建新站点记录: {site_id}")
                    self._sites[site_id] = SiteSetup(site_id=site_id)
                
                self._sites[site_id].crawler_credential = new_crawler_credential
                self.logger.debug("更新内存中的crawler_credential记录完成")

            if new_browser_state:
                self.logger.debug("开始处理browser_state")
                # 检查是否存在现有配置
                stmt = select(BrowserState).where(BrowserState.site_id == site_id)
                result = await db.execute(stmt)
                existing_browser_state = result.scalar_one_or_none()
                self.logger.debug(f"现有browser_state记录: {existing_browser_state is not None}")
                
                if existing_browser_state:
                    # 更新现有记录
                    browser_state_data = new_browser_state.model_dump()
                    self.logger.debug("更新现有browser_state记录")
                    for key, value in browser_state_data.items():
                        if not key.startswith('_'):
                            self.logger.debug(f"- 设置browser_state属性: {key} = {value}")
                            setattr(existing_browser_state, key, value)
                else:
                    # 添加新记录
                    self.logger.debug("添加新browser_state记录")
                    db_browser_state = BrowserState(**new_browser_state.model_dump())
                    db.add(db_browser_state)
                
                # 确保站点在_sites字典中存在
                if site_id not in self._sites:
                    self.logger.debug(f"在_sites字典中创建新站点记录: {site_id}")
                    self._sites[site_id] = SiteSetup(site_id=site_id)
                
                self._sites[site_id].browser_state = new_browser_state
                self.logger.debug("更新内存中的browser_state记录完成")
                    
            # 提交所有更改
            self.logger.debug("开始提交所有更改")
            await db.commit()
            self.logger.info(f"更新站点配置成功: {site_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"更新站点配置失败 {site_id}: {str(e)}")
            self.logger.debug(f"错误详情: ", exc_info=True)
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
    
    async def load_local_site_setups(self) -> Dict[str, SiteSetup]:
        """从本地JSON文件加载所有站点配置"""
        try:
            site_setups = {}
            config_dir = await SettingManager.get_instance().get_setting("crawler_config_path")
            
            if config_dir and Path(config_dir).exists():
                for config_file in Path(config_dir).iterdir():
                    if config_file.is_dir() or config_file.name.startswith('_'):
                        continue
                        
                    site_id = config_file.stem
                    site_setup = await self._load_local_site_setup(site_id)
                    if site_setup and site_setup.is_valid():
                        site_setups[site_id] = site_setup
                        
            return site_setups
        except Exception as e:
            self.logger.error(f"从本地加载站点配置失败: {str(e)}")
            return {}
        
    async def _load_local_site_setup(self, site_id: str) -> Optional[SiteSetup]:
        """从本地JSON文件加载站点配置
        
        Args:
            site_id: 站点ID
            
        Returns:
            Optional[SiteSetup]: 站点配置集合，如果未找到则返回None
        """
        try:
            # 1. 获取配置目录
            config_dir = await SettingManager.get_instance().get_setting("crawler_config_path")
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
            
            # 2. 读取站点配置文件
            site_config_path = os.path.join(config_dir, f"{site_id}.json")
            if not os.path.exists(site_config_path):
                self.logger.warning(f"{site_id}.json 未找到")
                return None
            
            with open(site_config_path, 'r', encoding='utf-8') as f:
                site_config_data = json.load(f)
            self.logger.info(f"加载站点配置文件: {site_config_path}")

            # 3. 读取凭证配置
            credential_dir = await SettingManager.get_instance().get_setting("crawler_credential_path")
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
                    "is_logged_in": False,
                    "total_tasks": 0
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
                    "enabled": True,
                    "use_proxy": False,
                    "fresh_login": False,
                    "captcha_skip": False,
                    "headless": True
                },
                "crawler_credential": {
                    "site_id": site_id,
                    "username": credential_data.get("username", ""),
                    "password": credential_data.get("password", ""),
                    "authorization": credential_data.get("authorization", ""),
                    "apikey": credential_data.get("apikey", ""),
                    "enable_manual_cookies": bool(credential_data.get("manual_cookies")),
                    "manual_cookies": credential_data.get("manual_cookies", "")
                }
            }
            
            # 5. 验证并创建 SiteSetup 实例
            site_setup = SiteSetup.model_validate(setup_data)
            if not site_setup.site_config or not site_setup.site_config.site_url:
                self.logger.error(f"站点 {site_id} 配置无效：缺少必要的站点URL")
                return None
            
            self.logger.info(f"成功加载本地配置: {site_id}")
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
                    # 创建新的 Crawler 记录
                    crawler_data = site_setup.crawler.model_dump()
                    db_crawler = Crawler(**crawler_data)
                    db.add(db_crawler)
                else:
                    # 如果没有提供 crawler，创建一个新的
                    db_crawler = Crawler(
                        site_id=site_setup.site_id,
                        is_logged_in=False,
                        total_tasks=0
                    )
                    db.add(db_crawler)
                # 确保 crawler 记录被创建
                await db.flush()
            elif site_setup.crawler:
                # 更新现有记录
                crawler_data = site_setup.crawler.model_dump()
                for key, value in crawler_data.items():
                    if not key.startswith('_'):
                        setattr(existing_crawler, key, value)
                await db.flush()
            
            # 2. 更新或插入其他配置
            if site_setup.site_config:
                # 检查是否存在现有配置
                stmt = select(SiteConfig).where(SiteConfig.site_id == site_setup.site_id)
                result = await db.execute(stmt)
                existing_site_config = result.scalar_one_or_none()
                
                # 转换配置数据
                site_config_data = site_setup.site_config.model_dump()
                site_config_data['login_config'] = json.dumps(site_config_data.get('login_config', {}))
                site_config_data['extract_rules'] = json.dumps(site_config_data.get('extract_rules', {}))
                site_config_data['checkin_config'] = json.dumps(site_config_data.get('checkin_config', {}))
                
                if existing_site_config:
                    # 更新现有记录
                    for key, value in site_config_data.items():
                        if not key.startswith('_'):
                            setattr(existing_site_config, key, value)
                else:
                    # 创建新记录
                    db_site_config = SiteConfig(**site_config_data)
                    db.add(db_site_config)
                
            if site_setup.crawler_config:
                # 检查是否存在现有配置
                stmt = select(CrawlerConfig).where(CrawlerConfig.site_id == site_setup.site_id)
                result = await db.execute(stmt)
                existing_crawler_config = result.scalar_one_or_none()
                
                crawler_config_data = site_setup.crawler_config.model_dump()
                if existing_crawler_config:
                    # 更新现有记录
                    for key, value in crawler_config_data.items():
                        if not key.startswith('_'):
                            setattr(existing_crawler_config, key, value)
                else:
                    # 创建新记录
                    db_crawler_config = CrawlerConfig(**crawler_config_data)
                    db.add(db_crawler_config)
                
            if site_setup.crawler_credential:
                # 检查是否存在现有配置
                stmt = select(CrawlerCredential).where(CrawlerCredential.site_id == site_setup.site_id)
                result = await db.execute(stmt)
                existing_crawler_credential = result.scalar_one_or_none()
                
                credential_data = site_setup.crawler_credential.model_dump()
                if existing_crawler_credential:
                    # 更新现有记录
                    for key, value in credential_data.items():
                        if not key.startswith('_'):
                            setattr(existing_crawler_credential, key, value)
                else:
                    # 创建新记录
                    db_crawler_credential = CrawlerCredential(**credential_data)
                    db.add(db_crawler_credential)
                
            if site_setup.browser_state:
                # 检查是否存在现有配置
                stmt = select(BrowserState).where(BrowserState.site_id == site_setup.site_id)
                result = await db.execute(stmt)
                existing_browser_state = result.scalar_one_or_none()
                
                browser_state_data = site_setup.browser_state.model_dump()
                if existing_browser_state:
                    # 更新现有记录
                    for key, value in browser_state_data.items():
                        if not key.startswith('_'):
                            setattr(existing_browser_state, key, value)
                else:
                    # 创建新记录
                    db_browser_state = BrowserState(**browser_state_data)
                    db.add(db_browser_state)
                
            # 3. 提交所有更改
            await db.commit()
            self.logger.info(f"保存站点配置到数据库成功: {site_setup.site_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存站点配置到数据库失败: {site_setup.site_id}: {str(e)}")
            await db.rollback()
            return False
            
    async def delete_site_setup(self, db: AsyncSession, site_id: str) -> bool:
        """删除站点配置
        
        Args:
            db: 数据库会话
            site_id: 站点ID
            
        Returns:
            bool: 是否成功
        """
        try:
            self.logger.debug(f"开始删除站点配置: {site_id}")
            
            # 1. 检查站点是否存在
            stmt = select(Crawler).where(Crawler.site_id == site_id)
            result = await db.execute(stmt)
            existing_crawler = result.scalar_one_or_none()
            
            if not existing_crawler:
                self.logger.warning(f"站点不存在: {site_id}")
                return False
                
            # 2. 删除相关配置记录
            # 注意：由于外键约束，删除 crawler 记录会自动删除相关的配置记录
            self.logger.debug(f"删除站点 {site_id} 的 crawler 记录")
            await db.delete(existing_crawler)
            
            # 3. 从内存中移除
            if site_id in self._sites:
                self.logger.debug(f"从内存中移除站点配置: {site_id}")
                del self._sites[site_id]
            
            # 4. 提交更改
            await db.commit()
            self.logger.info(f"成功删除站点配置: {site_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除站点配置失败 {site_id}: {str(e)}")
            self.logger.debug(f"错误详情: ", exc_info=True)
            await db.rollback()
            return False