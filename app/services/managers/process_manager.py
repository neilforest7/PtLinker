import asyncio
import os
import sys
from datetime import datetime
from multiprocessing import Process
from pathlib import Path
from typing import Dict, Optional
import traceback

from services.managers.result_manager import ResultManager
from services.managers.setting_manager import SettingManager
from core.database import AsyncSession
from core.logger import get_logger, setup_logger
from models.models import Task, TaskStatus
from schemas.task import TaskCreate, TaskResponse, TaskUpdate
from services.crawler.site_crawler import SiteCrawler
from services.managers.site_manager import SiteManager
from services.managers.setting_manager import settings
from services.managers.browserstate_manager import BrowserStateManager
from sqlalchemy import select
from services.managers.task_status_manager import task_status_manager


class CrawlerProcess(Process):
    """爬虫进程类"""
    def __init__(self, site_id: str, task_id: str, log_dir: str):
        super().__init__()
        self.site_id = site_id
        self.task_id = task_id
        self.log_dir = log_dir
        
    def run(self):
        """进程运行入口"""
        # 设置环境变量
        os.environ.update({
            "SITE_ID": self.site_id,
            "TASK_ID": self.task_id,
            "LOG_DIR": self.log_dir,
            "LOG_FILE": f"task_{self.task_id}_%Y%m%d.log",
            "ERROR_LOG_FILE": f"error_{self.task_id}_%Y%m%d.log",
        })
        
        async def _run():
            db = None
            try:
                # 初始化日志
                setup_logger(is_subprocess=True)
                logger = get_logger(name=__name__, site_id=self.site_id, is_subprocess=True)
                logger.debug("子进程启动")
                
                # 初始化数据库连接
                from core import database
                db = await anext(database.get_db())
                
                # 更新任务状态为 PENDING
                await self._update_task_status(db, TaskStatus.PENDING, "任务初始化中")
                
                # 初始化所有管理器
                logger.debug("开始初始化管理器")
                
                # 1. 初始化 settings
                from services.managers.setting_manager import settings
                logger.debug("初始化 settings")
                await settings.initialize(db)
                
                # 2. 初始化 site manager
                logger.debug("初始化 site manager")
                site_manager = SiteManager.get_instance()
                await site_manager.initialize(db)
                
                # 3. 初始化 queue manager
                logger.debug("初始化 queue manager")
                from services.managers.queue_manager import queue_manager
                await queue_manager.initialize(max_concurrency=await settings.get_setting("crawler_max_concurrency"))
                
                # 4. 初始化 result manager
                logger.debug("初始化 result manager")
                result_manager = ResultManager.get_instance()
                await result_manager.initialize(db)
                
                # 5. 初始化 browserstate manager
                logger.debug("初始化 browserstate manager")
                browserstate_manager = BrowserStateManager.get_instance()
                await browserstate_manager.initialize(db)
                
                logger.debug("所有管理器初始化完成")
                
                # 更新任务状态为 RUNNING
                await self._update_task_status(db, TaskStatus.RUNNING, "开始执行任务")
                
                # 获取站点配置
                site_setup = await site_manager.get_site_setup(self.site_id)
                if not site_setup:
                    raise ValueError(f"站点 {self.site_id} 配置不存在")
                
                # 创建并启动爬虫
                logger.debug(f"创建爬虫实例: {site_setup.site_id}")
                crawler = SiteCrawler(site_setup=site_setup, task_id=self.task_id)
                logger.debug("开始爬虫任务")
                await crawler.start()
                logger.debug("爬虫任务完成")
                
                # 更新任务状态为 SUCCESS
                await self._update_task_status(db, TaskStatus.SUCCESS, "任务执行成功", 
                                            completed_at=datetime.now())
                
            except Exception as e:
                error_msg = str(e)
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc()
                }
                logger.error(f"任务执行失败: {error_msg}")
                logger.debug("错误详情:", exc_info=True)
                
                if db:
                    # 更新任务状态为 FAILED
                    await self._update_task_status(db, TaskStatus.FAILED, error_msg,
                                                completed_at=datetime.now(),
                                                error_details=error_details)
                raise
            finally:
                if db:
                    await db.close()
        
        # 运行异步任务
        asyncio.run(_run())
        
    async def _update_task_status(self, db: AsyncSession, status: TaskStatus, 
                                msg: Optional[str] = None,
                                completed_at: Optional[datetime] = None,
                                error_details: Optional[Dict] = None) -> None:
        """更新任务状态"""
        await task_status_manager.update_task_status(
            db=db,
            task_id=self.task_id,
            status=status,
            msg=msg,
            completed_at=completed_at,
            error_details=error_details,
            site_id=self.site_id
        )


