import asyncio
import os
import sys
import traceback
from datetime import datetime
from multiprocessing import Process
from pathlib import Path
from typing import Dict, List, Optional

from core.database import AsyncSession
from core.logger import get_logger, setup_logger
from models.models import Task, TaskStatus
from schemas.task import TaskCreate, TaskResponse, TaskUpdate
from services.crawler.site_crawler import SiteCrawler
from services.managers.browserstate_manager import BrowserStateManager
from services.managers.result_manager import ResultManager
from services.managers.setting_manager import SettingManager
from services.managers.site_manager import SiteManager
from services.managers.task_status_manager import task_status_manager
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
            db = None
            try:
                # 初始化日志
                setup_logger(is_subprocess=True)
                logger = get_logger(name=__name__, site_id=self.site_id, is_subprocess=True)
                logger.debug("子进程启动")
                
                # 初始化数据库连接
                from core import database
                db = await database.get_init_db()
                
                # 更新任务状态为 PENDING
                await self._update_task_status(db, TaskStatus.PENDING, "任务初始化中")
                
                # 初始化所有管理器
                logger.debug("开始初始化管理器")
                
                # 1. 初始化 settings
                from services.managers.setting_manager import SettingManager
                logger.debug("初始化 settings")
                await SettingManager.get_instance().initialize(db)
                
                # 2. 初始化 site manager
                logger.debug("初始化 site manager")
                site_manager = SiteManager.get_instance()
                await site_manager.initialize(db)
                
                # 3. 初始化 queue manager
                logger.debug("初始化 queue manager")
                from services.managers.queue_manager import queue_manager
                await queue_manager.initialize(max_concurrency=await SettingManager.get_instance().get_setting("crawler_max_concurrency"))
                
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
                # 设置数据库会话
                await crawler.set_db(db)
                logger.debug(f"{self.site_id}开始爬虫任务")
                await crawler.start()
                logger.debug(f"{self.site_id}爬虫任务完成")
                
                # 更新任务状态为 SUCCESS
                if not await task_status_manager.get_task_status(db, self.task_id) == TaskStatus.FAILED:
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
        self._running_sites: Dict[str, str] = {}  # site_id -> task_id
        self._lock = asyncio.Lock()
        self._queue_manager = None
        self._db = None
        self._task_timeout = 240  # 默认超时时间（秒）
        self._max_concurrency = 1  # 默认最大并发数
        self.logger = get_logger(name=__name__, site_id="ProcessMgr")
        
    async def initialize(self, queue_manager, db: AsyncSession) -> None:
        """初始化进程管理器"""
        self._queue_manager = queue_manager
        self._db = db
        
        # 获取最大并发数设置
        from services.managers.setting_manager import SettingManager
        self._max_concurrency = await SettingManager.get_instance().get_setting("crawler_max_concurrency")
        self.logger.info(f"Process manager initialized with max concurrency: {self._max_concurrency}")
        
        # 创建定期检查任务
        async def periodic_check():
            while True:
                try:
                    await self.check_all_tasks()
                    self.logger.info("周期检查任务状态")
                except Exception as e:
                    self.logger.error(f"周期检查任务失败: {str(e)}")
                    self.logger.debug("错误详情:", exc_info=True)
                await asyncio.sleep(5)  # 每5秒检查一次
                
        # 启动定期检查任务
        asyncio.create_task(periodic_check())
        
    async def check_task_status(self, task_id: str) -> Optional[Dict]:
        """检查任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[Dict]: 任务状态信息，包含 is_alive、exit_code 和 running_time
        """
        if task_id not in self._processes:
            return None
            
        process = self._processes[task_id]
        status = self._status[task_id].copy()
        
        # 计算运行时间
        running_time = (datetime.now() - status["start_time"]).total_seconds()
        
        status.update({
            "is_alive": process.is_alive(),
            "exit_code": process.exitcode if not process.is_alive() else None,
            "running_time": running_time,
            "is_timeout": running_time > self._task_timeout
        })
        
        return status
        
    async def start_crawlertask(self, db: AsyncSession) -> List[TaskResponse]:
        """启动所有READY状态的任务进程
        
        Args:
            db: 数据库会话
            
        Returns:
            List[TaskResponse]: 成功启动的任务列表
        """
        async with self._lock:
            try:
                # 确保已经初始化
                if not self._queue_manager:
                    from services.managers.queue_manager import queue_manager
                    self._queue_manager = queue_manager
                    self.logger.info("已获取queue_manager")
                
                # 获取所有READY状态的任务
                stmt = (
                    select(Task)
                    .where(Task.status == TaskStatus.READY)
                    .order_by(Task.created_at.asc())
                )
                result = await db.execute(stmt)
                ready_tasks = result.scalars().all()
                
                if not ready_tasks:
                    self.logger.info("没有READY状态的任务需要启动")
                    return []
                
                self.logger.info(f"找到 {len(ready_tasks)} 个READY状态的任务")
                started_tasks = []
                
                # 构建日志路径
                log_path = str(Path(__file__).parent.parent.parent / 'logs' / 'tasks')
                
                # 尝试启动每个任务
                for task in ready_tasks:
                    try:
                        # 检查站点是否已有运行中的任务
                        if task.site_id in self._running_sites:
                            self.logger.warning(f"站点 {task.site_id} 已有运行中的任务，跳过任务 {task.task_id}")
                            continue
                            
                        # 检查进程状态
                        if task.task_id in self._processes:
                            status = await self.check_task_status(task.task_id)
                            if status and status["is_alive"]:
                                self.logger.warning(f"任务 {task.task_id} 已经在运行")
                                continue
                        
                        # 创建并启动进程
                        process = CrawlerProcess(
                            site_id=task.site_id,
                            task_id=task.task_id,
                            log_dir=log_path
                        )
                        process.start()
                        self.logger.info(f"任务 {task.task_id} 启动 (PID: {process.pid})")
                        
                        # 存储进程信息
                        self._processes[task.task_id] = process
                        self._status[task.task_id] = {
                            "start_time": datetime.now(),
                            "pid": process.pid,
                            "site_id": task.site_id
                        }
                        
                        # 更新任务状态为RUNNING
                        await self._queue_manager._update_task_status(
                            db=db,
                            task_id=task.task_id,
                            status=TaskStatus.RUNNING,
                            msg="任务已启动",
                            task_metadata={
                                "pid": process.pid,
                            }
                        )
                        
                        # 记录运行中的任务
                        self._running_sites[task.site_id] = task.task_id
                        started_tasks.append(TaskResponse.model_validate(task))
                        self.logger.info(f"任务 {task.task_id} 启动成功 (PID: {process.pid})")
                        
                    except Exception as e:
                        self.logger.error(f"启动任务 {task.task_id} 失败: {str(e)}")
                        self.logger.debug("错误详情:", exc_info=True)
                        # 如果启动失败，确保清理任何可能创建的进程记录
                        if task.task_id in self._processes:
                            await self.cleanup_task(task.task_id)
                        continue
                
                self.logger.info(f"成功启动 {len(started_tasks)}/{len(ready_tasks)} 个任务")
                return started_tasks
                
            except Exception as e:
                error_msg = str(e)
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc()
                }
                self.logger.error(f"启动任务失败: {error_msg}")
                self.logger.debug("错误详情:", exc_info=True)
                return []
                
    async def cleanup_task(self, task_id: str) -> bool:
        """清理任务进程
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功清理
        """
        async with self._lock:
            try:
                if task_id not in self._processes:
                    self.logger.warning(f"任务 {task_id} 不存在或已清理")
                    return False
                
                process = self._processes[task_id]
                if process.is_alive():
                    self.logger.info(f"停止进程 - 任务ID: {task_id}, PID: {process.pid}")
                    process.terminate()
                    process.join(timeout=5)
                    if process.is_alive():
                        self.logger.warning(f"进程未响应，强制终止 - 任务ID: {task_id}")
                        process.kill()
                        process.join()
                
                # 清理进程记录
                del self._processes[task_id]
                
                # 清理状态记录
                if task_id in self._status:
                    site_id = self._status[task_id].get("site_id")
                    if site_id and site_id in self._running_sites and self._running_sites[site_id] == task_id:
                        del self._running_sites[site_id]
                        self.logger.debug(f"已从运行中站点列表移除: {site_id}")
                    del self._status[task_id]
                
                self.logger.info(f"任务 {task_id} 已清理")
                return True
                
            except Exception as e:
                self.logger.error(f"清理任务 {task_id} 失败: {str(e)}")
                self.logger.debug("错误详情:", exc_info=True)
                return False
                
    async def check_all_tasks(self):
        """检查所有任务的状态"""
        try:
            # 获取新的数据库会话
            if not self._db:
                from core import database
                self._db = await database.get_init_db()
            try:
                task_ids = list(self._processes.keys())
                for task_id in task_ids:
                    try:
                        status = await self.check_task_status(task_id)
                        if status:
                            # 检查是否超时
                            if status["is_alive"] and status["is_timeout"]:
                                self.logger.warning(f"任务 {task_id} 执行超时 ({status['running_time']:.1f}s > {self._task_timeout}s)，强制终止")
                                # 强制终止进程并清理状态
                                await self.cleanup_task(task_id)
                                # 更新任务状态为失败
                                await self._queue_manager._update_task_status(
                                    db=self._db,
                                    task_id=task_id,
                                    status=TaskStatus.FAILED,
                                    msg=f"任务执行超时（{status['running_time']:.1f}s > {self._task_timeout}s）"
                                )
                                continue
                                
                            # 如果进程已经结束
                            if not status["is_alive"]:
                                self.logger.info(f"任务 {task_id} 进程已结束 (退出码: {status['exit_code']})")
                                # 获取站点ID用于清理
                                site_id = self._status[task_id].get("site_id") if task_id in self._status else None
                                
                                # 根据退出码更新任务状态
                                if status["exit_code"] == 0:
                                    await self._queue_manager.complete_task(
                                        task_id,
                                        self._db,
                                        TaskStatus.SUCCESS,
                                        f"任务执行完成（耗时：{status['running_time']:.1f}s）"
                                    )
                                else:
                                    await self._queue_manager.complete_task(
                                        task_id,
                                        self._db,
                                        TaskStatus.FAILED,
                                        f"任务执行失败（退出码: {status['exit_code']}，耗时：{status['running_time']:.1f}s）"
                                    )
                                
                                # 清理进程记录和运行状态
                                await self.cleanup_task(task_id)
                                
                    except Exception as e:
                        self.logger.error(f"检查任务 {task_id} 状态时出错: {str(e)}")
                        self.logger.debug("错误详情:", exc_info=True)
                        # 发生错误时也尝试清理
                        await self.cleanup_task(task_id)
                        continue
                
                # 检查并启动READY状态的任务
                running_count = len(self._running_sites)
                if running_count < self._max_concurrency:
                    self.logger.debug(f"当前运行任务数: {running_count}, 尝试启动新任务")
                    started_tasks = await self.start_crawlertask(self._db)
                    if started_tasks:
                        self.logger.info(f"定期检查时启动了 {len(started_tasks)} 个新任务")
                
            finally:
                if self._db:
                    await self._db.close()
                    self._db = None
                    
        except Exception as e:
            self.logger.error(f"检查任务状态时出错: {str(e)}")
            self.logger.debug("错误详情:", exc_info=True)
            
    async def cleanup(self):
        """清理所有进程"""
        async with self._lock:
            try:
                self.logger.info("开始清理所有进程")
                # 获取所有正在运行的任务
                running_tasks = list(self._processes.keys())
                
                # 清理每个任务
                for task_id in running_tasks:
                    try:
                        # 清理进程
                        await self.cleanup_task(task_id)
                        
                        # 更新任务状态为已取消
                        if self._db and self._queue_manager:
                            await self._queue_manager.cancel_task(task_id, self._db)
                            
                    except Exception as e:
                        self.logger.error(f"清理任务 {task_id} 时发生错误: {str(e)}")
                        self.logger.debug("错误详情:", exc_info=True)
                        continue
                
                self.logger.info(f"成功清理 {len(running_tasks)} 个进程")
                
                if self._db:
                    await self._db.close()
                    
            except Exception as e:
                self.logger.error(f"清理进程时发生错误: {str(e)}")
                self.logger.debug("错误详情:", exc_info=True)
                raise


# 全局进程管理器实例
process_manager = ProcessManager()