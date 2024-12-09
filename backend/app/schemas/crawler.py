from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

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

class CrawlerStatus(BaseModel):
    """爬虫状态"""
    crawler_id: str = Field(..., description="爬虫ID")
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