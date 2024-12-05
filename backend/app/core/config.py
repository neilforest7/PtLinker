import os
from pydantic_settings import BaseSettings
from pathlib import Path
from functools import lru_cache
from app.core.logger import get_logger

logger = get_logger(service="config")

class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./ptlinker.db"
    
    # 爬虫配置
    CRAWLER_CONFIG_PATH: Path = Path(os.path.join(os.path.dirname(__file__), "../../..", "crawler_py/src/crawlers/site_config"))
    CRAWLER_STORAGE_PATH: Path = Path(os.path.join(os.path.dirname(__file__), "../../..", "crawler_py/storage"))
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_PATH: Path = Path("logs")
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    """获取应用配置"""
    try:
        settings = Settings()
        logger.info("Application settings loaded")
        logger.debug(f"Database URL: {settings.DATABASE_URL}")
        logger.debug(f"Crawler config path: {settings.CRAWLER_CONFIG_PATH}")
        logger.debug(f"Crawler storage path: {settings.CRAWLER_STORAGE_PATH}")
        return settings
    except Exception as e:
        logger.error(f"Failed to load settings: {str(e)}", exc_info=True)
        raise 