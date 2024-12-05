from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLAEnum
from datetime import datetime
import enum
from app.core.database import Base

class LogLevel(str, enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class TaskLog(Base):
    __tablename__ = "task_logs"

    log_id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.task_id"), nullable=False)
    level = Column(SQLAEnum(LogLevel), nullable=False)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow) 