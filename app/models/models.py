from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import (JSON, Boolean, CheckConstraint, Column, DateTime,
                        Float, ForeignKey, Index, Integer, String, Text, Enum)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from core.database import Base


class TaskStatus(PyEnum):
    """任务状态枚举"""
    PENDING = "pending"     # 初始状态
    QUEUED = "queued"      # 在队列中等待
    READY = "ready"         # 准备就绪
    RUNNING = "running"   # 正在运行
    SUCCESS = "success"   # 成功
    FAILED = "failed"     # 失败
    CANCELLED = "cancelled" # 已取消

class TimestampMixin:
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now(), nullable=False)
    
class Crawler(Base):
    __tablename__ = "crawlers"
    
    site_id = Column(String(500), primary_key=True)
    is_logged_in = Column(Boolean, default=False)
    last_login_time = Column(DateTime, nullable=True, index=True)
    last_run_result = Column(Text, nullable=True)
    total_tasks = Column(Integer, nullable=False, default=0)

    # 关系
    tasks = relationship("Task", back_populates="crawler", cascade="all, delete-orphan")
    results = relationship("Result", back_populates="crawler", cascade="all, delete-orphan")
    checkin_results = relationship("CheckInResult", back_populates="crawler", cascade="all, delete-orphan")
    browser_state = relationship("BrowserState", back_populates="crawler", uselist=False, cascade="all, delete-orphan")
    config = relationship("CrawlerConfig", back_populates="crawler", uselist=False, cascade="all, delete-orphan")
    credential = relationship("CrawlerCredential", back_populates="crawler", uselist=False, cascade="all, delete-orphan")
    site_config = relationship("SiteConfig", back_populates="crawler", uselist=False, cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('ix_crawler_login_status', 'site_id', 'is_logged_in'),
        Index('ix_crawler_last_login', 'last_login_time'),
    )

class CrawlerConfig(Base):
    __tablename__ = "crawler_config"
    
    site_id = Column(String(500), ForeignKey("crawlers.site_id", ondelete="CASCADE"), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=True)
    use_proxy = Column(Boolean, nullable=True, default=False)
    proxy_url = Column(String(500), nullable=True)
    fresh_login = Column(Boolean, nullable=True, default=False)
    captcha_method = Column(String(500), nullable=True)
    captcha_skip = Column(Boolean, nullable=True, default=False)
    timeout = Column(Integer, nullable=True)
    headless = Column(Boolean, nullable=True, default=True)
    login_max_retry = Column(Integer, nullable=True, default=3)
    
    crawler = relationship("Crawler", back_populates="config")

    # 约束
    __table_args__ = (
        Index('ix_config_enabled', 'site_id', 'enabled'),
    )

class CrawlerCredential(Base):
    __tablename__ = "crawler_credential"
    
    site_id = Column(String(500), ForeignKey("crawlers.site_id", ondelete="CASCADE"), primary_key=True)
    enable_manual_cookies = Column(Boolean, nullable=True, default=False)
    manual_cookies = Column(Text, nullable=True)
    username = Column(String(500), nullable=True)
    password = Column(String(500), nullable=True)
    authorization = Column(String(500), nullable=True)
    apikey = Column(String(500), nullable=True)
    description = Column(String(500), nullable=True)
    
    crawler = relationship("Crawler", back_populates="credential")

class SiteConfig(Base):
    __tablename__ = "site_config"
    
    site_id = Column(String(500), ForeignKey("crawlers.site_id", ondelete="CASCADE"), primary_key=True)
    site_url = Column(String(500), nullable=False)
    login_config = Column(Text, nullable=True)
    extract_rules = Column(Text, nullable=True)
    checkin_config = Column(Text, nullable=True)
    
    crawler = relationship("Crawler", back_populates="site_config")

    # 索引
    __table_args__ = (
        Index('ix_site_config_site', 'site_id', 'site_id'),
    )
    