class ProcessManager:
    """进程管理器"""
    def __init__(self):
        self._processes: Dict[str, CrawlerProcess] = {}  # task_id -> process
        self._status: Dict[str, Dict] = {}  # task_id -> status
        self._lock = asyncio.Lock()
        self._queue_manager = None
        self._db = None
        self.logger = get_logger(name=__name__, site_id="process_manager")
        
    async def initialize(self, queue_manager, db: AsyncSession) -> None:
        """初始化进程管理器"""
        self._queue_manager = queue_manager
        self._db = db
        self.logger.info("Process manager initialized")
        
    async def start_crawlertask(self, task: TaskCreate, db: AsyncSession) -> Optional[TaskResponse]:
        """启动任务进程"""
        async with self._lock:
            if task.task_id in self._processes:
                self.logger.warning(f"任务 {task.task_id} 已经在运行")
                return None
                
            try:
                # 检查任务是否存在
                stmt = select(Task).where(Task.task_id == task.task_id)
                result = await db.execute(stmt)
                db_task = result.scalar_one_or_none()
                
                if db_task:
                    # 更新任务状态为 READY
                    await self._update_task_status(db, task.task_id, TaskStatus.READY, "任务准备中")
                else:
                    # 创建新任务
                    db_task = Task(
                        task_id=task.task_id,
                        site_id=task.site_id,
                        status=TaskStatus.READY,
                        task_metadata=task.task_metadata
                    )
                    db.add(db_task)
                    await db.commit()
                    await db.refresh(db_task)
                
                # 构建日志路径
                log_path = str(Path(__file__).parent.parent.parent / 'logs' / 'tasks')
                
                # 创建并启动进程
                process = CrawlerProcess(
                    site_id=task.site_id,
                    task_id=task.task_id,
                    log_dir=log_path
                )
                process.start()
                
                # 存储进程信息
                self._processes[task.task_id] = process
                self._status[task.task_id] = {
                    "start_time": datetime.now(),
                    "pid": process.pid,
                    "site_id": task.site_id
                }
                
                # 更新任务状态为 RUNNING
                await self._update_task_status(
                    db, 
                    task.task_id, 
                    TaskStatus.RUNNING, 
                    "任务已启动",
                    task_metadata={"pid": process.pid}
                )
                
                self.logger.info(f"任务 {task.task_id} 启动成功 (PID: {process.pid})")
                return TaskResponse.model_validate(db_task)
                
            except Exception as e:
                error_msg = str(e)
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc()
                }
                self.logger.error(f"启动任务 {task.task_id} 失败: {error_msg}")
                self.logger.debug("错误详情:", exc_info=True)
                
                # 更新任务状态为 FAILED
                await self._update_task_status(
                    db,
                    task.task_id,
                    TaskStatus.FAILED,
                    error_msg,
                    datetime.now(),
                    error_details
                )
                return None
    
    async def stop_task(self, task_id: str) -> bool:
        """停止任务进程"""
        async with self._lock:
            if task_id not in self._processes:
                self.logger.warning(f"任务 {task_id} 不存在或已停止")
                return False
            
            try:
                process = self._processes[task_id]
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
                    if process.is_alive():
                        process.kill()
                        process.join()
                
                # 更新任务状态为 CANCELLED
                if self._db:
                    await self._update_task_status(
                        self._db,
                        task_id,
                        TaskStatus.CANCELLED,
                        "任务已手动停止",
                        datetime.now()
                    )
                
                del self._processes[task_id]
                del self._status[task_id]
                
                self.logger.info(f"任务 {task_id} 已停止")
                return True
                
            except Exception as e:
                self.logger.error(f"停止任务 {task_id} 失败: {str(e)}")
                return False
    
    async def check_task_status(self, task_id: str) -> Optional[Dict]:
        """检查任务状态"""
        if task_id not in self._processes:
            return None
            
        process = self._processes[task_id]
        status = self._status[task_id].copy()
        status.update({
            "is_alive": process.is_alive(),
            "exit_code": process.exitcode if not process.is_alive() else None
        })
        return status

    async def _update_task_status(self, db: AsyncSession, task_id: str, status: TaskStatus, 
                                msg: Optional[str] = None,
                                completed_at: Optional[datetime] = None,
                                error_details: Optional[Dict] = None,
                                task_metadata: Optional[Dict] = None) -> None:
        """更新任务状态"""
        await task_status_manager.update_task_status(
            db=db,
            task_id=task_id,
            status=status,
            msg=msg,
            completed_at=completed_at,
            error_details=error_details,
            task_metadata=task_metadata,
            site_id=self._status.get(task_id, {}).get("site_id")
        )
        
    async def cleanup(self):
        """清理所有进程"""
        async with self._lock:
            for task_id in list(self._processes.keys()):
                await self.stop_task(task_id)


# 全局进程管理器实例
process_manager = ProcessManager()