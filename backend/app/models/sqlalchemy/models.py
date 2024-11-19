from sqlalchemy import Boolean, Column, Integer, String, DateTime, JSON, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class TaskStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPING = "stopping"
    STOPPED = "stopped"

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    config = Column(JSON, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    progress = Column(Integer, default=0)
    error = Column(String)
    stats = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CrawledData(Base):
    __tablename__ = "crawled_data"
    
    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    url = Column(String, nullable=False)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class CrawlerConfig(Base):
    __tablename__ = "crawler_configs"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    config = Column(JSON, nullable=False)
    is_template = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 