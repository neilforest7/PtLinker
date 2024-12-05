from pydantic import BaseModel, Field, conlist
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import json
from app.models.task import TaskStatus

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

class TaskBase(BaseModel):
    crawler_id: str
    config: Optional[Dict[str, Any]] = None

class TaskCreate(TaskBase):
    crawler_id: str = Field(
        ...,
        description="爬虫ID，对应爬虫配置文件名",
        example="bilibili"
    )
    config: Dict[str, Any] = Field(
        ...,
        description="爬虫配置参数",
        example={
            "user_id": "12345678",
            "max_videos": 50,
            "include_replies": True,
            "fetch_details": True,
            "credentials": {
                "cookie": "your_cookie_here",
                "csrf": "your_csrf_token"
            }
        }
    )

class BatchTaskCreate(BaseModel):
    site_ids: List[str] = Field(
        ...,
        description="要创建任务的站点ID列表",
        example=["bilibili", "youtube"],
        min_items=1
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="所有任务共用的基础配置参数（可选）",
        example={
            "max_items": 100,
            "fetch_details": True
        }
    )

class TaskResponse(TaskBase):
    task_id: str = Field(..., description="任务唯一标识")
    crawler_id: str = Field(..., description="爬虫ID")
    config: Dict[str, Any] = Field(..., description="爬虫配置")
    status: TaskStatus = Field(..., description="任务状态")
    result: Optional[Dict[str, Any]] = Field(None, description="任务执行结果")
    error: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    started_at: Optional[datetime] = Field(None, description="开始执行时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        from_attributes = True

class BatchTaskResponse(BaseModel):
    tasks: List[TaskResponse] = Field(..., description="创建的任务列表")
    total_count: int = Field(..., description="创建的任务总数")
    failed_sites: List[str] = Field(default_factory=list, description="创建失败的站点ID列表")