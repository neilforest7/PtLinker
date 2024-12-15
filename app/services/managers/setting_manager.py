import os
from pathlib import Path
from typing import Any, Dict, Optional

from core.logger import get_logger, setup_logger
from dotenv import load_dotenv
from models.settings import Settings as DBSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 加载.env文件
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

class SettingManager:
    """设置管理器"""
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not SettingManager._initialized:
            self._settings: Optional[DBSettings] = None
            self._cache: Dict[str, Any] = {}
            SettingManager._initialized = True
            # setup_logger()
            self.logger = get_logger(name=__name__, site_id="settingmanager")
            
    def _get_env_value(self, key: str) -> Any:
        """从环境变量获取配置值"""
        value = os.getenv(key.upper())
        if value is None:
            return None
            
        if key.upper() in ['CAPTCHA_SKIP_SITES', 'CHECKIN_SITES']:
            return value
        
        # 转换布尔值
        if value.lower() in ['true', 'false']:
            return value.lower() == 'true'
        
        # 转换整数
        try:
            return int(value)
        except ValueError:
            pass
            
        return value
    
    async def initialize(self, db: AsyncSession) -> None:
        """初始化设置管理器"""
        try:
            # 获取最新的配置
            stmt = select(DBSettings).order_by(DBSettings.updated_at.desc()).limit(1)
            result = await db.execute(stmt)
            settings = result.scalar_one_or_none()
            
            if not settings:
                # 如果没有配置，创建默认配置
                settings = DBSettings()
                
            # 获取所有可配置的字段
            settable_fields = [
                column.key for column in DBSettings.__table__.columns
                if not column.key.startswith('_')
            ]
            
            # 遍历所有字段，检查空值并从环境变量补充
            added_fields = 0
            
            for field in settable_fields:
                current_value = getattr(settings, field, None)
                if current_value is None or current_value == '':
                    env_value = self._get_env_value(field)
                    if env_value is not None:
                        setattr(settings, field, env_value)
                        added_fields += 1
                        self.logger.info(f"Setting {field} loaded from .env: {env_value}")
            
            # if not settings.id:
            # 如果是新创建的配置，保存到数据库
            db.add(settings)
            await db.commit()
            if added_fields > 0:
                self.logger.info(f"Created new settings with {added_fields} values from .env")
            else:
                self.logger.info("No new settings created from .env")
            
            self._settings = settings
            # 清空缓存
            self._cache.clear()
            self.logger.info("Settings initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize settings: {str(e)}", exc_info=True)
            raise
    
    async def get_setting(self, key: str) -> Any:
        """获取配置值"""
        # 先从缓存获取
        if key in self._cache:
            return self._cache[key]
            
        if not self._settings:
            raise RuntimeError("Settings not initialized. Call initialize() first.")
            
        # 从数据库配置获取
        value = getattr(self._settings, key, None)
        if value is not None:
            self._cache[key] = value
            
        return value
    
    async def set_setting(self, db: AsyncSession, key: str, value: Any) -> None:
        """设置配置值"""
        if not self._settings:
            raise RuntimeError("Settings not initialized. Call initialize() first.")
            
        try:
            # 检查属性是否存在
            if not hasattr(self._settings, key):
                raise ValueError(f"Invalid setting key: {key}")
                
            # 设置新值
            setattr(self._settings, key, value)
            await db.commit()
            
            # 更新缓存
            self._cache[key] = value
            self.logger.info(f"Setting updated: {key} = {value}")
            
        except Exception as e:
            await db.rollback()
            self.logger.error(f"Failed to update setting: {str(e)}", exc_info=True)
            raise
    
    async def get_all_settings(self) -> Dict[str, Any]:
        """获取所有配置"""
        if not self._settings:
            raise RuntimeError("Settings not initialized. Call initialize() first.")
            
        return {
            column.key: getattr(self._settings, column.key)
            for column in self._settings.__table__.columns
            if not column.key.startswith('_')
        }
    
    async def update_settings(self, db: AsyncSession, settings: Dict[str, Any]) -> None:
        """批量更新配置"""
        if not self._settings:
            raise RuntimeError("Settings not initialized. Call initialize() first.")
            
        try:
            for key, value in settings.items():
                if hasattr(self._settings, key):
                    setattr(self._settings, key, value)
                    self._cache[key] = value
                    
            await db.commit()
            self.logger.info("Settings updated successfully")
            
        except Exception as e:
            await db.rollback()
            self.logger.error(f"Failed to update settings: {str(e)}", exc_info=True)
            raise
    
    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache.clear()
        self.logger.debug("Settings cache cleared")

    # 便捷属性访问方法
    @property
    def crawler_max_concurrency(self) -> int:
        """获取爬虫最大并发数"""
        return self._settings.crawler_max_concurrency if self._settings else 15

    @property
    def fresh_login(self) -> bool:
        """获取是否强制重新登录"""
        return self._settings.fresh_login if self._settings else False

    @property
    def chrome_path(self) -> Optional[str]:
        """获取Chrome浏览器路径"""
        return self._settings.chrome_path if self._settings else None

    @property
    def headless(self) -> bool:
        """获取是否使用无头模式"""
        return self._settings.headless if self._settings else True

    @property
    def log_level(self) -> str:
        """获取日志级别"""
        return self._settings.log_level if self._settings else "DEBUG"

    @property
    def enable_checkin(self) -> bool:
        """获取是否启用签到"""
        return self._settings.enable_checkin if self._settings else True


# 全局设置管理器实例
settings = SettingManager()