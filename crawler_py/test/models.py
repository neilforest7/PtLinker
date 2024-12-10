from datetime import datetime, timezone

from app.core.database import Base
from sqlalchemy import (JSON, Boolean, CheckConstraint, Column, DateTime,
                        Float, ForeignKey, Index, Integer, String, Text)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc), nullable=False)
    
class Crawler(Base):
    __tablename__ = "crawlers"
    
    crawler_id = Column(String(500), primary_key=True)
    is_logged_in = Column(Boolean, default=False)
    last_login_time = Column(DateTime, nullable=True, index=True)
    last_run_result = Column(Text, nullable=True)
    
    # 关系
    tasks = relationship("Task", back_populates="crawler", cascade="all, delete-orphan")
    browser_state = relationship("BrowserState", back_populates="crawler", uselist=False, cascade="all, delete-orphan")
    config = relationship("CrawlerConfig", back_populates="crawler", uselist=False, cascade="all, delete-orphan")
    credential = relationship("CrawlerCredential", back_populates="crawler", uselist=False, cascade="all, delete-orphan")
    site_config = relationship("SiteConfig", back_populates="crawler", uselist=False, cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('ix_crawler_login_status', 'crawler_id', 'is_logged_in'),
        Index('ix_crawler_last_login', 'last_login_time'),
    )

class BrowserState(Base):
    __tablename__ = "browserstate"
    
    crawler_id = Column(String(500), ForeignKey("crawlers.crawler_id", ondelete="CASCADE"), primary_key=True)
    cookies = Column(Text, nullable=True)
    local_storage = Column(Text, nullable=True)
    session_storage = Column(Text, nullable=True)
    
    crawler = relationship("Crawler", back_populates="browser_state")

class CrawlerConfig(Base):
    __tablename__ = "crawler_config"
    
    crawler_id = Column(String(500), ForeignKey("crawlers.crawler_id", ondelete="CASCADE"), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=True)
    use_proxy = Column(Boolean, nullable=False, default=False)
    proxy_url = Column(String(500), nullable=True)
    fresh_login = Column(Boolean, nullable=False, default=False)
    captcha_method = Column(String(500), nullable=True)
    captcha_skip = Column(Boolean, nullable=False, default=False)
    timeout = Column(Integer, nullable=True)
    headless = Column(Boolean, nullable=False, default=True)
    
    crawler = relationship("Crawler", back_populates="config")

    # 约束
    __table_args__ = (
        Index('ix_config_enabled', 'crawler_id', 'enabled'),
    )

class CrawlerCredential(Base):
    __tablename__ = "crawler_credential"
    
    crawler_id = Column(String(500), ForeignKey("crawlers.crawler_id", ondelete="CASCADE"), primary_key=True)
    manual_cookies = Column(Text, nullable=True)
    username = Column(String(500), nullable=True)
    password = Column(String(500), nullable=True)
    authorization = Column(String(500), nullable=True)
    apikey = Column(String(500), nullable=True)
    
    crawler = relationship("Crawler", back_populates="credential")

class SiteConfig(Base):
    __tablename__ = "site_config"
    
    crawler_id = Column(String(500), ForeignKey("crawlers.crawler_id", ondelete="CASCADE"), primary_key=True)
    site_id = Column(String(500), nullable=False)
    site_url = Column(String(500), nullable=False)
    login_config = Column(Text, nullable=True)
    extract_rules = Column(Text, nullable=True)
    checkin_config = Column(Text, nullable=True)
    credential = Column(Text, nullable=True)
    
    crawler = relationship("Crawler", back_populates="site_config")

    # 索引
    __table_args__ = (
        Index('ix_site_config_site', 'site_id', 'crawler_id'),
    )

class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    
    task_id = Column(String(500), primary_key=True)
    crawler_id = Column(String(500), ForeignKey("crawlers.crawler_id", ondelete="CASCADE"))
    status = Column(String(500), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)
    error = Column(String(500), nullable=True)
    error_details = Column(JSON, nullable=True)
    task_metadata = Column(JSON, nullable=True)
    system_info = Column(JSON, nullable=True)
    
    crawler = relationship("Crawler", back_populates="tasks")
    result = relationship("Result", back_populates="task", uselist=False, cascade="all, delete-orphan")

    # 混合属性
    @hybrid_property
    def duration(self):
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    # 索引和约束
    __table_args__ = (
        Index('ix_task_status', 'status'),
        Index('ix_task_crawler', 'crawler_id', 'status'),
        Index('ix_task_dates', 'created_at', 'completed_at'),
    )

class Result(Base):
    __tablename__ = "results"
    
    task_id = Column(String(500), ForeignKey("tasks.task_id", ondelete="CASCADE"), primary_key=True)
    crawler_id = Column(String(500), ForeignKey("crawlers.crawler_id", ondelete="CASCADE"), nullable=False)
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
    
    task = relationship("Task", back_populates="result")
    crawler = relationship("Crawler")

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
        Index('ix_result_user', 'crawler_id', 'username'),
        Index('ix_result_dates', 'join_time', 'last_active'),
    )