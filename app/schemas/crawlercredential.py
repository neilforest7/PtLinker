from typing import Optional
from pydantic import BaseModel, Field


class CrawlerCredentialBase(BaseModel):
    """站点凭证配置"""
    site_id: str = Field(..., min_length=1, max_length=500)
    manual_cookies: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    authorization: Optional[str] = None
    apikey: Optional[str] = None
    enabled: Optional[bool] = True
    description: Optional[str] = None

class CrawlerCredentialCreate(CrawlerCredentialBase):
    pass

class CrawlerCredentialUpdate(CrawlerCredentialBase):
    pass

class CrawlerCredentialResponse(CrawlerCredentialBase):
    site_id: str
    enabled: bool
    
    class Config:
        from_attributes = True