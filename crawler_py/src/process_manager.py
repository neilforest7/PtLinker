import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import psutil
from utils.logger import get_logger
from pathlib import Path
from dotenv import load_dotenv
import os
import platform

class ProcessManager:
    def __init__(
        self,
        max_workers: int = None,
        max_memory_percent: float = 90.0,
        max_cpu_percent: float = 90.0
    ):
        # 根据操作系统设置合适的最大工作进程数
        if platform.system() == 'Windows':
            system_max_workers = 61  # Windows系统的限制
        else:
            system_max_workers = 256  # Linux/Unix系统的默认限制
            
        # 计算建议的工作进程数
        suggested_workers = os.cpu_count() * 2 if os.cpu_count() else 4
        
        # 如果指定了max_workers，确保不超过系统限制
        if max_workers is not None:
            self.max_workers = min(max_workers, system_max_workers)
        else:
            # 如果没有指定，使用建议值，但不超过系统限制
            self.max_workers = min(suggested_workers, system_max_workers)
            
        self.logger = get_logger(name="process_manager")
        self.logger.info(f"Initializing process manager with {self.max_workers} workers")
        
        self.max_memory_percent = max_memory_percent
        self.max_cpu_percent = max_cpu_percent
        self._active_processes: Dict[str, psutil.Process] = {}
        self._stop_event = asyncio.Event()
        self._monitor_task: Optional[asyncio.Task] = None
        self.pool: Optional[ProcessPoolExecutor] = None

    async def start(self):
        """启动进程管理器"""
        if self.pool is not None:
            return

        try:
            self.pool = ProcessPoolExecutor(max_workers=self.max_workers)
            self._stop_event.clear()
            self._monitor_task = asyncio.create_task(self._monitor_resources())
            self.logger.info(f"Process manager started with {self.max_workers} workers")
        except Exception as e:
            self.logger.error(f"Failed to start process manager: {str(e)}")
            raise RuntimeError(f"Failed to start process manager: {str(e)}")

    async def stop(self):
        """停止进程管理器"""
        self._stop_event.set()
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self.pool:
            self.pool.shutdown(wait=True)
            self.pool = None
            
        # 终止所有活动进程
        for process_id, process in self._active_processes.items():
            try:
                process.terminate()
                self.logger.info(f"Terminated process {process_id}")
            except Exception as e:
                self.logger.error(f"Error terminating process {process_id}: {str(e)}")

        self._active_processes.clear()
        self.logger.info("Process manager stopped")

    async def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        if not self.pool:
            raise RuntimeError("Process manager not started")

        task_id = task_data.get("task_id")
        if not task_id:
            raise ValueError("Task ID is required")

        try:
            # 检查资源限制
            if not await self._check_resources():
                raise ResourceWarning("System resources exceeded limits")

            # 创建进程
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(
                self.pool,
                self._run_crawler_process,
                task_data
            )

            # 等待结果
            result = await future
            return result

        except Exception as e:
            self.logger.error(f"Failed to execute task {task_id}: {str(e)}")
            raise

    @staticmethod
    def _run_crawler_process(task_data: Dict[str, Any]) -> Dict[str, Any]:
        """在新进程中运行爬虫"""
        from crawlers.site.site_crawler import SiteCrawler
        from storage.browser_state_manager import BrowserStateManager
        from storage.storage_manager import get_storage_manager
        from utils.logger import get_logger
        from pathlib import Path
        from dotenv import load_dotenv
        import asyncio
        from main import SITE_CONFIGS

        try:
            # 加载环境变量
            env_path = Path(__file__).parent.parent.parent / '.env'
            load_dotenv(env_path)
            
            # 获取任务信息
            task_id = task_data.get("task_id")
            site_id = task_data.get("crawler_id")
            config = task_data.get("config", {})

            if not all([task_id, site_id]):
                raise ValueError("Missing required task information")

            # 在进程内创建新的logger
            logger = get_logger(name="crawler_process", site_id=site_id)
            logger.info(f"Starting crawler process for site {site_id} (task: {task_id})")

            # 初始化管理器
            storage_manager = get_storage_manager()
            browser_manager = BrowserStateManager(storage_manager)

            # 获取站点配置
            site_id = site_id.lower()
            if site_id not in SITE_CONFIGS:
                raise ValueError(f"Site configuration not found for {site_id}")
                
            # 创建任务配置
            config_class = SITE_CONFIGS[site_id]
            task_config = config_class.create_task_config()
            task_config_dict = task_config.dict()
            
            # 合并用户提供的配置
            task_config_dict.update({
                "task_id": task_id,
                "site_id": site_id,
                **config
            })

            # 使用统一的SiteCrawler
            crawler = SiteCrawler(task_config_dict, browser_manager=browser_manager)
            
            # 执行爬虫任务
            asyncio.run(crawler.start())
            
            # 获取爬虫结果
            crawler_result = crawler.get_result()
            
            # 更新站点状态
            asyncio.run(storage_manager.update_site_status(site_id))
            
            # 获取结果
            result = {
                "task_id": task_id,
                "site_id": site_id,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "result": crawler_result
            }

            logger.info(f"Crawler process completed successfully (task: {task_id})")
            return result

        except Exception as e:
            error_msg = str(e)
            error_result = {
                "task_id": task_data.get("task_id"),
                "site_id": task_data.get("crawler_id"),
                "status": "failed",
                "timestamp": datetime.utcnow().isoformat(),
                "error": error_msg
            }
            raise RuntimeError(f"Crawler execution failed: {error_msg}") from e

    async def _monitor_resources(self):
        """监控系统资源使用情况"""
        while not self._stop_event.is_set():
            try:
                # 检查CPU使用率
                cpu_percent = psutil.cpu_percent(interval=1)
                if cpu_percent > self.max_cpu_percent:
                    self.logger.warning(f"High CPU usage: {cpu_percent}%")

                # 检查内存使用率
                memory_percent = psutil.virtual_memory().percent
                if memory_percent > self.max_memory_percent:
                    self.logger.warning(f"High memory usage: {memory_percent}%")

                # 检查每个进程的资源使用
                for process_id, process in list(self._active_processes.items()):
                    try:
                        if not process.is_running():
                            self._active_processes.pop(process_id, None)
                            continue

                        proc_cpu = process.cpu_percent()
                        proc_mem = process.memory_percent()
                        if proc_cpu > self.max_cpu_percent or proc_mem > self.max_memory_percent:
                            self.logger.warning(
                                f"Process {process_id} using high resources: "
                                f"CPU={proc_cpu}%, Memory={proc_mem}%"
                            )

                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        self._active_processes.pop(process_id, None)

                await asyncio.sleep(5)  # 每5秒检查一次

            except Exception as e:
                self.logger.error(f"Error monitoring resources: {str(e)}")
                await asyncio.sleep(5)

    async def _check_resources(self) -> bool:
        """检查是否有足够的资源执行新任务"""
        try:
            # 检查系统资源
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent

            if cpu_percent > self.max_cpu_percent:
                self.logger.warning(f"CPU usage too high: {cpu_percent}%")
                return False

            if memory_percent > self.max_memory_percent:
                self.logger.warning(f"Memory usage too high: {memory_percent}%")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error checking resources: {str(e)}")
            return False

    def get_active_processes(self) -> Dict[str, Dict[str, Any]]:
        """获取活动进程的状态信息"""
        processes = {}
        for process_id, process in self._active_processes.items():
            try:
                if process.is_running():
                    processes[process_id] = {
                        "cpu_percent": process.cpu_percent(),
                        "memory_percent": process.memory_percent(),
                        "create_time": datetime.fromtimestamp(process.create_time()).isoformat(),
                        "status": process.status()
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes 

    def get_process_info(self) -> Optional[Dict[str, Any]]:
        """获取当前进程信息"""
        active_processes = self.get_active_processes()
        if not active_processes:
            return None
            
        process_info = {
            "active_count": len(active_processes),
            "processes": []
        }
        
        for process in active_processes:
            try:
                info = {
                    "pid": process.pid,
                    "status": "running",
                    "cpu_percent": process.cpu_percent(),
                    "memory_percent": process.memory_percent(),
                    "create_time": datetime.fromtimestamp(process.create_time()).isoformat()
                }
                process_info["processes"].append(info)
            except Exception:
                continue
                
        return process_info