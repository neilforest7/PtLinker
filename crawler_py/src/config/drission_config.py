import os
from typing import Dict, List
from pydantic import BaseModel


class BrowserConfig(BaseModel):
    """浏览器配置"""
    # 是否使用无头模式
    headless: bool = True
    # 页面加载超时时间(秒)
    timeout: int = 20
    # 下载路径
    download_path: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'downloads')
    # 浏览器启动参数
    browser_args: List[str] = [
        '--disable-gpu',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-software-rasterizer',
        '--disable-extensions',
    ]
    # 是否使用新环境
    new_env: bool = True
    # 是否启用stealth.min.js
    stealth: bool = True
    # 是否自动关闭无用窗口
    auto_close_pages: bool = True


class SessionConfig(BaseModel):
    """请求会话配置"""
    # 请求超时时间(秒)
    timeout: int = 20
    # 是否验证SSL证书
    verify: bool = False
    # 重试次数
    retry_times: int = 3
    # 重试间隔(秒)
    retry_interval: float = 1.0
    # 默认请求头
    headers: Dict[str, str] = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }


class DrissionConfig(BaseModel):
    """DrissionPage总配置"""
    browser: BrowserConfig = BrowserConfig()
    session: SessionConfig = SessionConfig()
    
    @classmethod
    def load_from_env(cls) -> 'DrissionConfig':
        """从环境变量加载配置"""
        browser_config = BrowserConfig(
            headless=os.getenv('HEADLESS', 'true').lower() == 'true',
            timeout=int(os.getenv('PAGE_TIMEOUT', '20')),
            new_env=os.getenv('NEW_ENV', 'true').lower() == 'true',
        )
        
        session_config = SessionConfig(
            timeout=int(os.getenv('REQUEST_TIMEOUT', '20')),
            verify=os.getenv('VERIFY_SSL', 'false').lower() == 'true',
            retry_times=int(os.getenv('RETRY_TIMES', '3')),
        )
        
        return cls(
            browser=browser_config,
            session=session_config,
        )
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'browser_configs': self.browser.model_dump(),
            'session_configs': self.session.model_dump(),
        }

# 默认配置实例
default_config = DrissionConfig() 