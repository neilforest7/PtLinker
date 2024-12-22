from typing import Optional

from pydantic import BaseModel, Field


class CrawlerCredentialBase(BaseModel):
    """站点凭证配置"""
    site_id: str = Field(..., min_length=1, max_length=500)
    enable_manual_cookies: Optional[bool] = False
    manual_cookies: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    authorization: Optional[str] = None
    apikey: Optional[str] = None
    description: Optional[str] = None

class CrawlerCredentialCreate(CrawlerCredentialBase):
    pass

class CrawlerCredentialUpdate(BaseModel):
    enable_manual_cookies: Optional[bool] = False
    manual_cookies: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    authorization: Optional[str] = None
    apikey: Optional[str] = None
    description: Optional[str] = None

class CrawlerCredentialResponse(CrawlerCredentialBase):
    site_id: str
    
    class Config:
        from_attributes = True