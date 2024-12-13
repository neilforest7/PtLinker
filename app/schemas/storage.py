from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field
from schemas.browserstate import BrowserState
from schemas.crawlerschemas import CrawlerError


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