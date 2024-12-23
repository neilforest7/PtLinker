import os

from pydantic_settings import BaseSettings

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "ptlinker.db")
# 数据库URL
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

class DatabaseSettings(BaseSettings):
    """数据库连接配置"""
    DATABASE_URL: str = DATABASE_URL
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800  # 30分钟
    DB_ECHO: bool = False

    class Config:
        env_file = ".env"
        # 允许额外字段
        extra = "allow"  # 或者使用 "ignore" 忽略额外字段

database_settings = DatabaseSettings() 