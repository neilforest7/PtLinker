from typing import Optional
from pydantic import BaseModel, Field, HttpUrl
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
    proxy_url: Optional[HttpUrl] = None
    fresh_login: bool = False
    captcha_method: Optional[CaptchaMethod] = None
    captcha_skip: bool = False
    timeout: Optional[int] = Field(None, gt=0, le=3600)
    headless: bool = True

class CrawlerConfigCreate(CrawlerConfigBase):
    site_id: str = Field(..., min_length=1, max_length=500)

class CrawlerConfigUpdate(CrawlerConfigBase):
    pass

class CrawlerConfigResponse(CrawlerConfigBase):
    site_id: str = Field(..., min_length=1, max_length=500)
    
    class Config:
        from_attributes = True

