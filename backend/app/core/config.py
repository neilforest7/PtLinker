from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # 基本配置
    PROJECT_NAME: str = "Web Crawler System"
    VERSION: str = "1.0.0"
    
    # API 配置
    API_V1_STR: str = "/api/v1"
    
    # 爬虫配置
    MAX_CONCURRENT_TASKS: int = 5
    RETRY_TIMES: int = 3
    REQUEST_TIMEOUT: int = 30
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings() 