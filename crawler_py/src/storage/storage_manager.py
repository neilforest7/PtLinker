from typing import Any, Dict,  Optional, Union
from pathlib import Path
import json
import gzip
import shutil
import time
from datetime import datetime
from abc import ABC, abstractmethod

from utils.logger import get_logger, setup_logger

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

class BaseStorage(ABC):
    """存储后端的基类，定义存储接口"""
    
    @abstractmethod
    async def save(self, data: Any, path: str) -> bool:
        """保存数据"""
        pass
    
    @abstractmethod
    async def load(self, path: str) -> Any:
        """加载数据"""
        pass
    
    @abstractmethod
    async def delete(self, path: str) -> bool:
        """删除数据"""
        pass
    
    @abstractmethod
    async def exists(self, path: str) -> bool:
        """检查数据是否存在"""
        pass

class FileStorage(BaseStorage):
    """文件存储后端实现"""
    
    def __init__(self, base_dir: Union[str, Path], compress: bool = True):
        self.base_dir = Path(base_dir)
        self.compress = compress
        setup_logger()
        self.logger = get_logger(name=__name__, site_id="Storage")
        
    async def save(self, data: Any, path: str) -> bool:
        """
        保存数据到文件
        
        Args:
            data: 要保存的数据
            path: 相对于base_dir的路径
            
        Returns:
            bool: 是否保存成功
        """
        try:
            full_path = self.base_dir / path
            self.logger.debug(f"准备保存数据到: {full_path}")
            
            # 确保目录存在
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 检查磁盘空间
            if not self._check_disk_space(data):
                raise StorageSpaceError("存储空间不足")
            
            # 序列化数据
            json_data = json.dumps(data, ensure_ascii=False, indent=2)
            
            if self.compress:
                # 使用gzip压缩
                compressed_path = str(full_path) + '.gz'
                self.logger.debug(f"使用gzip压缩保存: {compressed_path}")
                with gzip.open(compressed_path, 'wt', encoding='utf-8') as f:
                    f.write(json_data)
            else:
                # 直接保存JSON
                self.logger.debug(f"直接保存JSON: {full_path}")
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(json_data)
            
            self.logger.info(f"数据保存成功: {path}")
            return True
            
        except Exception as e:
            self.logger.error("保存数据失败", exc_info=True)
            raise StorageWriteError(str(e))
    
    async def load(self, path: str) -> Any:
        """
        从文件加载数据
        
        Args:
            path: 相对于base_dir的路径
            
        Returns:
            加载的数据
            
        Raises:
            StorageReadError: 当文件不存在或读取失败时
        """
        try:
            full_path = self.base_dir / path
            
            # 检查文件是否存在
            if not await self.exists(path):
                self.logger.debug(f"文件不存在: {full_path}")
                raise FileNotFoundError(f"文件不存在: {full_path}")
            
            # 检查压缩文件
            compressed_path = str(full_path) + '.gz'
            if self.compress and Path(compressed_path).exists():
                self.logger.debug(f"从压缩文件加载: {compressed_path}")
                with gzip.open(compressed_path, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                self.logger.info(f"从JSON文件加载: {full_path}")
                with open(full_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            self.logger.info(f"数据加载成功: {path}")
            return data
            
        except FileNotFoundError as e:
            self.logger.debug(f"文件不存在: {str(e)}")
            raise StorageReadError(f"文件不存在: {str(e)}")
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {str(e)}")
            raise StorageReadError(f"JSON解析失败: {str(e)}")
        except Exception as e:
            self.logger.error(f"加载数据失败: {str(e)}")
            raise StorageReadError(f"加载数据失败: {str(e)}")
    
    async def delete(self, path: str) -> bool:
        """
        删除文件
        
        Args:
            path: 相对于base_dir的路径
            
        Returns:
            bool: 是否删除成功
        """
        try:
            full_path = self.base_dir / path
            self.logger.debug(f"准备删除文件: {full_path}")
            
            # 检查并删除原始文件
            if full_path.exists():
                full_path.unlink()
                self.logger.debug(f"删除原始文件: {full_path}")
            
            # 检查并删除压缩文件
            compressed_path = Path(str(full_path) + '.gz')
            if compressed_path.exists():
                compressed_path.unlink()
                self.logger.debug(f"删除压缩文件: {compressed_path}")
            
            self.logger.info(f"文件删除成功: {path}")
            return True
            
        except Exception as e:
            self.logger.error("删除文件失败", exc_info=True)
            return False
    
    async def exists(self, path: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            path: 相对于base_dir的路径
            
        Returns:
            bool: 文件是否存在
        """
        full_path = self.base_dir / path
        compressed_path = Path(str(full_path) + '.gz')
        return full_path.exists() or compressed_path.exists()
    
    def _check_disk_space(self, data: Any, min_free_space: int = 100*1024*1024) -> bool:
        """
        检查磁盘空间是否足够
        
        Args:
            data: 要存储的数据
            min_free_space: 最小剩余空间(bytes)，默认100MB
            
        Returns:
            bool: 空间是否足够
        """
        try:
            # 获取数据大小估计值
            data_size = len(json.dumps(data, ensure_ascii=False).encode('utf-8'))
            
            # 获取存储目录所在磁盘的剩余空间
            free_space = shutil.disk_usage(self.base_dir).free
            
            self.logger.debug(f"数据大小: {data_size/1024/1024:.2f}MB, 剩余空间: {free_space/1024/1024:.2f}MB")
            
            return free_space > (data_size + min_free_space)
        except Exception as e:
            self.logger.warning(f"检查磁盘空间失败: {str(e)}")
            return True  # 如果检查失败，默认认为空间足够

class StorageManager:
    """存储管理器，提供统一的存储接口"""
    
    def __init__(self, storage_config: Dict[str, Any]):
        """
        初始化存储管理器
        
        Args:
            storage_config: 存储配置
                {
                    'type': 'file',  # 存储类型
                    'base_dir': 'storage',  # 基础目录
                    'compress': True,  # 是否压缩
                    'backup': True,  # 是否备份
                    'max_backups': 3,  # 最大备份数
                }
        """
        self.config = storage_config    
        setup_logger()
        self.logger = get_logger(name=__name__, site_id="Storage")
        
        # 初始化存储后端
        if storage_config['type'] == 'file':
            self.storage = FileStorage(
                storage_config['base_dir'],
                storage_config.get('compress', True)
            )
        else:
            raise ValueError(f"不支持的存储类型: {storage_config['type']}")
        
        self.logger.info(f"存储管理器初始化完成: {storage_config}")
    
    async def save(self, data: Any, path: str, backup: bool = None) -> bool:
        """
        保存数据
        
        Args:
            data: 要保存的数据
            path: 存储路径
            backup: 是否创建备份，默认使用配置值
            
        Returns:
            bool: 是否保存成功
        """
        try:
            self.logger.info(f"开始保存数据: {path}")
            
            # 确定是否需要备份
            should_backup = backup if backup is not None else self.config.get('backup', False)
            
            # 如果需要备份且文件已存在，创建备份
            if should_backup and await self.storage.exists(path):
                await self._create_backup(path)
            
            # 保存数据
            success = await self.storage.save(data, path)
            
            # 如果配置了最大备份数，清理旧备份
            if should_backup and success:
                await self._cleanup_old_backups(path)
            
            return success
            
        except Exception as e:
            self.logger.error("保存数据失败", exc_info=True)
            raise
    
    async def load(self, path: str, fallback_to_backup: bool = True) -> Optional[Any]:
        """
        加载数据
        
        Args:
            path: 存储路径
            fallback_to_backup: 加载失败时是否尝试从备份加载
            
        Returns:
            Optional[Any]: 加载的数据，如果文件不存在且没有备份则返回None
        """
        try:
            self.logger.debug(f"开始加载数据: {path}")
            return await self.storage.load(path)
        except StorageReadError as e:
            if "文件不存在" in str(e):
                if fallback_to_backup:
                    self.logger.debug("文件不存在，尝试从备份加载")
                    try:
                        return await self._load_from_backup(path)
                    except StorageReadError as backup_error:
                        if "没有可用的备份" in str(backup_error):
                            self.logger.debug("没有找到文件或备份")
                            return None
                        raise backup_error
                else:
                    self.logger.debug("文件不存在且不尝试从备份加载")
                    return None
            raise
        except Exception as e:
            self.logger.error(f"加载数据时发生未知错误: {str(e)}")
            raise
    
    async def _create_backup(self, path: str) -> bool:
        """创建数据备份"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{path}.{timestamp}.bak"
            
            self.logger.debug(f"创建备份: {backup_path}")
            
            # 加载原始数据并保存为备份
            data = await self.storage.load(path)
            return await self.storage.save(data, backup_path)
            
        except Exception as e:
            self.logger.error(f"创建备份失败: {str(e)}")
            return False
    
    async def _load_from_backup(self, path: str) -> Any:
        """从最新的备份加载数据"""
        try:
            # 获取所有备份文件
            base_path = Path(path)
            backup_pattern = f"{base_path.name}.*.bak"
            backup_dir = self.storage.base_dir / base_path.parent
            
            # 确保备份目录存在
            if not backup_dir.exists():
                raise StorageReadError("没有可用的备份")
            
            backup_files = sorted(
                backup_dir.glob(backup_pattern),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            if not backup_files:
                raise StorageReadError("没有可用的备份")
            
            # 加载最新的备份
            latest_backup = backup_files[0]
            self.logger.debug(f"从备份加载数据: {latest_backup}")
            return await self.storage.load(str(latest_backup.relative_to(self.storage.base_dir)))
            
        except Exception as e:
            self.logger.warning(f"从备份加载失败: {str(e)}")
            raise StorageReadError(str(e))
    
    async def _cleanup_old_backups(self, path: str) -> None:
        """清理旧的备份文件"""
        try:
            max_backups = self.config.get('max_backups', 3)
            base_path = Path(path)
            backup_pattern = f"{base_path.name}.*.bak"
            
            # 获取所有备份文件
            backup_files = sorted(
                base_path.parent.glob(backup_pattern),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            # 删除超出数量的旧备份
            for backup_file in backup_files[max_backups:]:
                self.logger.debug(f"删除旧备份: {backup_file}")
                await self.storage.delete(str(backup_file.relative_to(self.storage.base_dir)))
                
        except Exception as e:
            self.logger.warning(f"清理旧备份失败: {str(e)}")