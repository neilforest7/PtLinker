from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime

class LoginState(BaseModel):
    """登录状态"""
    is_logged_in: bool = False
    last_login_time: Optional[int] = None
    username: Optional[str] = None

class BrowserState(BaseModel):
    """浏览器状态"""
    cookies: List[Dict[str, Any]] = []
    local_storage: Dict[str, str] = {}
    session_storage: Dict[str, str] = {}
    login_state: LoginState = Field(default_factory=LoginState)

class CrawlerError(BaseModel):
    """爬虫错误"""
    type: str
    message: str
    timestamp: int
    stack: Optional[str] = None

class DatasetInfo(BaseModel):
    """数据集信息"""
    id: str
    item_count: int = 0
    total_size: int = 0
    created_at: float
    modified_at: float

class StorageConfig(BaseModel):
    """存储配置"""
    site_id: str
    task_id: str
    base_dir: str
    home_url: str = Field(default="")
    login_check_selector: str = Field(default="")

    class Config:
        arbitrary_types_allowed = True