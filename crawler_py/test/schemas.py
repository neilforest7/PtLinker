from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator


class TaskStatus(str, Enum):
    READY = "ready"
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class CaptchaMethod(str, Enum):
    MANUAL = "manual"
    API = "api"
    OCR = "ocr"
    SKIP = "skip"

# Crawler Schemas
class CrawlerBase(BaseModel):
    crawler_id: str = Field(..., min_length=1, max_length=500)
    is_logged_in: bool = False
    last_login_time: Optional[datetime] = None
    last_run_result: Optional[str] = None

class CrawlerCreate(CrawlerBase):
    pass

class CrawlerUpdate(CrawlerBase):
    pass

class CrawlerResponse(CrawlerBase):
    tasks: Optional[List["TaskResponse"]] = []
    config: Optional["CrawlerConfigResponse"] = None
    
    class Config:
        from_attributes = True

# Config Schemas
class CrawlerConfigBase(BaseModel):
    enabled: bool = True
    use_proxy: bool = False
    proxy_url: Optional[HttpUrl] = None
    fresh_login: bool = False
    captcha_method: Optional[CaptchaMethod] = None
    captcha_skip: bool = False
    timeout: Optional[int] = Field(None, gt=0, le=3600)
    headless: bool = True

class CrawlerConfigCreate(CrawlerConfigBase):
    crawler_id: str = Field(..., min_length=1, max_length=500)

class CrawlerConfigUpdate(CrawlerConfigBase):
    pass

class CrawlerConfigResponse(CrawlerConfigBase):
    crawler_id: str
    
    class Config:
        from_attributes = True

# Site Config Schemas
class SiteConfigBase(BaseModel):
    site_id: str = Field(..., min_length=1, max_length=500)
    site_url: HttpUrl
    login_config: Optional[Dict[str, Any]] = None
    extract_rules: Optional[Dict[str, Any]] = None
    checkin_config: Optional[Dict[str, Any]] = None
    credential: Optional[Dict[str, Any]] = None

class SiteConfigCreate(SiteConfigBase):
    crawler_id: str = Field(..., min_length=1, max_length=500)

class SiteConfigUpdate(SiteConfigBase):
    pass

class SiteConfigResponse(SiteConfigBase):
    site_id: str
    
    class Config:
        from_attributes = True

# Result Schema
class ResultBase(BaseModel):
    username: Optional[str] = Field(None, min_length=1, max_length=500)
    user_class: Optional[str] = None
    uid: Optional[str] = None
    join_time: Optional[datetime] = None
    last_active: Optional[datetime] = None
    upload: Optional[float] = Field(None, ge=0)
    download: Optional[float] = Field(None, ge=0)
    ratio: Optional[float] = Field(None, ge=0)
    bonus: Optional[float] = Field(None, ge=0)
    seeding_score: Optional[float] = Field(None, ge=0)
    hr_count: Optional[int] = Field(None, ge=0)
    bonus_per_hour: Optional[float] = Field(None, ge=0)
    seeding_size: Optional[float] = Field(None, ge=0)
    seeding_count: Optional[int] = Field(None, ge=0)

class ResultCreate(ResultBase):
    task_id: str = Field(..., min_length=1, max_length=500)
    crawler_id: str = Field(..., min_length=1, max_length=500)
    
class ResultResponse(ResultBase):
    task_id: str
    crawler_id: str
    
    class Config:
        from_attributes = True

class TaskBase(BaseModel):
    status: TaskStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration: Optional[float]
    error: Optional[str]
    result: Optional[ResultResponse]

class TaskCreate(TaskBase):
    task_id: str = Field(..., min_length=1, max_length=500)
    crawler_id: str = Field(..., min_length=1, max_length=500)

class TaskUpdate(TaskBase):
    pass

# Response Models
class TaskResponse(TaskBase):
    task_id: str = Field(..., min_length=1, max_length=500)
    crawler_id: str = Field(..., min_length=1, max_length=500)

    class Config:
        from_attributes = True

class CrawlerResponse(BaseModel):
    crawler_id: str
    is_logged_in: bool
    last_login_time: Optional[datetime]
    config: Optional[CrawlerConfigResponse]
    site_config: Optional[SiteConfigResponse]
    active_tasks_count: int
    total_tasks_count: int

    class Config:
        from_attributes = True