from pydantic_settings import BaseSettings
from typing import List, Optional, Dict
from pathlib import Path
import os

class Settings(BaseSettings):
    """应用配置"""
    
    # 项目基础路径
    BASE_DIR: Path = Path(__file__).parent.parent
    
    # Crawler Configuration
    CRAWLER_HEADLESS: bool = False
    CRAWLER_MAX_CONCURRENCY: int = 10
    FRESH_LOGIN: bool = os.getenv('FRESH_LOGIN', 'false').lower() == 'true'
    
    # Browser Configuration
    BROWSER_PATH: str = os.getenv('CHROME_PATH', r'C:/Users/Lukee/AppData/Local/pyppeteer/pyppeteer/local-chromium/1181205/chrome-win/chrome.exe')
    BROWSER_TIMEOUT: int = int(os.getenv('PAGE_TIMEOUT', '30000'))
    BROWSER_VIEWPORT_WIDTH: int = int(os.getenv('BROWSER_VIEWPORT_WIDTH', '1280'))
    BROWSER_VIEWPORT_HEIGHT: int = int(os.getenv('BROWSER_VIEWPORT_HEIGHT', '720'))
    
    # Captcha Configuration
    CAPTCHA_HANDLE_METHOD: str = os.getenv('CAPTCHA_DEFAULT_METHOD', 'api')
    CAPTCHA_API_KEY: str = os.getenv('CAPTCHA_API_KEY', '')
    CAPTCHA_API_URL: str = os.getenv('CAPTCHA_API_URL', 'http://api.2captcha.com')
    CAPTCHA_SKIP_SITES: str = os.getenv('CAPTCHA_SKIP_SITES', '')
    CAPTCHA_MAX_RETRIES: int = int(os.getenv('CAPTCHA_MAX_RETRIES', '10'))
    CAPTCHA_POLL_INTERVAL: float = float(os.getenv('CAPTCHA_POLL_INTERVAL', '3.0'))
    CAPTCHA_TIMEOUT: int = int(os.getenv('CAPTCHA_TIMEOUT', '120'))
    
    # Login Credentials
    LOGIN_USERNAME: str = os.getenv('LOGIN_USERNAME', '')
    LOGIN_PASSWORD: str = os.getenv('LOGIN_PASSWORD', '')
    
    # Storage Configuration
    STORAGE_DIR: Path = BASE_DIR / os.getenv('STORAGE_PATH', 'storage')
    CAPTCHA_STORAGE_DIR: Path = STORAGE_DIR / 'captcha'

    
    # Request Configuration
    DEFAULT_HEADERS: Dict[str, str] = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    model_config = {
        'env_file': '.env',
        'env_file_encoding': 'utf-8',
        'case_sensitive': True,
        'extra': 'allow'
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 确保存储目录存在
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.CAPTCHA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        
        # 处理 CAPTCHA_SKIP_SITES
        if self.CAPTCHA_SKIP_SITES:
            self._skip_sites = [site.strip() for site in self.CAPTCHA_SKIP_SITES.split(',') if site.strip()]
        else:
            self._skip_sites = []
    
    @property
    def skip_sites(self) -> List[str]:
        return self._skip_sites

# 创建全局设置实例
settings = Settings()