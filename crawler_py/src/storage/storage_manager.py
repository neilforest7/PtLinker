from typing import Any, Dict, Optional

from models.storage import SiteRunStatus, SitesStatusSummary, StorageConfig
from storage.browser_state_manager import BrowserStateManager
from storage.backup_manager import BackupManager
from storage.site_state_manager import SiteStatusManager
from storage.storage_backend import FileStorage, StoragePaths
from utils.logger import get_logger

class StorageManager:
    """存储管理器，提供统一的存储接口"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = StorageConfig(**config)
        self.paths = StoragePaths(self.config)
        
        self.logger = get_logger(__name__, site_id='StorageMgr')
        
        # 初始化存储后端
        if self.config.storage_type == 'file':
            self.storage = FileStorage(self.config.base_dir, self.config.compress)
        else:
            raise ValueError(f"不支持的存储类型: {self.config.storage_type}")
            
        self.backup_manager = BackupManager(self.storage, self.config)

        # 初始化站点状态管理器
        self.site_status_manager = SiteStatusManager(self.storage, self.paths)
        
        # 初始化浏览器状态管理器
        self.browser_manager = BrowserStateManager(self)
        
        # 设置browser_manager到site_status_manager
        self.site_status_manager.set_browser_manager(self.browser_manager)
    
    async def save(self, data: Any, path: str, backup: bool = None) -> bool:
        """保存数据"""
        self.logger.info(f"开始保存数据: {path}")
        
        # 确定是否需要备份
        should_backup = backup if backup is not None else self.config.backup
        
        # 如果需要备份且文件已存在，创建备份
        if should_backup:
            await self.backup_manager.create_backup(path)
        
        return await self.storage.save(data, path)
    
    async def load(self, path: str) -> Any:
        """加载数据"""
        return await self.storage.load(path)
    
    async def exists(self, path: str) -> bool:
        """检查路径是否存在"""
        return await self.storage.exists(path)
    
    async def delete(self, path: str) -> bool:
        """删除数据"""
        return await self.storage.delete(path)
    
    async def check_space(self, required_mb: int = 100) -> bool:
        """检查存储空间是否足够"""
        return await self.storage.check_space(required_mb)
    
    async def update_site_status(self, site_id: str) -> None:
        """更新站点状态"""
        await self.site_status_manager.update_site_status(site_id)
    
    async def get_all_sites_status(self, force_scan: bool = False) -> SitesStatusSummary:
        """获取所有站点状态"""
        return await self.site_status_manager.get_all_sites_status(force_scan)
    
    async def get_site_status(self, site_id: str, force_update: bool = False) -> Optional[SiteRunStatus]:
        """获取单个站点的状态"""
        return await self.site_status_manager.get_site_status(site_id)
