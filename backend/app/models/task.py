from sqlalchemy import Column, String, DateTime, JSON, Enum as SQLAEnum
from datetime import datetime
import enum
from app.core.database import Base

class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True)
    crawler_id = Column(String, nullable=False)
    status = Column(SQLAEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING)
    config = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 