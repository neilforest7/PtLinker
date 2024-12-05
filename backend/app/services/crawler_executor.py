import sys
import os
import asyncio
import importlib.util
import signal
import psutil
from typing import Dict, Any, Optional, Callable, Coroutine, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.task import Task, TaskStatus
from app.services.logger import TaskLogger
from app.services.websocket_manager import manager
from app.core.logger import get_logger
from app.core.config import get_settings
from app.schemas.crawler import CrawlerProcessStatus

class CrawlerProcess:
    def __init__(self, task_id: str, crawler_id: str):
        self.task_id = task_id
        self.crawler_id = crawler_id
        self.process: Optional[asyncio.subprocess.Process] = None
        self.logger = get_logger(task_id=task_id, crawler_id=crawler_id)
        self.settings = get_settings()
        self._stop_event = asyncio.Event()
        self._health_check_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self.last_health_check: Optional[datetime] = None
        self._resource_limits: Dict[str, float] = {
            "max_cpu_percent": 80.0,
            "max_memory_percent": 80.0
        }

    def set_resource_limits(self, limits: Dict[str, Any]) -> None:
        """设置资源限制"""
        if limits:
            self._resource_limits.update(limits)

    async def start(self, config: Dict[str, Any]) -> None:
        """启动爬虫进程"""
        try:
            # 设置资源限制
            if "process_config" in config:
                self.set_resource_limits(config["process_config"])

            # 准备爬虫脚本路径
            crawler_path = os.path.join(
                self.settings.CRAWLER_CONFIG_PATH.parent.parent,
                "src",
                "main.py"
            )
            
            # 将配置转换为命令行参数
            config_args = [f"--{k}={v}" for k, v in config.items() if k != "process_config"]
            
            # 启动爬虫进程
            self.process = await asyncio.create_subprocess_exec(
                sys.executable,
                crawler_path,
                "--crawler_id", self.crawler_id,
                "--task_id", self.task_id,
                *config_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.logger.info(f"Started crawler process with PID: {self.process.pid}")
            
            # 启动健康检查和资源监控
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            self._monitor_task = asyncio.create_task(self._monitor_resources())
            
            # 启动输出监控
            asyncio.create_task(self._monitor_output())
            
        except Exception as e:
            self.logger.error(f"Failed to start crawler process: {str(e)}", exc_info=True)
            raise

    async def stop(self) -> None:
        """停止爬虫进程"""
        if self.process:
            self.logger.info("Stopping crawler process")
            self._stop_event.set()
            
            # 取消所有监控任务
            for task in [self._health_check_task, self._monitor_task]:
                if task:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.logger.warning("Process did not terminate, killing it")
                self.process.kill()
                await self.process.wait()
            
            self.logger.info("Crawler process stopped")

    async def _health_check_loop(self) -> None:
        """健康检查循环"""
        while not self._stop_event.is_set():
            try:
                if self.process and self.process.returncode is not None:
                    self.logger.error("Crawler process died unexpectedly")
                    await manager.send_status(self.task_id, "failed", {
                        "error": "Crawler process died unexpectedly"
                    })
                    break
                
                self.last_health_check = datetime.utcnow()
                await manager.send_status(self.task_id, "running", {
                    "health_check": self.last_health_check.isoformat()
                })
                
                await asyncio.sleep(5)  # 每5秒检查一次
                
            except Exception as e:
                self.logger.error(f"Health check error: {str(e)}", exc_info=True)
                await asyncio.sleep(5)

    async def _monitor_resources(self) -> None:
        """监控进程资源使用"""
        while not self._stop_event.is_set():
            try:
                if self.process and self.process.returncode is None:
                    process = psutil.Process(self.process.pid)
                    cpu_percent = process.cpu_percent()
                    memory_percent = process.memory_percent()
                    
                    # 检查资源限制
                    if cpu_percent > self._resource_limits["max_cpu_percent"]:
                        self.logger.warning(f"CPU usage too high: {cpu_percent}%")
                        await manager.send_log(self.task_id, "warning", 
                            f"High CPU usage: {cpu_percent}%")
                    
                    if memory_percent > self._resource_limits["max_memory_percent"]:
                        self.logger.warning(f"Memory usage too high: {memory_percent}%")
                        await manager.send_log(self.task_id, "warning", 
                            f"High memory usage: {memory_percent}%")
                    
                    # 发送资源使用状态
                    await manager.send_status(self.task_id, "running", {
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory_percent
                    })
                
                await asyncio.sleep(2)  # 每2秒检查一次
                
            except Exception as e:
                self.logger.error(f"Resource monitoring error: {str(e)}", exc_info=True)
                await asyncio.sleep(2)

    async def _monitor_output(self) -> None:
        """监控进程输出"""
        if not self.process:
            return
            
        async def read_stream(stream, is_error: bool):
            while True:
                line = await stream.readline()
                if not line:
                    break
                    
                message = line.decode().strip()
                if is_error:
                    self.logger.error(message)
                    await manager.send_log(self.task_id, "error", message)
                else:
                    self.logger.info(message)
                    await manager.send_log(self.task_id, "info", message)
        
        try:
            await asyncio.gather(
                read_stream(self.process.stdout, False),
                read_stream(self.process.stderr, True)
            )
        except Exception as e:
            self.logger.error(f"Output monitoring error: {str(e)}", exc_info=True)

    def get_status(self) -> CrawlerProcessStatus:
        """获取进程状态"""
        try:
            if not self.process or self.process.returncode is not None:
                return CrawlerProcessStatus(is_running=False)
            
            process = psutil.Process(self.process.pid)
            return CrawlerProcessStatus(
                pid=self.process.pid,
                start_time=datetime.fromtimestamp(process.create_time()),
                cpu_percent=process.cpu_percent(),
                memory_percent=process.memory_percent(),
                is_running=True,
                last_health_check=self.last_health_check
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return CrawlerProcessStatus(is_running=False)

class CrawlerExecutorManager:
    _running_tasks: Dict[str, asyncio.Task] = {}
    _task_events: Dict[str, asyncio.Event] = {}
    _processes: Dict[str, CrawlerProcess] = {}
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
    def get_running_tasks_for_crawler(cls, crawler_id: str) -> List[str]:
        """获取特定爬虫的运行中任务"""
        return [
            task_id for task_id, process in cls._processes.items()
            if process.crawler_id == crawler_id and cls.is_task_running(task_id)
        ]

    @classmethod
    def get_process(cls, task_id: str) -> Optional[CrawlerProcess]:
        """获取任务的进程实例"""
        return cls._processes.get(task_id)

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
            
            # 创建进程实例
            process = CrawlerProcess(task_id, task.crawler_id)
            cls._processes[task_id] = process
            
            # 通过WebSocket发送状态更新
            await manager.send_status(task_id, "running")
            logger_ctx.info("Starting crawler task")
            
            # 创建异步任务
            async def wrapped_task():
                try:
                    # 检查取消事件
                    if cancel_event.is_set():
                        return
                    
                    # 启动爬虫进程
                    await process.start(task.config)
                    
                    # 等待进程完成
                    if process.process:
                        return_code = await process.process.wait()
                        
                        if return_code == 0:
                            # 更新任务状态为成功
                            task.status = TaskStatus.SUCCESS
                            task.completed_at = datetime.utcnow()
                            await db.commit()
                            await manager.send_status(task_id, "success")
                            logger_ctx.info("Task completed successfully")
                        else:
                            # 更新任务状态为失败
                            task.status = TaskStatus.FAILED
                            task.error = f"Process exited with code {return_code}"
                            task.completed_at = datetime.utcnow()
                            await db.commit()
                            await manager.send_status(task_id, "failed")
                            logger_ctx.error(f"Task failed: {task.error}")
                    
                except Exception as e:
                    # 记录错误并更新任务状态
                    error_msg = str(e)
                    task.status = TaskStatus.FAILED
                    task.error = error_msg
                    task.completed_at = datetime.utcnow()
                    await db.commit()
                    await manager.send_status(task_id, "failed")
                    logger_ctx.error(f"Task failed: {error_msg}", exc_info=True)
                    raise
                finally:
                    # 停止进程
                    if task_id in cls._processes:
                        await cls._processes[task_id].stop()
                    # 清理任务记录
                    cls._running_tasks.pop(task_id, None)
                    cls._task_events.pop(task_id, None)
                    cls._processes.pop(task_id, None)
            
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
        
        try:
            # 设置取消事件
            if task_id in cls._task_events:
                cls._task_events[task_id].set()
            
            # 停止进程
            if task_id in cls._processes:
                await cls._processes[task_id].stop()
            
            # 取消任务
            task = cls._running_tasks[task_id]
            if not task.done():
                logger_ctx.info("Cancelling running task")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    await manager.send_status(task_id, "cancelled")
                    logger_ctx.info("Task was cancelled by user")
            
            return True
            
        except Exception as e:
            logger_ctx.error(f"Failed to cancel task: {str(e)}", exc_info=True)
            return False
        finally:
            # 清理任务记录
            cls._running_tasks.pop(task_id, None)
            cls._task_events.pop(task_id, None)
            cls._processes.pop(task_id, None)