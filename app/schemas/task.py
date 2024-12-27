from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, computed_field
from schemas.result import ResultResponse


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    QUEUED = "queued"
    READY = "ready"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskBase(BaseModel):
    """任务基础模型"""
    task_id: str = Field(..., description="任务ID")
    site_id: str = Field(..., description="站点ID")
    status: TaskStatus = Field(..., description="任务状态")
    created_at: Optional[datetime] = Field(None, description="任务开始时间")
    updated_at: Optional[datetime] = Field(None, description="任务更新时间")
    completed_at: Optional[datetime] = Field(None, description="任务完成时间")
    msg: Optional[str] = Field(None, description="错误信息")
    error_details: Optional[Dict[str, Any]] = Field(None, description="详细错误信息")
    task_metadata: Optional[Dict[str, Any]] = Field(None, description="任务元数据")
    system_info: Optional[Dict[str, Any]] = Field(None, description="系统信息")
    # result: Optional[ResultResponse] = Field(None, description="任务结果")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class TaskCreate(TaskBase):
    """创建任务模型"""
    task_id: str = Field(..., description="任务ID")
    site_id: str = Field(..., description="站点ID")
    status: TaskStatus = Field(default=TaskStatus.READY, description="任务状态")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class TaskUpdate(BaseModel):
    """更新任务模型"""
    task_id: str = Field(..., description="任务ID")
    site_id: Optional[str] = Field(None, description="站点ID")
    status: Optional[TaskStatus] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    msg: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    task_metadata: Optional[Dict[str, Any]] = None
    system_info: Optional[Dict[str, Any]] = None


class TaskResponse(TaskBase):
    """任务响应模型"""
    duration: Optional[float] = Field(None, description="任务持续时间(秒)")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    # @computed_field
    # @property
    # def duration(self) -> Optional[float]:
    #     """计算任务持续时间（秒）"""
    #     if self.completed_at and self.created_at:
    #         return (self.completed_at - self.created_at).total_seconds()
    #     return None

    # class Config:
    #     json_schema_extra = {
    #         "example": {
    #             "task_id": "task_123",
    #             "site_id": "example_site",
    #             "status": "running",
    #             "started_at": "2024-01-20T10:00:00",
    #             "completed_at": None,
    #             "error": None,
    #             "duration": 120.5,
    #             "created_at": "2024-01-20T10:00:00",
    #             "updated_at": "2024-01-20T10:02:00",
    #             "task_metadata": {
    #                 "type": "crawl",
    #                 "priority": 1
    #             },
    #             "system_info": {
    #                 "cpu_usage": 45.2,
    #                 "memory_usage": 128.5
    #             },
    #             "result": {
    #                 "username": "example_user",
    #                 "user_class": "VIP",
    #                 "upload": 1024.5,
    #                 "download": 512.3,
    #                 "ratio": 2.0,
    #                 "bonus": 1000.0,
    #                 "seeding_size": 2048.0,
    #                 "seeding_count": 10
    #             }
    #         }
    #     }