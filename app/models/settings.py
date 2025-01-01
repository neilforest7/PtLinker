from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (JSON, Boolean, CheckConstraint, Column, DateTime,
                        Float, ForeignKey, Index, Integer, String, Text)
from core.database import Base


class Settings(Base):
    """系统设置数据库模型"""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now(), nullable=False)
    
    # 核心配置
    crawler_config_path = Column(String(500), default="services/sites/implementations", nullable=False, comment="爬虫配置路径")
    crawler_credential_path = Column(String(500), default="services/sites/credentials", nullable=False, comment="爬虫凭证路径")
    crawler_storage_path = Column(String(500), default="storage", nullable=False, comment="爬虫存储路径")
    

    # 爬虫基础配置
    crawler_max_concurrency = Column(Integer, default=8, comment="爬虫最大并发数")
    fresh_login = Column(Boolean, default=False, nullable=False, comment="是否强制重新登录")
    login_max_retry = Column(Integer, default=3, nullable=False, comment="登录最大重试次数")
    
    # 验证码配置
    captcha_default_method = Column(String(50), default="api", comment="验证码处理方法")
    captcha_skip_sites = Column(String, default="", comment="跳过验证码的站点")  # 使用逗号分隔的字符串
    captcha_api_key = Column(String(200), comment="验证码API密钥")
    captcha_api_url = Column(String(500), comment="验证码API地址")
    captcha_max_retries = Column(Integer, default=10, comment="验证码最大重试次数")
    captcha_poll_interval = Column(Float, default=3.0, comment="验证码轮询间隔")
    captcha_timeout = Column(Integer, default=60, comment="验证码超时时间")
    captcha_storage_path = Column(String(200), default="storage/captcha", comment="验证码存储路径")
    
    # 浏览器配置
    browser_viewport_width = Column(Integer, default=1920, comment="浏览器视窗宽度")
    browser_viewport_height = Column(Integer, default=1080, comment="浏览器视窗高度")
    chrome_path = Column(String(500), comment="Chrome浏览器路径")
    driver_path = Column(String(500), comment="驱动路径")
    headless = Column(Boolean, default=True, nullable=False, comment="是否使用无头模式")
    page_timeout = Column(Float, default=20, comment="页面超时时间")
    navigation_timeout = Column(Integer, default=60, comment="导航超时时间")
    
    # 请求配置
    request_timeout = Column(Float, default=20, comment="请求超时时间")
    verify_ssl = Column(Boolean, default=False, comment="是否验证SSL证书")
    retry_times = Column(Integer, default=3, comment="请求重试次数")
    
    # 日志配置
    log_level = Column(String(20), default="DEBUG", comment="日志级别")
    console_log_level = Column(String(20), default="INFO", comment="控制台日志级别")
    file_log_level = Column(String(20), default="DEBUG", comment="文件日志级别")
    error_log_level = Column(String(20), default="ERROR", comment="错误日志级别")
    log_file = Column(String(200), default="task_{time:YYMMDD-HHMM}.log", comment="日志文件名")
    error_log_file = Column(String(200), default="task_error_{time:YYMMDD-HHMM}.log", comment="错误日志文件名")
    
    # 存储配置
    storage_path = Column(String(200), default="storage", comment="存储路径")
    
    # 签到配置
    enable_checkin = Column(Boolean, default=True, nullable=False, comment="是否启用签到")
    checkin_sites = Column(String, default="", comment="需要签到的站点列表")  # 使用逗号分隔的字符串

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

    def __repr__(self) -> str:
        return f"<Settings(id={self.id})(updated_at={self.updated_at})>"