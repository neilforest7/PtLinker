from typing import Optional
from pydantic import BaseModel, Field, validator
from enum import Enum

class CaptchaMethod(str, Enum):
    MANUAL = "manual"
    API = "api"
    OCR = "ocr"
    SKIP = "skip"


# Config Schemas
class CrawlerConfigBase(BaseModel):
    site_id: str = Field(..., min_length=1, max_length=500)
    enabled: bool = True
    use_proxy: bool = False
    proxy_url: Optional[str] = None
    fresh_login: bool = False
    captcha_method: Optional[CaptchaMethod] = None
    captcha_skip: bool = False
    timeout: Optional[int] = Field(None, gt=0, le=3600)
    headless: bool = True
    login_max_retry: Optional[int] = Field(None, gt=0, le=10)

class CrawlerConfigCreate(CrawlerConfigBase):
    site_id: str = Field(..., min_length=1, max_length=500)

class CrawlerConfigUpdate(BaseModel):
    site_id: Optional[str] = Field(None, min_length=1, max_length=500)
    enabled: Optional[bool] = None
    use_proxy: Optional[bool] = None
    proxy_url: Optional[str] = None
    fresh_login: Optional[bool] = None
    captcha_method: Optional[CaptchaMethod] = None
    captcha_skip: Optional[bool] = None
    timeout: Optional[int] = Field(None, gt=0, le=3600)
    headless: Optional[bool] = None
    login_max_retry: Optional[int] = Field(None, gt=0, le=10)

    @validator('use_proxy', 'enabled', 'fresh_login', 'captcha_skip', 'headless', pre=True)
    def validate_boolean(cls, v):
        if isinstance(v, str):
            if v.lower() in ('true', '1', 'yes', 'on'):
                return True
            if v.lower() in ('false', '0', 'no', 'off'):
                return False
        return v

class CrawlerConfigResponse(CrawlerConfigBase):
    site_id: str = Field(..., min_length=1, max_length=500)
    
    class Config:
        from_attributes = True

