from datetime import datetime
import json
import os
from typing import Any, Dict, Optional, Tuple

import aiofiles
from models.storage import BrowserState, CrawlerError, SiteRunStatus, SitesStatusSummary, StorageReadError
from utils.logger import get_logger
from storage.browser_state_manager import BrowserStateManager
from storage.storage_backend import FileStorage, StoragePaths


class SiteStatusManager:
    """站点状态管理器"""
    
    def __init__(self, storage: FileStorage, paths: StoragePaths):
        self.storage = storage
        self.paths = paths
        self.logger = get_logger(__name__, site_id='SiteStat')
        self.browser_manager = None
        
    def set_browser_manager(self, browser_manager: BrowserStateManager):
        """设置浏览器状态管理器"""
        self.browser_manager = browser_manager
    
    async def update_site_status(self, site_id: str) -> None:
        """更新单个站点状态"""
        try:
            latest_task, latest_data, task_data, last_error = await self._get_latest_task_info(site_id)
            
            status = SiteRunStatus(
                site_id=site_id,
                last_run_time=int(datetime.now().timestamp()),
                browser_state=await self.browser_manager.restore_state(site_id) or BrowserState(),
                last_task=latest_task,
                last_data_file=latest_data,
                last_task_data=task_data,
                last_error=last_error
            )
            
            # 读取现有汇总文件
            summary_path = self.paths.get_relative_path(self.paths.get_summary_path())
            try:
                summary_data = await self.storage.load(summary_path)
                summary = SitesStatusSummary(**summary_data)
            except (StorageReadError, FileNotFoundError):
                summary = SitesStatusSummary()
            
            # 更新状态
            summary.sites[site_id] = status
            summary.last_updated = int(datetime.now().timestamp())
            
            # 保存汇总文件
            await self.storage.save(summary.model_dump(), summary_path)
            self.logger.debug(f"已更新站点 {site_id} 的状态")
            
        except Exception as e:
            self.logger.error(f"Error updating site status for {site_id}: {str(e)}")
            raise
    
    async def get_all_sites_status(self, force_scan: bool = False) -> SitesStatusSummary:
        """获取所有站点的状态汇总"""
        try:
            summary_path = self.paths.get_relative_path(self.paths.get_summary_path())
            
            # 如果不强制扫描，尝试读取现有汇总文件
            if not force_scan:
                try:
                    summary_data = await self.storage.load(summary_path)
                    return SitesStatusSummary(**summary_data)
                except (StorageReadError, FileNotFoundError):
                    pass
            
            # 强制扫描或读取失败时，重新扫描所有站点
            self.logger.info("开始扫描所有站点状态...")
            state_dir = self.paths.get_state_dir()
            if not os.path.exists(state_dir):
                self.logger.warning("状态目录不存在")
                return SitesStatusSummary()
            
            # 遍历state目录下的所有站点目录
            for site_id in os.listdir(state_dir):
                site_dir = state_dir / site_id
                if not os.path.isdir(site_dir):
                    continue
                
                try:
                    await self.update_site_status(site_id)
                except Exception as e:
                    self.logger.error(f"Error scanning site {site_id}: {str(e)}")
            
            # 读取更新后的汇总文件
            try:
                summary_data = await self.storage.load(summary_path)
                return SitesStatusSummary(**summary_data)
            except (StorageReadError, FileNotFoundError):
                return SitesStatusSummary()
            
        except Exception as e:
            self.logger.error(f"获取站点状态失败: {str(e)}")
            raise

    async def get_site_status(self, site_id: str) -> Optional[SiteRunStatus]:
        """获取单个站点的状态信息"""
        try:
            # 1. 获取浏览器状态
            browser_state = await self._get_browser_state(site_id)
            
            # 2. 获取最新任务信息
            latest_task, latest_data, task_data, last_error = await self._get_latest_task_info(site_id)
            
            # 3. 获取站点状态目录的修改时间作为最后运行时间
            site_state_dir = self.paths.get_site_state_dir(site_id)
            try:
                last_run_time = int(site_state_dir.stat().st_mtime)
            except:
                last_run_time = int(datetime.now().timestamp())
            
            
            
            # 4. 构建站点状态对象
            status = SiteRunStatus(
                site_id=site_id,
                last_run_time=last_run_time,
                browser_state=browser_state,
                last_task=latest_task,
                last_data_file=latest_data,
                last_task_data=task_data,
                last_error=last_error,
                stats=await self._get_site_stats(site_id)
            )
            
            return status
            
        except Exception as e:
            self.logger.error(f"获取站点 {site_id} 状态失败: {str(e)}")
            return None
    
    async def _get_browser_state(self, site_id: str) -> BrowserState:
        """获取浏览器状态
        
        此方法已弃用，请使用BrowserStateManager
        """
        try:
            state = await self.browser_manager.restore_state(site_id)
            return state if state else BrowserState()
        except Exception as e:
            self.logger.error(f"获取站点 {site_id} 的浏览器状态失败: {str(e)}")
            return BrowserState()
            
    async def _get_latest_task_info(self, site_id: str) -> Tuple[Optional[str], Optional[str], Optional[Dict], Optional[CrawlerError]]:
        """获取最新任务信息"""
        try:
            task_dir = self.paths.get_site_tasks_dir(site_id)
            if not os.path.exists(task_dir):
                return None, None, None, None
            
            # 获取所有任务目录
            task_dirs = [d for d in os.listdir(task_dir) if os.path.isdir(os.path.join(task_dir, d))]
            if not task_dirs:
                return None, None, None, None
            
            latest_task = sorted(task_dirs)[-1]
            latest_task_dir = task_dir / latest_task
            
            # 查找数据文件或错误文件
            data_files = [f for f in os.listdir(latest_task_dir) if f.endswith('.json') and not f.endswith('_error.json')]
            error_files = [f for f in os.listdir(latest_task_dir) if f.endswith('_error.json')]
            
            if data_files:
                latest_data = sorted(data_files)[-1]
                data_path = latest_task_dir / latest_data
                # 读取数据文件内容
                async with aiofiles.open(data_path, 'r', encoding='utf-8') as f:
                    task_data = json.loads(await f.read())
                return latest_task, latest_data, task_data, None
                
            elif error_files:
                latest_error = sorted(error_files)[-1]
                error_path = latest_task_dir / latest_error
                async with aiofiles.open(error_path, 'r', encoding='utf-8') as f:
                    error_content = await f.read()
                    error_data = json.loads(error_content)
                    return latest_task, None, None, CrawlerError(**error_data)
            
            return latest_task, None, None, None
            
        except Exception as e:
            self.logger.error(f"Error getting latest task info for {site_id}: {str(e)}")
            return None, None, None, None

    async def _get_site_stats(self, site_id: str) -> Dict[str, Any]:
        """获取站点统计信息"""
        try:
            stats = {
                'total_tasks': 0,
                'total_data_files': 0,
                'total_errors': 0,
                'data_size_bytes': 0
            }
            
            # 统计任务目录
            tasks_dir = self.paths.get_site_tasks_dir(site_id)
            if tasks_dir.exists():
                # 统计任务文件数量
                stats['total_tasks'] = len(list(tasks_dir.glob('**/*.json')))
                
                # 统计数据文件
                data_files = list(tasks_dir.glob('**/*_data.json'))
                stats['total_data_files'] = len(data_files)
                
                # 统计数据大小
                for file in data_files:
                    stats['data_size_bytes'] += file.stat().st_size
                    
            # 统计错误文件
            error_files = list(tasks_dir.glob('**/*_error.json'))
            stats['total_errors'] = len(error_files)
            
            return stats
            
        except Exception as e:
            self.logger.warning(f"获取站点 {site_id} 统计信息失败: {str(e)}")
            return {}

