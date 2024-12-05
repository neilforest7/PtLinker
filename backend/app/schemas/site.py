from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

class LoginState(BaseModel):
    """站点登录状态"""
    is_logged_in: bool
    last_login_time: int
    username: str

class BrowserState(BaseModel):
    """浏览器状态"""
    cookies: Dict[str, Dict[str, Any]]
    local_storage: Dict[str, Any] = {}
    session_storage: Dict[str, Any] = {}
    login_state: LoginState

class SiteUserStats(BaseModel):
    """站点用户统计信息"""
    username: str
    user_class: str
    uid: str
    join_time: datetime
    last_active: datetime
    upload: float = Field(..., description="上传量(GB)")
    download: float = Field(..., description="下载量(GB)")
    ratio: float = Field(..., description="分享率")
    bonus: float = Field(..., description="魔力值")
    seeding_score: Optional[float] = None
    hr_count: Optional[int] = None
    bonus_per_hour: Optional[float] = None
    seeding_size: Optional[float] = None
    seeding_count: Optional[int] = None

class SiteSummary(BaseModel):
    """站点摘要信息"""
    site_id: str = Field(..., description="站点ID")
    name: str = Field(..., description="站点名称")
    status: str = Field(..., description="站点状态")
    last_check_time: Optional[datetime] = None
    user_stats: Optional[SiteUserStats] = None
    browser_state: Optional[BrowserState] = None 