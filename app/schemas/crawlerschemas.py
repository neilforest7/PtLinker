from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator
from schemas.crawlerconfig import CrawlerConfigResponse
from schemas.task import TaskResponse


# Crawler Schemas
class CrawlerBase(BaseModel):
    site_id: str = Field(..., min_length=1, max_length=500)
    is_logged_in: bool = False
    last_login_time: Optional[datetime] = None
    last_run_result: Optional[str] = None
    total_tasks: int = 0

class CrawlerCreate(CrawlerBase):
    pass

class CrawlerUpdate(CrawlerBase):
    pass

class CrawlerResponse(CrawlerBase):
    tasks: Optional["TaskResponse"] = None
    config: Optional["CrawlerConfigResponse"] = None
    
    class Config:
        from_attributes = True

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
    site_id: str = Field(..., description="爬虫唯一标识")
    name: str = Field(..., description="爬虫名称")
    description: str = Field(default="", description="爬虫描述")
    site_id: str = Field(..., description="关联的站点ID")

class CrawlerStatus(BaseModel):
    """爬虫状态"""
    site_id: str = Field(..., description="爬虫ID")
    is_connected: bool = Field(..., description="是否已连接")
    status: Optional[str] = Field(None, description="爬虫状态")
    last_updated: str = Field(..., description="最后更新时间")
    connected_at: Optional[str] = Field(None, description="连接时间")
    disconnected_at: Optional[str] = Field(None, description="断开连接时间")
    error: Optional[str] = Field(None, description="错误信息")

class CrawlerListResponse(BaseModel):
    """爬虫列表响应"""
    crawlers: List[CrawlerInfo]
    total: int
    
class CrawlerError(BaseModel):
    """爬虫错误"""
    type: str
    message: str
    timestamp: int
    stack: Optional[str] = None
