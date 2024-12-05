from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
from .site import SiteSummary

class CrawlerProcessStatus(BaseModel):
    """爬虫进程状态"""
    pid: Optional[int] = Field(None, description="进程ID")
    start_time: Optional[datetime] = Field(None, description="进程启动时间")
    cpu_percent: Optional[float] = Field(None, description="CPU使用率")
    memory_percent: Optional[float] = Field(None, description="内存使用率")
    is_running: bool = Field(default=False, description="是否正在运行")
    last_health_check: Optional[datetime] = Field(None, description="最后健康检查时间")

class CrawlerInfo(BaseModel):
    """爬虫基本信息"""
    crawler_id: str = Field(..., description="爬虫唯一标识")
    name: str = Field(..., description="爬虫名称")
    description: str = Field(default="", description="爬虫描述")
    site_id: str = Field(..., description="关联的站点ID")
    config_schema: Dict[str, Any] = Field(default={}, description="配置模式")
    default_config: Dict[str, Any] = Field(default={}, description="默认配置")

class CrawlerStatus(BaseModel):
    """爬虫状态信息"""
    crawler_id: str
    site_id: str
    status: str = Field(..., description="爬虫状态: idle, running, error")
    running_tasks: int = Field(default=0, description="运行中的任务数")
    total_tasks: int = Field(default=0, description="总任务数")
    last_run: Optional[datetime] = Field(default=None, description="最后运行时间")
    success_rate: float = Field(default=0.0, description="成功率")
    site_status: Optional[SiteSummary] = None
    process_status: Optional[CrawlerProcessStatus] = None
    last_error: Optional[str] = Field(None, description="最后一次错误信息")

class TaskResult(BaseModel):
    """任务执行结果"""
    task_id: str
    crawler_id: str
    site_id: str
    execution_time: datetime
    user_stats: Optional[Dict[str, Any]] = None
    browser_state: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    process_info: Optional[CrawlerProcessStatus] = None

class CrawlerListResponse(BaseModel):
    """爬虫列表响应"""
    crawlers: List[CrawlerInfo]
    total: int

class CrawlerDetailResponse(CrawlerInfo):
    """爬虫详细信息响应"""
    status: CrawlerStatus
    latest_result: Optional[TaskResult] = None

class CrawlerConfig(BaseModel):
    """爬虫配置模型"""
    site_id: str = Field(..., description="站点ID")
    name: str = Field(..., description="站点名称")
    url: str = Field(..., description="站点URL")
    login_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="登录配置"
    )
    extract_rules: Optional[Dict[str, Any]] = Field(
        None,
        description="数据提取规则"
    )
    browser_config: Optional[Dict[str, Any]] = Field(
        None,
        description="浏览器配置"
    )
    process_config: Optional[Dict[str, Any]] = Field(
        None,
        description="进程配置，如资源限制等"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "site_id": "example",
                "name": "Example Site",
                "url": "https://example.com",
                "login_config": {
                    "username": "your_username",
                    "password": "your_password",
                    "captcha": True
                },
                "extract_rules": {
                    "user_info": {
                        "selector": "#user-info",
                        "fields": {
                            "username": ".username",
                            "ratio": ".ratio"
                        }
                    }
                },
                "browser_config": {
                    "headless": True,
                    "timeout": 30
                },
                "process_config": {
                    "max_memory_percent": 80,
                    "max_cpu_percent": 50,
                    "health_check_interval": 5
                }
            }
        } 