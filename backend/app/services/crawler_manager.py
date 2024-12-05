import os
import sys
import json
import importlib.util
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.models.task import Task, TaskStatus
from app.services.crawler_executor import CrawlerExecutorManager

settings = get_settings()

class CrawlerManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.config_path = settings.CRAWLER_CONFIG_PATH
        self.storage_path = settings.CRAWLER_STORAGE_PATH
        
        # 获取项目根目录（PtLinker）
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        crawler_src_path = os.path.join(project_root, "crawler_py", "src")
        
        if crawler_src_path not in sys.path:
            sys.path.insert(0, crawler_src_path)
            print(f"Added to sys.path: {crawler_src_path}")

    def _load_crawler_module(self, crawler_id: str) -> Any:
        """加载爬虫配置模块"""
        try:
            # 直接导入模块
            return importlib.import_module(f"crawlers.site_config.{crawler_id}")
        except Exception as e:
            print(f"Error importing {crawler_id}: {str(e)}")
            print(f"sys.path: {sys.path}")
            raise ImportError(f"Cannot load crawler module {crawler_id}: {str(e)}")

    def _list_crawler_configs(self) -> List[Dict[str, Any]]:
        """列出所有爬虫配置"""
        configs = []
        if not os.path.exists(self.config_path):
            print(f"Config path not found: {self.config_path}")
            return configs

        for filename in os.listdir(self.config_path):
            if not filename.endswith('.py') or filename.startswith('__'):
                continue
                
            crawler_id = filename.replace('.py', '')
            try:
                module = self._load_crawler_module(crawler_id)
                site_config = getattr(module, 'SITE_CONFIG', {})
                configs.append({
                    "crawler_id": crawler_id,
                    "site_id": crawler_id,
                    "name": site_config.get('name', crawler_id),
                    "description": site_config.get('description', ''),
                    "config_schema": getattr(module, 'CONFIG_SCHEMA', {}),
                    "default_config": getattr(module, 'DEFAULT_CONFIG', {})
                })
            except Exception as e:
                print(f"Error loading config for {crawler_id}: {str(e)}")
                continue
                
        return configs

    def _load_site_data(self, site_id: str) -> Dict[str, Any]:
        """加载站点相关数据"""
        result = {
            "summary": None,
            "browser_state": None,
            "latest_result": None
        }
        
        # 加载站点摘要
        summary_file = os.path.join(self.storage_path, "state", "sites_summary.json")
        if os.path.exists(summary_file):
            with open(summary_file, 'r', encoding='utf-8') as f:
                summaries = json.load(f)
                result["summary"] = summaries.get(site_id)
        
        # 加载浏览器状态
        state_file = os.path.join(self.storage_path, "state", site_id, "browser_state.json")
        if os.path.exists(state_file):
            with open(state_file, 'r', encoding='utf-8') as f:
                result["browser_state"] = json.load(f)
        
        return result

    def _load_latest_task_data(self, crawler_id: str) -> Optional[Dict[str, Any]]:
        """加载最新任务数据"""
        task_dir = os.path.join(self.storage_path, "tasks", crawler_id)
        if not os.path.exists(task_dir):
            return None
            
        task_dirs = sorted([d for d in os.listdir(task_dir) if os.path.isdir(os.path.join(task_dir, d))], reverse=True)
        if not task_dirs:
            return None
            
        latest_dir = os.path.join(task_dir, task_dirs[0])
        data_files = sorted([f for f in os.listdir(latest_dir) if f.startswith("data_") and f.endswith(".json")], reverse=True)
        if not data_files:
            return None
            
        with open(os.path.join(latest_dir, data_files[0]), 'r', encoding='utf-8') as f:
            return json.load(f)

    def _process_user_stats(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """处理用户统计数据，确保所有必需字段都存在"""
        if not stats:
            return None
            
        # 创建新的字典以避免修改原始数据
        processed_stats = dict(stats)
            
        # 计算分享率
        if 'ratio' not in processed_stats and 'upload' in processed_stats and 'download' in processed_stats:
            upload = float(processed_stats['upload'])
            download = float(processed_stats['download'])
            # 当下载量为0时，设置一个足够大的有限数
            processed_stats['ratio'] = upload / download if download > 0 else 999999.99
            
        # 确保所有数值字段都是有限的
        for key in ['ratio', 'upload', 'download', 'bonus', 'seeding_score', 
                    'bonus_per_hour', 'seeding_size']:
            if key in processed_stats:
                value = float(processed_stats[key])
                if not isinstance(value, (int, float)) or not abs(value) < float('inf'):
                    processed_stats[key] = 0.0
                    
        return processed_stats

    async def get_crawler_status(self, crawler_id: str) -> Dict[str, Any]:
        """获取爬虫状态信息"""
        module = self._load_crawler_module(crawler_id)
        site_config = getattr(module, 'SITE_CONFIG', {})
        site_id = crawler_id
        site_data = self._load_site_data(site_id)
        latest_data = self._load_latest_task_data(crawler_id)
        
        # 处理用户统计数据
        processed_stats = self._process_user_stats(latest_data)
        
        # 获取任务统计
        total_tasks = await self.db.execute(
            select(func.count()).select_from(Task).filter(Task.crawler_id == crawler_id)
        )
        total = total_tasks.scalar() or 0
        
        success_tasks = await self.db.execute(
            select(func.count()).select_from(Task).filter(
                Task.crawler_id == crawler_id,
                Task.status == TaskStatus.COMPLETED
            )
        )
        success = success_tasks.scalar() or 0
        
        # 获取最后运行的任务
        last_task = await self.db.execute(
            select(Task).filter(Task.crawler_id == crawler_id)
            .order_by(Task.created_at.desc()).limit(1)
        )
        last_task = last_task.scalar_one_or_none()
        
        # 计算运行中的任务数
        running_tasks = sum(1 for task_id in CrawlerExecutorManager._running_tasks if task_id.startswith(crawler_id))
        
        browser_state = site_data.get("browser_state", {})
        login_state = browser_state.get("login_state", {})
        
        site_status = {
            "site_id": site_id,
            "name": site_config.get('name', site_id),
            "status": "online" if login_state.get("is_logged_in") else "offline",
            "last_check_time": datetime.fromtimestamp(login_state.get("last_login_time", 0)) if login_state else None,
            "user_stats": processed_stats,
            "browser_state": browser_state
        }
        
        return {
            "crawler_id": crawler_id,
            "site_id": site_id,
            "status": "running" if running_tasks > 0 else "idle",
            "running_tasks": running_tasks,
            "total_tasks": total,
            "last_run": last_task.created_at if last_task else None,
            "success_rate": (success / total * 100) if total > 0 else 0,
            "site_status": site_status
        }

    async def list_crawlers(self) -> Dict[str, Any]:
        """获取爬虫列表"""
        configs = self._list_crawler_configs()
        return {
            "crawlers": configs,
            "total": len(configs)
        }

    async def get_crawler_detail(self, crawler_id: str) -> Dict[str, Any]:
        """获取爬虫详细信息"""
        module = self._load_crawler_module(crawler_id)
        site_config = getattr(module, 'SITE_CONFIG', {})
        status = await self.get_crawler_status(crawler_id)
        latest_data = self._load_latest_task_data(crawler_id)
        
        return {
            "crawler_id": crawler_id,
            "site_id": crawler_id,
            "name": site_config.get('name', crawler_id),
            "description": site_config.get('description', ''),
            "config_schema": getattr(module, 'CONFIG_SCHEMA', {}),
            "default_config": getattr(module, 'DEFAULT_CONFIG', {}),
            "status": status,
            "latest_result": {
                "task_id": f"{crawler_id}-latest",
                "crawler_id": crawler_id,
                "site_id": crawler_id,
                "execution_time": datetime.now(),
                "user_stats": latest_data,
                "browser_state": self._load_site_data(crawler_id).get("browser_state")
            } if latest_data else None
        }

    def validate_config(self, crawler_id: str, config: Dict[str, Any]) -> bool:
        """验证爬虫配置"""
        try:
            module = self._load_crawler_module(crawler_id)
            validate_func = getattr(module, 'validate_config', None)
            if validate_func:
                return validate_func(config)
            return True
        except Exception:
            return False
