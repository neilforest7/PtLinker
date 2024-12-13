from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Union
import os
import json
import aiofiles

from core.logger import get_logger, setup_logger
from schemas.storage import StorageConfig, StorageWriteError, StorageReadError

class BaseStorage(ABC):
    """存储后端基类"""
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        
    @abstractmethod
    async def save(self, data: Any, path: str) -> bool:
        """保存数据"""
        pass
        
    @abstractmethod
    async def load(self, path: str) -> Any:
        """加载数据"""
        pass
        
    @abstractmethod
    async def exists(self, path: str) -> bool:
        """检查路径是否存在"""
        pass
        
    @abstractmethod
    async def delete(self, path: str) -> bool:
        """删除数据"""
        pass
        
    @abstractmethod
    async def check_space(self, required_mb: int = 100) -> bool:
        """检查存储空间是否足够"""
        pass


class FileStorage(BaseStorage):
    """文件存储后端"""
    
    def __init__(self, base_dir: str, compress: bool = False):
        super().__init__(base_dir)
        self.compress = compress
        setup_logger()
        self.logger = get_logger(name=__name__, site_id='FileStorage')
        
    async def save(self, data: Any, path: str) -> bool:
        try:
            full_path = self.base_dir / path
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            if isinstance(data, (dict, list)):
                content = json.dumps(data, ensure_ascii=False, indent=2)
            else:
                content = str(data)
                
            async with aiofiles.open(full_path, 'w', encoding='utf-8') as f:
                await f.write(content)
            return True
            
        except Exception as e:
            self.logger.error(f"保存文件失败: {str(e)}")
            raise StorageWriteError(str(e))
    
    async def load(self, path: str) -> Any:
        try:
            full_path = self.base_dir / path
            if not os.path.exists(full_path):
                raise StorageReadError("文件不存在")
                
            async with aiofiles.open(full_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content
                
        except Exception as e:
            self.logger.error(f"加载文件失败: {str(e)}")
            raise StorageReadError(str(e))
    
    async def exists(self, path: str) -> bool:
        return os.path.exists(self.base_dir / path)
    
    async def delete(self, path: str) -> bool:
        try:
            full_path = self.base_dir / path
            if os.path.exists(full_path):
                os.remove(full_path)
            return True
        except Exception as e:
            self.logger.error(f"删除文件失败: {str(e)}")
            return False
    
    async def check_space(self, required_mb: int = 100) -> bool:
        try:
            stats = os.statvfs(self.base_dir)
            free_mb = (stats.f_bavail * stats.f_frsize) / (1024 * 1024)
            return free_mb >= required_mb
        except:
            return True  # 如果检查失败，默认认为空间足够

class StoragePaths:
    """存储路径管理"""
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self.base_dir = Path(config.base_dir)
    
    def get_state_dir(self) -> Path:
        """获取状态目录"""
        return self.base_dir / self.config.state_dir
    
    def get_tasks_dir(self) -> Path:
        """获取任务目录"""
        return self.base_dir / self.config.tasks_dir
    
    def get_summary_path(self) -> Path:
        """获取汇总文件路径"""
        return self.get_state_dir() / self.config.summary_file
    
    def get_site_state_dir(self, site_id: str) -> Path:
        """获取站点状态目录"""
        return self.get_state_dir() / site_id
    
    def get_site_tasks_dir(self, site_id: str) -> Path:
        """获取站点任务目录"""
        return self.get_tasks_dir() / site_id
    
    def get_browser_state_path(self, site_id: str) -> Path:
        """获取浏览器状态文件路径"""
        return self.get_site_state_dir(site_id) / self.config.browser_state_file
    
    def get_relative_path(self, path: Union[str, Path]) -> str:
        """获取相对于base_dir的路径"""
        return str(Path(path).relative_to(self.base_dir))
