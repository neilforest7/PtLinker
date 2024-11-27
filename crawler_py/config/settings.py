from pydantic_settings import BaseSettings
from typing import List, Optional
from pathlib import Path
import os
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

class Settings(BaseSettings):
    """应用配置"""
    
    # 项目基础路径
    BASE_DIR: Path = Path(__file__).parent.parent
    
    # Crawler Configuration
    CRAWLER_HEADLESS: bool = False
    CRAWLER_MAX_CONCURRENCY: int = 10
    
    # Browser Configuration
    BROWSER_PATH: str = os.getenv('BROWSER_PATH', r'C:/Users/Lukee/AppData/Local/pyppeteer/pyppeteer/local-chromium/1181205/chrome-win/chrome.exe')
    BROWSER_TIMEOUT: int = 30000
    BROWSER_VIEWPORT_WIDTH: int = 1280
    BROWSER_VIEWPORT_HEIGHT: int = 720
    
    # Captcha Configuration
    CAPTCHA_HANDLE_METHOD: str = "api"  # api, ocr, manual, skip
    CAPTCHA_API_KEY: Optional[str] = None
    CAPTCHA_API_URL: str = "http://api.2captcha.com"
    CAPTCHA_SKIP_SITES: List[str] = []
    
    # Login Credentials
    LOGIN_USERNAME: str
    LOGIN_PASSWORD: str
    
    # Storage Configuration
    STORAGE_DIR: Path = BASE_DIR / 'storage'
    DATASET_DIR: Path = STORAGE_DIR / 'datasets'
    KEY_VALUE_STORE_DIR: Path = STORAGE_DIR / 'key_value_stores'
    REQUEST_QUEUE_DIR: Path = STORAGE_DIR / 'request_queues'
    
    # Request Configuration
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    class Config:
        env_file = '.env'
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 确保存储目录存在
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.DATASET_DIR.mkdir(parents=True, exist_ok=True)
        self.KEY_VALUE_STORE_DIR.mkdir(parents=True, exist_ok=True)
        self.REQUEST_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        
        # 解析 CAPTCHA_SKIP_SITES
        if isinstance(self.CAPTCHA_SKIP_SITES, str):
            self.CAPTCHA_SKIP_SITES = self.CAPTCHA_SKIP_SITES.split(',')

# 创建全局设置实例
settings = Settings()