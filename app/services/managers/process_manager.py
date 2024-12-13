import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import psutil
from core import database
from core.logger import get_logger, setup_logger
from models.models import Task, TaskStatus
from schemas.sitesetup import SiteSetup
from schemas.task import TaskCreate, TaskResponse, TaskUpdate
from services.crawler.site_crawler import SiteCrawler
from services.managers.setting_manager import settings
from services.managers.site_manager import SiteManager
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def get_site_manager():
    return SiteManager.get_instance()

class ProcessManager:
    def __init__(self):
        self._processes: Dict[str, psutil.Process] = {}  # task_id -> process
        self._status: Dict[str, Dict] = {}  # task_id -> status
        self._lock = asyncio.Lock()
        self._queue_manager = None
        self._db = None
        setup_logger()
        self.logger = get_logger(name=__name__, site_id="process_manager")
        
    async def initialize(self, queue_manager, db: AsyncSession) -> None:
        """初始化进程管理器
        
        Args:
            queue_manager: 队列管理器实例
            db: 数据库会话
        """
        self._queue_manager = queue_manager
        self._db = db
        self.logger.info("Process manager initialized")
        
    async def start_crawlertask(self, task: TaskCreate, db: AsyncSession) -> Optional[TaskResponse]:
        """启动任务进程
        
        Args:
            task: 任务创建模型
            db: 数据库会话
        """
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
                    # 如果任务已存在，更新状态
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
                    # 如果任务不存在，创建新任务
                    db_task = Task(
                        task_id=task.task_id,
                        site_id=task.site_id,
                        status=TaskStatus.READY,
                        task_metadata=task.task_metadata
                    )
                    db.add(db_task)
                
                await db.commit()
                await db.refresh(db_task)
                
                # 准备进程环境
                env = os.environ.copy()
                env.update({
                    "SITE_ID": task.site_id,
                    "TASK_ID": task.task_id,
                    "PYTHONPATH": str(Path(__file__).parent.parent.parent.parent),
                    "LOG_LEVEL": "DEBUG",
                    "DATABASE_URL": database.DATABASE_URL,
                })
                
                # 获取站点配置
                site_setup = await get_site_manager().get_site_setup(task.site_id)
                if not site_setup:
                    raise ValueError(f"站点 {task.site_id} 配置不存在")
                
                # 启动进程
                process = psutil.Popen(
                    [
                        sys.executable,
                        "-c",
                        f"""
import asyncio
from services.crawler.site_crawler import SiteCrawler
from schemas.sitesetup import SiteSetup
import json

async def run_crawler():
    # 使用新的序列化方法
    site_setup = SiteSetup.from_json('{site_setup.to_json()}')
    crawler = SiteCrawler(site_setup)
    await crawler.start()

asyncio.run(run_crawler())
                        """,
                    ],
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    text=True,
                )
                
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
                
                # 启动日志监控
                asyncio.create_task(self._monitor_process_output(task.task_id, process))
                
                self.logger.info(f"任务 {task.task_id} 启动成功 (PID: {process.pid})")
                return TaskResponse.model_validate(db_task)
                
            except Exception as e:
                self.logger.error(f"启动任务 {task.task_id} 失败: {str(e)}")
                if 'db_task' in locals():
                    db_task.status = TaskStatus.FAILED
                    db_task.error = str(e)
                    await db.commit()
                return None
    
    async def _monitor_process_output(self, task_id: str, process: psutil.Process):
        """监控进程输出"""
        try:
            while process.is_running():
                # 读取进程输出
                stdout = await process.stdout.readline()
                if stdout:
                    self.logger.info(f"[Task {task_id}] {stdout.strip()}")
                
                stderr = await process.stderr.readline()
                if stderr:
                    self.logger.error(f"[Task {task_id}] {stderr.strip()}")
                
                await asyncio.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"监控任务输出失败 [{task_id}]: {str(e)}")
    
    async def stop_crawlertask(self, task_id: str, db: AsyncSession) -> bool:
        """停止任务进程"""
        async with self._lock:
            if task_id not in self._processes:
                self.logger.warning(f"任务 {task_id} 未运行")
                return False
            
            try:
                process = self._processes[task_id]
                # 首先尝试优雅地终止进程
                process.terminate()
                try:
                    process.wait(timeout=5)
                except psutil.TimeoutExpired:
                    # 如果超时，强制终止
                    process.kill()
                
                # 更新任务状态
                stmt = select(Task).where(Task.task_id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if task:
                    task_update = TaskUpdate(
                        status=TaskStatus.CANCELLED,
                        completed_at=datetime.now(),
                        error="Task cancelled by user"
                    )
                    for key, value in task_update.model_dump(exclude_unset=True).items():
                        setattr(task, key, value)
                    await db.commit()
                
                # 清理状态
                del self._processes[task_id]
                del self._status[task_id]
                
                self.logger.info(f"任务 {task_id} 已停止")
                return True
                
            except Exception as e:
                self.logger.error(f"停止任务 {task_id} 失败: {str(e)}")
                return False
    
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        if task_id not in self._processes:
            return None
            
        try:
            process = self._processes[task_id]
            status = self._status[task_id]
            
            return {
                "task_id": task_id,
                "site_id": status["site_id"],
                "pid": process.pid,
                "cpu_percent": process.cpu_percent(),
                "memory_percent": process.memory_percent(),
                "start_time": status["start_time"],
                "script_path": status["script_path"],
                "is_running": process.is_running(),
                "status": "running" if process.is_running() else "stopped"
            }
        except Exception as e:
            self.logger.error(f"获取任务 {task_id} 状态失败: {str(e)}")
            return None
    
    async def cleanup(self, db: AsyncSession):
        """清理所有进程"""
        async with self._lock:
            for task_id in list(self._processes.keys()):
                await self.stop_task(task_id, db)
                
    async def monitor_processes(self, db: AsyncSession):
        """监控所有进程状态"""
        while True:
            for task_id, process in list(self._processes.items()):
                try:
                    if not process.is_running():
                        self.logger.warning(f"任务 {task_id} 异常退出")
                        # 更新任务状态
                        stmt = select(Task).where(Task.task_id == task_id)
                        result = await db.execute(stmt)
                        task = result.scalar_one_or_none()
                        
                        if task and task.status not in [TaskStatus.SUCCESS, TaskStatus.CANCELLED]:
                            task_update = TaskUpdate(
                                status=TaskStatus.FAILED,
                                completed_at=datetime.now(),
                                error="Process terminated unexpectedly"
                            )
                            for key, value in task_update.model_dump(exclude_unset=True).items():
                                setattr(task, key, value)
                            await db.commit()
                            
                except Exception as e:
                    self.logger.error(f"监控任务 {task_id} 失败: {str(e)}")
            
            await asyncio.sleep(5)  # 每5秒检查一次

# 全局进程管理器实例
process_manager = ProcessManager()