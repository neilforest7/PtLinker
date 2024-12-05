from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import os

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "PtLinker"
    DEBUG: bool = True
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./ptlinker.db"  # 默认使用SQLite
    
    # 爬虫配置
    CRAWLER_CONFIG_PATH: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..", "crawler_py/src/crawlers/site_config"))
    CRAWLER_STORAGE_PATH: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..", "crawler_py/storage"))
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings() 