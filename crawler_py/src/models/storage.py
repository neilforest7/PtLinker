from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class LoginState(BaseModel):
    """登录状态"""
    is_logged_in: bool = False
    last_login_time: Optional[int] = None
    username: Optional[str] = None

class BrowserState(BaseModel):
    """浏览器状态"""
    cookies: Dict[str, Any] = Field(default_factory=dict)
    local_storage: Dict[str, str] = {}
    session_storage: Dict[str, str] = {}
    login_state: LoginState = Field(default_factory=LoginState)

    def validate_state(self) -> Tuple[bool, str]:
        """验证状态数据的有效性
        
        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        try:
            # 1. 验证cookies格式
            for name, cookie in self.cookies.items():
                if not isinstance(name, str):
                    return False, f"Cookie名称必须是字符串，而不是 {type(name)}"
                if isinstance(cookie, dict):
                    required_fields = {'value', 'domain', 'path'}
                    missing_fields = required_fields - set(cookie.keys())
                    if missing_fields:
                        return False, f"Cookie {name} 缺少必要字段: {missing_fields}"
                elif not isinstance(cookie, str):
                    return False, f"Cookie {name} 的值必须是字符串或字典，而不是 {type(cookie)}"
            
            # 2. 验证storage格式
            for key, value in self.local_storage.items():
                if not isinstance(key, str):
                    return False, f"localStorage键必须是字符串，而不是 {type(key)}"
                if not isinstance(value, str):
                    return False, f"localStorage值必须是字符串，而不是 {type(value)}"
                    
            for key, value in self.session_storage.items():
                if not isinstance(key, str):
                    return False, f"sessionStorage键必须是字符串，而不是 {type(key)}"
                if not isinstance(value, str):
                    return False, f"sessionStorage值必须是字符串，而不是 {type(value)}"
            
            # 3. 验证登录状态的一致性
            if self.login_state.is_logged_in:
                if not self.login_state.username:
                    return False, "登录状态为已登录但缺少用户名"
                if not self.login_state.last_login_time:
                    return False, "登录状态为已登录但缺少登录时间"
            else:
                if self.login_state.username or self.login_state.last_login_time:
                    return False, "登录状态为未登录但存在用户名或登录时间"
            
            # 4. 验证时间戳的有效性
            if self.login_state.last_login_time:
                current_time = int(datetime.now().timestamp())
                if self.login_state.last_login_time > current_time:
                    return False, "登录时间戳无效（未来时间）"
                if current_time - self.login_state.last_login_time > 90 * 24 * 3600:  # 90天
                    return False, "登录时间戳过期（超过90天）"
            
            return True, ""
            
        except Exception as e:
            return False, f"验证状态时发生错误: {str(e)}"

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
    # 基础配置
    site_id: str = Field(default="")
    task_id: str = Field(default="")
    base_dir: str
    home_url: str = Field(default="")
    login_check_selector: str = Field(default="")
    
    # 目录结构
    state_dir: str = Field(default="state")  # 状态目录
    tasks_dir: str = Field(default="tasks")  # 任务目录
    summary_file: str = Field(default="sites_summary.json")  # 汇总文件名
    browser_state_file: str = Field(default="browser_state.json")  # 浏览器状态文件名
    
    # 文件处理配置
    storage_type: str = Field(default="file")  # 存储类型：file
    compress: bool = Field(default=False)  # 是否压缩文件
    compress_suffix: str = Field(default=".gz")  # 压缩文件后缀
    
    # 备份配置
    backup: bool = Field(default=True)  # 是否启用备份
    max_backups: int = Field(default=3)  # 最大备份数量
    backup_suffix: str = Field(default=".bak")  # 备份文件后缀
    backup_time_format: str = Field(default="%Y%m%d_%H%M%S")  # 备份文件时间格式
    
    # 存储限制
    min_free_space_mb: int = Field(default=100)  # 最小剩余空间(MB)

    class Config:
        arbitrary_types_allowed = True

class SiteRunStatus(BaseModel):
    """站点运行状态"""
    site_id: str
    last_run_time: int
    browser_state: BrowserState
    last_task: Optional[str] = None  # 最后一次任务ID
    last_data_file: Optional[str] = None  # 最后一次数据文件路径
    last_task_data: Optional[Dict[str, Any]] = Field(default=None)  # 最后一次抓取的数据
    last_error: Optional[CrawlerError] = None
    stats: Dict[str, Any] = Field(default_factory=dict)  # 统计信息

class SitesStatusSummary(BaseModel):
    """所有站点状态汇总"""
    last_updated: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    sites: Dict[str, SiteRunStatus] = Field(default_factory=dict)
    
class StorageError(Exception):
    """存储相关的基础异常类"""
    pass

class StorageWriteError(StorageError):
    """写入存储时的异常"""
    pass

class StorageReadError(StorageError):
    """读取存储时的异常"""
    pass

class StorageSpaceError(StorageError):
    """存储空间不足的异常"""
    pass