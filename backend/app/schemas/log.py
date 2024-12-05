from pydantic import BaseModel
from datetime import datetime
from app.models.log import LogLevel

class TaskLogResponse(BaseModel):
    log_id: str
    task_id: str
    level: LogLevel
    message: str
    created_at: datetime

    class Config:
        from_attributes = True

class TaskLogFilter(BaseModel):
    level: LogLevel | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None 