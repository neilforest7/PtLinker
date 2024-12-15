import asyncio
import os
import sys
from datetime import datetime
from multiprocessing import Process
from pathlib import Path
from typing import Dict, Optional

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
            try:
                # 初始化日志
                setup_logger(is_subprocess=True)
                logger = get_logger(name=__name__, site_id=self.site_id, is_subprocess=True)
                logger.debug("子进程启动")
                
                # 初始化数据库连接
                from core import database
                db = await anext(database.get_db())
                
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
                
            except Exception as e:
                logger.error(f"任务执行失败: {str(e)}")
                logger.debug("错误详情:", exc_info=True)
                if 'db' in locals():
                    stmt = select(Task).where(Task.task_id == self.task_id)
                    result = await db.execute(stmt)
                    task = result.scalar_one_or_none()
                    if task:
                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                        await db.commit()
                raise
            finally:
                if 'db' in locals():
                    await db.close()
        
        # 运行异步任务
        asyncio.run(_run())


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
                    # 更新现有任务
                    task_update = TaskUpdate(
                        task_id=task.task_id,
                        status=TaskStatus.READY,
                        updated_at=datetime.now()
                    )
                    for key, value in task_update.model_dump(exclude_unset=True).items():
                        if key == 'status':
                            value = TaskStatus(value.value)
                        setattr(db_task, key, value)
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
                
                # 更新任务状态
                task_update = TaskUpdate(
                    task_id=task.task_id,
                    status=TaskStatus.RUNNING,
                    updated_at=datetime.now(),
                    task_metadata={"pid": process.pid}
                )
                for key, value in task_update.model_dump(exclude_unset=True).items():
                    if key == 'status':
                        value = TaskStatus(value.value)
                    setattr(db_task, key, value)
                await db.commit()
                await db.refresh(db_task)
                
                self.logger.info(f"任务 {task.task_id} 启动成功 (PID: {process.pid})")
                return TaskResponse.model_validate(db_task)
                
            except Exception as e:
                self.logger.error(f"启动任务 {task.task_id} 失败: {str(e)}")
                self.logger.debug("错误详情:", exc_info=True)
                if 'db_task' in locals():
                    db_task.status = TaskStatus.FAILED
                    db_task.error = str(e)
                    await db.commit()
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
                
                del self._processes[task_id]
                del self._status[task_id]
                
                self.logger.info(f"任务 {task_id} 已停止")
                return True
                
            except Exception as e:
                self.logger.error(f"停止任务 {task_id} 失败: {str(e)}")
                return False
    
    async def check_task_status(self, task_id: str) -> Optional[Dict]:
        """��查任务状态"""
        if task_id not in self._processes:
            return None
            
        process = self._processes[task_id]
        status = self._status[task_id].copy()
        status.update({
            "is_alive": process.is_alive(),
            "exit_code": process.exitcode if not process.is_alive() else None
        })
        return status
    
    async def cleanup(self):
        """清理所有进程"""
        async with self._lock:
            for task_id in list(self._processes.keys()):
                await self.stop_task(task_id)


# 全局进程管理器实例
process_manager = ProcessManager()