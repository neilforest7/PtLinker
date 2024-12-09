from datetime import datetime
from pathlib import Path

from models.storage import StorageConfig
from utils.logger import get_logger
from storage.storage_backend import FileStorage

class BackupManager:
    """备份管理器"""
    
    def __init__(self, storage: FileStorage, config: StorageConfig):
        self.storage = storage
        self.config = config
        self.logger = get_logger(__name__, site_id='BackupMgr')
    
    async def create_backup(self, path: str) -> bool:
        """创建数据备份"""
        try:
            timestamp = datetime.now().strftime(self.config.backup_time_format)
            backup_path = f"{path}.{timestamp}{self.config.backup_suffix}"
            
            self.logger.debug(f"创建备份: {backup_path}")
            
            # 加载原始数据并保存为备份
            data = await self.storage.load(path)
            return await self.storage.save(data, backup_path)
            
        except Exception as e:
            self.logger.error(f"创建备份失败: {str(e)}")
            return False
    
    async def cleanup_old_backups(self, path: str) -> None:
        """清理旧的备份文件"""
        try:
            base_path = Path(path)
            backup_pattern = f"{base_path.name}.*{self.config.backup_suffix}"
            
            # 获取所有备份文件
            backup_files = sorted(
                base_path.parent.glob(backup_pattern),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            # 删除超出数量的旧备份
            for backup_file in backup_files[self.config.max_backups:]:
                self.logger.debug(f"删除旧备份: {backup_file}")
                await self.storage.delete(str(backup_file.relative_to(self.storage.base_dir)))
                
        except Exception as e:
            self.logger.warning(f"清理旧备份失败: {str(e)}")
