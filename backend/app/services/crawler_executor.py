import sys
import os
import asyncio
import importlib.util
from typing import Dict, Any, Optional, Callable, Coroutine
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.task import Task, TaskStatus
from app.services.logger import TaskLogger
from app.services.websocket_manager import manager
from app.core.logger import get_logger

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
    _logger = get_logger(service="crawler_executor")

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
        task_id = task.task_id
        logger_ctx = get_logger(task_id=task_id, crawler_id=task.crawler_id)
        
        # 创建取消事件
        cancel_event = asyncio.Event()
        cls._task_events[task_id] = cancel_event
        
        try:
            # 更新任务状态为运行中
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            await db.commit()
            
            # 通过WebSocket发送状态更新
            await manager.send_status(task_id, "running")
            logger_ctx.info("Starting crawler task")
            
            # 创建异步任务
            async def wrapped_task():
                try:
                    # 检查取消事件
                    if cancel_event.is_set():
                        return
                    
                    # 执行爬虫任务
                    logger_ctx.debug("Executing crawler function")
                    result = await crawler_func(
                        task.crawler_id,
                        task.config,
                        task_id,
                        db
                    )
                    
                    # 更新任务状态为成功
                    task.status = TaskStatus.SUCCESS
                    task.completed_at = datetime.utcnow()
                    task.result = result
                    await db.commit()
                    
                    # 发送完成状态
                    await manager.send_status(task_id, "success")
                    logger_ctx.info("Task completed successfully", result_summary=result)
                    
                except Exception as e:
                    # 记录错误并更新任务状态
                    error_msg = str(e)
                    task.status = TaskStatus.FAILED
                    task.error = error_msg
                    task.completed_at = datetime.utcnow()
                    await db.commit()
                    
                    # 发送错误状态
                    await manager.send_status(task_id, "failed")
                    logger_ctx.error(f"Task failed: {error_msg}", exc_info=True)
                    raise
                finally:
                    # 清理任务记录
                    cls._running_tasks.pop(task_id, None)
                    cls._task_events.pop(task_id, None)
            
            # 启动任务
            task_obj = asyncio.create_task(wrapped_task())
            cls._running_tasks[task_id] = task_obj
            
        except Exception as e:
            logger_ctx.error(f"Failed to start task: {str(e)}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.error = str(e)
            await db.commit()
            raise

    @classmethod
    async def cancel_task(cls, task_id: str) -> bool:
        """取消运行中的任务"""
        logger_ctx = get_logger(task_id=task_id)
        
        if task_id not in cls._running_tasks:
            logger_ctx.warning("Attempted to cancel non-existent task")
            return False
        
        # 设置取消事件
        if task_id in cls._task_events:
            cls._task_events[task_id].set()
        
        # 取消任务
        task = cls._running_tasks[task_id]
        if not task.done():
            logger_ctx.info("Cancelling running task")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                # 发送取消状态
                await manager.send_status(task_id, "cancelled")
                logger_ctx.info("Task was cancelled by user")
                pass
        
        # 清理任务记录
        cls._running_tasks.pop(task_id, None)
        cls._task_events.pop(task_id, None)
        
        return True 