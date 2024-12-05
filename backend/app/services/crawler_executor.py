import sys
import os
import asyncio
import importlib.util
from typing import Dict, Any, Optional, Callable, Coroutine
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.task import Task, TaskStatus
from app.services.logger import TaskLogger

class CrawlerExecutor:
    def __init__(self, db: AsyncSession, task: Task):
        self.db = db
        self.task = task
        self.crawler_path = os.path.abspath(os.path.join("..", "Crawler_py"))
        self.logger = TaskLogger(db, task.task_id)
        
    async def execute(self):
        """执行爬虫任务"""
        try:
            # 更新任务状态为运行中
            self.task.status = TaskStatus.RUNNING
            await self.db.commit()
            await self.logger.info(f"Starting crawler task: {self.task.crawler_id}")
            
            # 添加爬虫目录到Python路径
            if self.crawler_path not in sys.path:
                sys.path.append(self.crawler_path)
                await self.logger.debug(f"Added crawler path to sys.path: {self.crawler_path}")
            
            # 导入爬虫主模块
            spec = importlib.util.spec_from_file_location(
                "main",
                os.path.join(self.crawler_path, "src", "main.py")
            )
            if spec is None or spec.loader is None:
                raise ImportError("Cannot load crawler module")
            
            crawler_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(crawler_module)
            await self.logger.debug("Successfully loaded crawler module")
            
            # 执行爬虫任务
            await self.logger.info("Executing crawler task")
            result = await crawler_module.main()
            
            # 更新任务状态为完成
            self.task.status = TaskStatus.COMPLETED
            self.task.result = result
            await self.db.commit()
            await self.logger.info("Task completed successfully")
            
        except Exception as e:
            # 更新任务状态为失败
            error_message = str(e)
            self.task.status = TaskStatus.FAILED
            self.task.error = error_message
            await self.db.commit()
            await self.logger.error(f"Task failed: {error_message}")
            raise

class CrawlerExecutorManager:
    _running_tasks: Dict[str, asyncio.Task] = {}
    _task_events: Dict[str, asyncio.Event] = {}

    @classmethod
    def get_running_tasks_count(cls) -> int:
        """获取当前运行中的任务数量"""
        return len(cls._running_tasks)

    @classmethod
    def is_task_running(cls, task_id: str) -> bool:
        """检查任务是否正在运行"""
        return task_id in cls._running_tasks and not cls._running_tasks[task_id].done()

    @classmethod
    async def start_task(
        cls,
        db: AsyncSession,
        task: Task,
        crawler_func: Callable[[str, dict, str, AsyncSession], Coroutine[Any, Any, Any]]
    ):
        """启动新的爬虫任务"""
        logger = TaskLogger(db, task.task_id)
        
        # 创建取消事件
        cancel_event = asyncio.Event()
        cls._task_events[task.task_id] = cancel_event
        
        try:
            # 更新任务状态为运行中
            task.status = TaskStatus.RUNNING
            task.created_at = datetime.utcnow()
            await db.commit()
            
            # 创建异步任务
            async def wrapped_task():
                try:
                    # 检查取消事件
                    if cancel_event.is_set():
                        return
                    
                    # 执行爬虫任务
                    result = await crawler_func(
                        task.crawler_id,
                        task.config,
                        task.task_id,
                        db
                    )
                    
                    # 更新任务状态为成功
                    task.status = TaskStatus.SUCCESS
                    task.completed_at = datetime.utcnow()
                    task.result = result
                    await db.commit()
                    
                except Exception as e:
                    # 记录错误并更新任务状态
                    await logger.error(f"Task execution failed: {str(e)}")
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    task.completed_at = datetime.utcnow()
                    await db.commit()
                    raise
                finally:
                    # 清理任务记录
                    cls._running_tasks.pop(task.task_id, None)
                    cls._task_events.pop(task.task_id, None)
            
            # 启动任务
            task_obj = asyncio.create_task(wrapped_task())
            cls._running_tasks[task.task_id] = task_obj
            
            await logger.info("Task started successfully")
            
        except Exception as e:
            await logger.error(f"Failed to start task: {str(e)}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            await db.commit()
            raise

    @classmethod
    async def cancel_task(cls, task_id: str) -> bool:
        """取消运行中的任务"""
        if task_id not in cls._running_tasks:
            return False
        
        # 设置取消事件
        if task_id in cls._task_events:
            cls._task_events[task_id].set()
        
        # 取消任务
        task = cls._running_tasks[task_id]
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # 清理任务记录
        cls._running_tasks.pop(task_id, None)
        cls._task_events.pop(task_id, None)
        
        return True 