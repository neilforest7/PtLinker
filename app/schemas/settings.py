from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class SettingsBase(BaseModel):
    """基础配置模型"""
    # 核心配置
    crawler_config_path: str = Field(default="services/sites/implementations", description="爬虫配置路径")
    crawler_credential_path: str = Field(default="services/sites/credentials", description="爬虫凭证路径")
    crawler_storage_path: str = Field(default="storage", description="爬虫存储路径")
    
    # 爬虫基础配置
    crawler_max_concurrency: int = Field(default=8, description="爬虫最大并发数")
    fresh_login: bool = Field(default=False, description="是否强制重新登录")
    login_max_retry: int = Field(default=3, description="登录最大重试次数")
    
    # 验证码配置
    captcha_default_method: str = Field(default="api", description="验证码处理方法")
    captcha_skip_sites: str = Field(default="", description="跳过验证码的站点")
    captcha_api_key: Optional[str] = Field(default=None, description="验证码API密钥")
    captcha_api_url: Optional[str] = Field(default=None, description="验证码API地址")
    captcha_max_retries: int = Field(default=10, description="验证码最大重试次数")
    captcha_poll_interval: float = Field(default=3.0, description="验证码轮询间隔")
    captcha_timeout: int = Field(default=60, description="验证码超时时间")
    
    # 浏览器配置
    browser_viewport_width: int = Field(default=1920, description="浏览器视窗宽度")
    browser_viewport_height: int = Field(default=1080, description="浏览器视窗高度")
    chrome_path: Optional[str] = Field(default=None, description="Chrome浏览器路径")
    driver_path: Optional[str] = Field(default=None, description="驱动路径")
    headless: bool = Field(default=True, description="是否使用无头模式")
    page_timeout: float = Field(default=20.0, description="页面超时时间")
    navigation_timeout: int = Field(default=60, description="导航超时时间")
    
    # 请求配置
    request_timeout: float = Field(default=20.0, description="请求超时时间")
    verify_ssl: bool = Field(default=False, description="是否验证SSL证书")
    retry_times: int = Field(default=3, description="请求重试次数")
    
    # 日志配置
    log_level: str = Field(default="DEBUG", description="日志级别")
    console_log_level: str = Field(default="INFO", description="控制台日志级别")
    file_log_level: str = Field(default="DEBUG", description="文件日志级别")
    error_log_level: str = Field(default="ERROR", description="错误日志级别")
    log_file: str = Field(default="task_{time:YYMMDD-HHMM}.log", description="日志文件名")
    error_log_file: str = Field(default="task_error_{time:YYMMDD-HHMM}.log", description="错误日志文件名")
    
    # 存储配置
    storage_path: str = Field(default="storage", description="存储路径")
    captcha_storage_path: str = Field(default="storage/captcha", description="验证码存储路径")
    
    # 签到配置
    enable_checkin: bool = Field(default=True, description="是否启用签到")
    checkin_sites: str = Field(default="", description="需要签到的站点列表")

    @property
    def captcha_skip_sites_list(self) -> List[str]:
        """获取跳过验证码的站点列表"""
        if not self.captcha_skip_sites:
            return []
        return [site.strip() for site in self.captcha_skip_sites.split(",") if site.strip()]

    @property
    def checkin_sites_list(self) -> List[str]:
        """获取需要签到的站点列表"""
        if not self.checkin_sites:
            return []
        return [site.strip() for site in self.checkin_sites.split(",") if site.strip()]


class SettingsCreate(SettingsBase):
    """创建配置模型"""
    created_at: datetime
    pass


class SettingsUpdate(BaseModel):
    """更新配置模型"""
    updated_at: datetime
    
    crawler_config_path: Optional[str] = None
    crawler_storage_path: Optional[str] = None
    crawler_max_concurrency: Optional[int] = None
    fresh_login: Optional[bool] = None
    login_max_retry_count: Optional[int] = None
    captcha_default_method: Optional[str] = None
    captcha_skip_sites: Optional[str] = None
    captcha_api_key: Optional[str] = None
    captcha_api_url: Optional[str] = None
    captcha_max_retries: Optional[int] = None
    captcha_poll_interval: Optional[float] = None
    captcha_timeout: Optional[int] = None
    browser_viewport_width: Optional[int] = None
    browser_viewport_height: Optional[int] = None
    chrome_path: Optional[str] = None
    driver_path: Optional[str] = None
    headless: Optional[bool] = None
    page_timeout: Optional[float] = None
    navigation_timeout: Optional[int] = None
    request_timeout: Optional[float] = None
    verify_ssl: Optional[bool] = None
    retry_times: Optional[int] = None
    log_level: Optional[str] = None
    console_log_level: Optional[str] = None
    file_log_level: Optional[str] = None
    error_log_level: Optional[str] = None
    log_file: Optional[str] = None
    error_log_file: Optional[str] = None
    storage_path: Optional[str] = None
    captcha_storage_path: Optional[str] = None
    enable_checkin: Optional[bool] = None
    checkin_sites: Optional[str] = None


class SettingsResponse(SettingsBase):
    """配置响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True