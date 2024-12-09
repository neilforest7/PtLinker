from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskBase(BaseModel):
    crawler_id: str = Field(
        ...,
        description="爬虫ID",
        example="bilibili"
    )

class TaskCreate(TaskBase):
    pass

class BatchTaskCreate(BaseModel):
    site_ids: List[str] = Field(
        ...,
        description="要创建任务的站点ID列表",
        example=["bilibili", "youtube"],
        min_items=1
    )

class TaskResponse(TaskBase):
    task_id: str = Field(..., description="任务唯一标识")
    status: TaskStatus = Field(..., description="任务状态")
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
    failed_sites: List[str] = Field(default_factory=list, description="创建失败的站点ID列表")
    total_created: int = Field(..., description="成功创建的任务数量")
    total_failed: int = Field(..., description="创建失败的任务数量")