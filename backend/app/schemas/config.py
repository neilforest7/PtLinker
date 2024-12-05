from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class CrawlerConfig(BaseModel):
    # 爬虫基础配置
    crawler_max_concurrency: int = Field(default=15, description="爬虫最大并发数")
    fresh_login: bool = Field(default=False, description="是否强制重新登录")
    login_max_retry_count: int = Field(default=3, description="登录最大重试次数")
    
    # 验证码配置
    captcha_default_method: str = Field(default="api", description="验证码处理方法")
    captcha_skip_sites: List[str] = Field(default=[], description="跳过验证码的站点")
    captcha_api_key: Optional[str] = Field(default=None, description="验证码API密钥")
    captcha_api_url: Optional[str] = Field(default=None, description="验证码API地址")
    captcha_max_retries: int = Field(default=10, description="验证码最大重试次数")
    captcha_poll_interval: float = Field(default=3.0, description="验证码轮询间隔")
    captcha_timeout: int = Field(default=120, description="验证码超时时间")
    
    # 浏览器配置
    browser_viewport_width: int = Field(default=1920, description="浏览器视窗宽度")
    browser_viewport_height: int = Field(default=1080, description="浏览器视窗高度")
    chrome_path: Optional[str] = Field(default=None, description="Chrome浏览器路径")
    headless: bool = Field(default=True, description="是否使用无头模式")
    page_timeout: int = Field(default=20, description="页面超时时间")
    
    # 请求配置
    request_timeout: int = Field(default=20, description="请求超时时间")
    verify_ssl: bool = Field(default=False, description="是否验证SSL证书")
    retry_times: int = Field(default=3, description="请求重试次数")
    
    # 日志配置
    log_level: str = Field(default="DEBUG", description="日志级别")
    console_log_level: str = Field(default="INFO", description="控制台日志级别")
    file_log_level: str = Field(default="DEBUG", description="文件日志级别")
    error_log_level: str = Field(default="ERROR", description="错误日志级别")
    
    # 签到配置
    enable_checkin: bool = Field(default=True, description="是否启用签到")
    checkin_sites: List[str] = Field(default=[], description="需要签到的站点列表")

    class Config:
        json_schema_extra = {
            "example": {
                "crawler_max_concurrency": 15,
                "fresh_login": False,
                "captcha_default_method": "api",
                "captcha_skip_sites": ["hdhome", "ourbits"],
                "enable_checkin": True,
                "checkin_sites": ["ubits", "hdhome"]
            }
        }

class ConfigUpdateResponse(BaseModel):
    success: bool
    message: str
    updated_fields: Dict[str, Any] 