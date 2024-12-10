import enum
from datetime import datetime
from sqlalchemy import Column, DateTime, String, JSON
from sqlalchemy import Enum as SQLAEnum
from app.core.database import Base


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True)
    crawler_id = Column(String, nullable=False)
    status = Column(SQLAEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING)
    
    # 基本时间信息
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 错误信息
    error = Column(String, nullable=True)
    error_details = Column(JSON, nullable=True)  # 详细错误信息，包括堆栈跟踪等
    
    # 任务数据
    task_metadata = Column(JSON, nullable=True)  # 任务元数据，如配置信息、运行参数等
    result = Column(JSON, nullable=True)    # 任务结果数据
    
    # 系统信息
    system_info = Column(JSON, nullable=True)  # 运行时系统信息，如资源使用情况等 