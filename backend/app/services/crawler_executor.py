import sys
import os
import asyncio
import signal
import psutil
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.task import Task, TaskStatus
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
        self._monitor_task: Optional[asyncio.Task] = None
        self.last_health_check: Optional[datetime] = None

    async def start(self) -> None:
        """启动爬虫进程"""
        try:
            # 准备爬虫脚本路径
            crawler_path = os.path.join(
                self.settings.CRAWLER_CONFIG_PATH.parent.parent,
                "src",
                "main.py"
            )
            
            # 启动爬虫进程
            self.process = await asyncio.create_subprocess_exec(
                sys.executable,
                crawler_path,
                "--crawler_id", self.crawler_id,
                "--task_id", self.task_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.logger.info(f"Started crawler process with PID: {self.process.pid}")
            
            # 启动统一的进程监控
            self._monitor_task = asyncio.create_task(self._monitor_process())
            
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
            
            # 取消监控任务
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
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

    async def _monitor_process(self) -> None:
        """统一的进程监控逻辑"""
        while not self._stop_event.is_set():
            try:
                if not self.process or self.process.returncode is not None:
                    self.logger.error("Crawler process died unexpectedly")
                    await manager.send_status(self.task_id, "failed", {
                        "error": "Crawler process died unexpectedly"
                    })
                    break

                # 获取进程资源使用情况
                process = psutil.Process(self.process.pid)
                cpu_percent = process.cpu_percent()
                memory_percent = process.memory_percent()
                
                status_data = {
                    "task_id": self.task_id,
                    "crawler_id": self.crawler_id,
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "health_check": datetime.utcnow().isoformat()
                }

                # 更新健康检查时间
                self.last_health_check = datetime.utcnow()
                
                # 发送统一状态更新
                await manager.send_status(self.task_id, "running", status_data)
                
                await asyncio.sleep(2)  # 统一的检查间隔
                
            except Exception as e:
                self.logger.error(f"Process monitoring error: {str(e)}", exc_info=True)
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
            
            # 启动进程
            await process.start()
            
            # 创建任务
            run_task = asyncio.create_task(cls._run_task(task_id, process, cancel_event))
            cls._running_tasks[task_id] = run_task
            
            logger_ctx.info("Task started successfully")
            
        except Exception as e:
            logger_ctx.error(f"Failed to start task: {str(e)}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.error = str(e)
            await db.commit()
            raise

    @classmethod
    async def _run_task(
        cls,
        task_id: str,
        process: CrawlerProcess,
        cancel_event: asyncio.Event
    ) -> None:
        """运行任务的核心逻辑"""
        try:
            # 等待任务完成或取消
            while not cancel_event.is_set():
                if process.process and process.process.returncode is not None:
                    break
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            await process.stop()
            raise
            
        finally:
            # 清理资源
            if task_id in cls._processes:
                del cls._processes[task_id]
            if task_id in cls._task_events:
                del cls._task_events[task_id]
            if task_id in cls._running_tasks:
                del cls._running_tasks[task_id]

    @classmethod
    async def cancel_task(cls, task_id: str) -> bool:
        """取消运行中的任务"""
        if task_id not in cls._running_tasks:
            return False
            
        try:
            # 设置取消事件
            if task_id in cls._task_events:
                cls._task_events[task_id].set()
            
            # 停止进程
            if task_id in cls._processes:
                await cls._processes[task_id].stop()
            
            # 取消任务
            if not cls._running_tasks[task_id].done():
                cls._running_tasks[task_id].cancel()
                try:
                    await cls._running_tasks[task_id]
                except asyncio.CancelledError:
                    pass
            
            return True
            
        except Exception as e:
            cls._logger.error(f"Failed to cancel task {task_id}: {str(e)}", exc_info=True)
            return False