class BrowserState(Base):
    __tablename__ = "browserstate"
    
    site_id = Column(String(500), ForeignKey("crawlers.site_id", ondelete="CASCADE"), primary_key=True)
    cookies = Column(JSON, nullable=True)
    local_storage = Column(JSON, nullable=True)
    session_storage = Column(JSON, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    crawler = relationship("Crawler", back_populates="browser_state")

class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    
    task_id = Column(String(500), primary_key=True)
    site_id = Column(String(500), ForeignKey("crawlers.site_id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(TaskStatus), nullable=False)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    msg = Column(String(500), nullable=True)
    error_details = Column(JSON, nullable=True)
    task_metadata = Column(JSON, nullable=True)
    system_info = Column(JSON, nullable=True)
    
    crawler = relationship("Crawler", back_populates="tasks")
    result = relationship("Result", back_populates="task", uselist=False, cascade="all, delete-orphan")
    checkin_result = relationship("CheckInResult", back_populates="task", uselist=False, cascade="all, delete-orphan")

    # 混合属性
    # @hybrid_property
    # def duration(self):
    #     if self.completed_at and self.created_at:
    #         return (self.completed_at - self.created_at).total_seconds()
    #     return None

    # 索引和约束
    __table_args__ = (
        Index('ix_task_status', 'status'),
        Index('ix_task_crawler', 'site_id', 'status'),
        Index('ix_task_dates', 'created_at', 'completed_at'),
    )

class Result(Base):
    __tablename__ = "results"
    
    task_id = Column(String(500), ForeignKey("tasks.task_id", ondelete="CASCADE"), primary_key=True)
    site_id = Column(String(500), ForeignKey("crawlers.site_id", ondelete="CASCADE"), nullable=False)
    username = Column(Text, nullable=True)
    user_class = Column(Text, nullable=True)
    uid = Column(Text, nullable=True)
    join_time = Column(DateTime, nullable=True)
    last_active = Column(DateTime, nullable=True)
    upload = Column(Float, nullable=True)
    download = Column(Float, nullable=True)
    ratio = Column(Float, nullable=True)
    bonus = Column(Float, nullable=True)
    seeding_score = Column(Float, nullable=True)
    hr_count = Column(Integer, nullable=True)
    bonus_per_hour = Column(Float, nullable=True)
    seeding_size = Column(Float, nullable=True)
    seeding_count = Column(Integer, nullable=True)
    
    task = relationship("Task", back_populates="result", uselist=False)
    crawler = relationship("Crawler", back_populates="results")

    # 混合属性
    @hybrid_property
    def calculated_ratio(self):
        """获取分享率，优先使用已有值，否则自动计算
        当下载量为0时返回999999
        """
        if self.ratio is not None:
            return self.ratio
        if self.upload is not None and self.download is not None:
            if self.download == 0:
                return 999999
            return self.upload / self.download
        return None
    
    # 索引和约束
    __table_args__ = (
        Index('ix_result_user', 'site_id', 'username'),
        Index('ix_result_dates', 'join_time', 'last_active'),
    )

class CheckInResult(Base):
    __tablename__ = "checkin_results"
    
    task_id = Column(String(500), ForeignKey("tasks.task_id", ondelete="CASCADE"), primary_key=True)
    site_id = Column(String(500), ForeignKey("crawlers.site_id", ondelete="CASCADE"), nullable=False)
    result = Column(String(500), nullable=False)
    checkin_date = Column(DateTime, nullable=False)
    last_run_at = Column(DateTime, nullable=False, index=True)
    
    # 关系
    crawler = relationship("Crawler", back_populates="checkin_results")
    task = relationship("Task", back_populates="checkin_result", uselist=False)
    
    # 索引
    __table_args__ = (
        Index('ix_checkin_results_site_id', 'site_id'),
        Index('ix_checkin_results_dates', 'checkin_date', 'last_run_at'),
    )

