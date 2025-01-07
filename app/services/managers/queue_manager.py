import asyncio
import traceback
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from core.logger import get_logger, setup_logger
from models.models import Task, TaskStatus
from schemas.task import TaskCreate, TaskResponse, TaskUpdate
from services.managers.task_status_manager import task_status_manager
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class QueueManager:
    def __init__(self):
        self._queues: Dict[str, List[str]] = defaultdict(list)  # site_id -> [task_id]
        self._ready_tasks: Dict[str, str] = {}  # site_id -> task_id
        self._task_info: Dict[str, Dict] = {}  # task_id -> task_info
        self._lock = asyncio.Lock()
        self._max_concurrency = 1
        self.logger = get_logger(name=__name__, site_id="QueueMgr")

    async def initialize(self, max_concurrency: int = 1) -> None:
        """初始化队列管理器
        
        Args:
            max_concurrency: 最大并发数
        """
        self._max_concurrency = max_concurrency
        self.logger.info(f"Queue manager initialized with max concurrency: {max_concurrency}")
        
        # 启动定期检查任务
        asyncio.create_task(self._periodic_queue_check())
        
    async def _periodic_queue_check(self):
        """定期检查队列状态并处理任务"""
        while True:
            try:
                # 获取数据库会话
                self.logger.info("周期检查队列状态")
                from core import database
                db = await database.get_init_db()
                
                # 获取当前运行中的任务数量
                stmt = select(Task).where(Task.status == TaskStatus.RUNNING)
                result = await db.execute(stmt)
                running_tasks = result.scalars().all()
                running_count = len(running_tasks)

                # 计算可用槽位时考虑运行中的任务
                total_in_progress = running_count + len(self._ready_tasks)
                self.logger.success(f"当前运行中的任务数量: {running_count}, 已准备就绪的任务数量: {len(self._ready_tasks)}, 总任务数量: {total_in_progress}")
                self.logger.success(f"当前最大并发数: {self._max_concurrency}")
                self.logger.success(f"当前self._queues状态: {self._queues}")
                self.logger.success(f"当前self._ready_tasks状态: {self._ready_tasks}")
                if total_in_progress < self._max_concurrency:
                    available_slots = self._max_concurrency - total_in_progress
                    
                    # 获取QUEUED状态的任务
                    stmt = (
                        select(Task)
                        .where(
                            Task.status == TaskStatus.QUEUED,
                            Task.created_at <= datetime.now() - timedelta(seconds=5)
                        )
                        .order_by(Task.created_at.asc())
                        .limit(available_slots)
                    )
                    result = await db.execute(stmt)
                    queued_tasks = result.scalars().all()
                    
                    # 将任务标记为READY
                    for task in queued_tasks:
                        # 检查站点是否已有READY任务
                        if task.site_id in self._ready_tasks:
                            self.logger.debug(f"站点 {task.site_id} 已有READY状态任务，跳过")
                            continue
                        
                        await self._update_task_status(
                            db,
                            task.task_id,
                            TaskStatus.READY,
                            "任务准备就绪"
                        )
                        # 更新ready_tasks状态
                        self._ready_tasks[task.site_id] = task.task_id
                        self.logger.info(f"任务 {task.task_id} 已标记为READY状态")
                
                await db.commit()
                
            except Exception as e:
                self.logger.error(f"队列检查失败: {str(e)}")
                self.logger.debug("错误详情:", exc_info=True)
                if db:
                    await db.rollback()
            finally:
                if db:
                    await db.close()
                    
            # 每30秒检查一次
            await asyncio.sleep(30)

    async def _update_task_status(self, db: AsyncSession, task_id: str, status: TaskStatus, 
                                msg: Optional[str] = None,
                                completed_at: Optional[datetime] = None,
                                error_details: Optional[Dict] = None,
                                task_metadata: Optional[Dict] = None) -> None:
        """更新任务状态"""
        site_id = None
        task_info = self._task_info.get(task_id)
        if task_info:
            site_id = task_info.get("site_id")
            
        await task_status_manager.update_task_status(
            db=db,
            task_id=task_id,
            status=status,
            msg=msg,
            completed_at=completed_at,
            error_details=error_details,
            task_metadata=task_metadata,
            site_id=site_id
        )
        
    async def get_pending_tasks(self, site_id: Optional[str] = None, db: AsyncSession = None) -> List[TaskCreate]:
        """获取待处理的任务列表
        
        Args:
            site_id: 可选的站点ID，如果提供则只返回该站点的任务
            db: 数据库会话
            
        Returns:
            List[TaskCreate]: 待处理任务列表
        """
        async with self._lock:
            try:
                pending_tasks = []
                
                # 1. 从数据库中获取非终态的任务
                if db:
                    query = select(Task).where(
                        Task.status.in_([
                            TaskStatus.PENDING,
                            TaskStatus.QUEUED,
                            TaskStatus.READY
                        ])
                    )
                    if site_id:
                        query = query.where(Task.site_id == site_id)
                    query = query.order_by(Task.created_at.asc())
                    
                    result = await db.execute(query)
                    db_tasks = result.scalars().all()
                    
                    # 将数据库任务转换为TaskCreate对象
                    for task in db_tasks:
                        pending_tasks.append(TaskCreate(
                            task_id=task.task_id,
                            site_id=task.site_id,
                            status=task.status,
                            created_at=task.created_at,
                            updated_at=task.updated_at,
                            task_metadata=task.task_metadata
                        ))
                        # 同步到内存队列（如果不存在）
                        if task.task_id not in self._queues[task.site_id]:
                            self._queues[task.site_id].append(task.task_id)
                            self._task_info[task.task_id] = {
                                "queued_at": task.created_at,
                                "site_id": task.site_id,
                            }
                
                self.logger.debug(f"获取到 {len(pending_tasks)} 个待处理任务")
                if site_id:
                    self.logger.debug(f"站点 {site_id} 的待处理任务: {[t.task_id for t in pending_tasks]}")
                else:
                    self.logger.debug(f"所有站点的待处理任务: {[(t.site_id, t.task_id) for t in pending_tasks]}")
                    
                return pending_tasks
                
            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"获取待处理任务失败: {error_msg}")
                self.logger.debug("错误详情:", exc_info=True)
                return []

    async def add_task(self, task: TaskCreate, db: AsyncSession) -> Optional[TaskResponse]:
        """添加新任务到队列
        
        Args:
            task: 任务创建模型
            db: 数据库会话
        """
        async with self._lock:
            try:
                # 创建任务记录
                db_task = Task(
                    task_id=task.task_id,
                    site_id=task.site_id,
                    status=TaskStatus.PENDING,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                db.add(db_task)
                await db.commit()
                await db.refresh(db_task)
                
                # 添加到队列
                self._queues[task.site_id].append(task.task_id)
                self._task_info[task.task_id] = {
                    "queued_at": datetime.now(),
                    "site_id": task.site_id,
                }
                
                self.logger.info(f"任务 {task.task_id} 已添加到队列")
                return TaskResponse.model_validate(db_task)
                
            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"添加任务失败: {error_msg}")
                self.logger.debug("错误详情:", exc_info=True)
                await db.rollback()
                return None
    
    async def complete_task(self, task_id: str, db: AsyncSession, 
                            status: TaskStatus = TaskStatus.SUCCESS, 
                            msg: str = None) -> bool:
        """完成任务"""
        async with self._lock:
            try:
                # 获取任务信息
                stmt = select(Task).where(Task.task_id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if not task:
                    self.logger.error(f"任务不存在: {task_id}")
                    return False
                
                # 只有RUNNING状态的任务可以被完成
                if task.status != TaskStatus.RUNNING:
                    self.logger.warning(f"任务 {task_id} 状态为 {task.status}，不能标记为完成")
                    return False
                
                # 更新任务状态
                await self._update_task_status(
                    db=db,
                    task_id=task_id,
                    status=status,
                    msg=msg,
                    completed_at=datetime.now()
                )
                
                # 清理队列信息
                site_id = task.site_id
                if task_id in self._task_info:
                    del self._task_info[task_id]
                if task_id in self._queues[site_id]:
                    self._queues[site_id].remove(task_id)
                if site_id in self._ready_tasks and self._ready_tasks[site_id] == task_id:
                    del self._ready_tasks[site_id]
                
                self.logger.info(f"任务 {task_id} 已完成，状态: {status}")
                return True
                
            except Exception as e:
                error_msg = str(e)
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc()
                }
                self.logger.error(f"完成任务失败: {error_msg}")
                self.logger.debug("错误详情:", exc_info=True)
                return False
    
    async def cancel_task(self, task_id: str, db: AsyncSession) -> bool:
        """取消任务"""
        async with self._lock:
            try:
                # 获取任务信息
                stmt = select(Task).where(Task.task_id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if not task:
                    self.logger.error(f"任务不存在: {task_id}")
                    return False
                
                # 检查任务是否可以取消
                if task.status in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    self.logger.warning(f"任务 {task_id} 状态为 {task.status}，不能取消")
                    return False
                
                # 更新任务状态
                await self._update_task_status(
                    db=db,
                    task_id=task_id,
                    status=TaskStatus.CANCELLED,
                    msg="任务已取消",
                    completed_at=datetime.now()
                )
                
                # 清理运行状态
                site_id = task.site_id
                if site_id in self._ready_tasks and self._ready_tasks[site_id] == task_id:
                    del self._ready_tasks[site_id]
                
                # 清理队列信息
                if task_id in self._task_info:
                    del self._task_info[task_id]
                if task_id in self._queues[site_id]:
                    self._queues[site_id].remove(task_id)
                
                self.logger.info(f"任务 {task_id} 已取消")
                return True
                
            except Exception as e:
                error_msg = str(e)
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc()
                }
                self.logger.error(f"取消任务失败: {error_msg}")
                self.logger.debug("错误详情:", exc_info=True)
                return False
    
    async def clear_pending_tasks(self, db: AsyncSession, site_id: str = None) -> dict:
        """清除待运行的任务队列
        
        Args:
            db: 数据库会话
            site_id: 可选的站点ID，如果不提供则清除所有站点的待运行任务
            
        Returns:
            dict: 包含清除的任务数量信息
        """
        async with self._lock:
            try:
                cleared_count = 0
                total_count = 0
                
                # 从数据库中获取READY状态的任务
                query = select(Task).where(Task.status == TaskStatus.READY)
                if site_id:
                    query = query.where(Task.site_id == site_id)
                
                result = await db.execute(query)
                ready_tasks = result.scalars().all()
                
                # 记录总任务数
                total_count = len(ready_tasks)
                
                # 清除每个READY状态的任务
                for task in ready_tasks:
                    try:
                        # 从内存队列中移除任务
                        if task.task_id in self._queues[task.site_id]:
                            self._queues[task.site_id].remove(task.task_id)
                        
                        # 清理任务信息
                        if task.task_id in self._task_info:
                            del self._task_info[task.task_id]
                        
                        # 更新任务状态
                        await self._update_task_status(
                            db=db,
                            task_id=task.task_id,
                            status=TaskStatus.CANCELLED,
                            msg="任务已取消",
                            completed_at=datetime.now()
                        )
                        
                        # 清理 ready_tasks
                        if task.site_id in self._ready_tasks and self._ready_tasks[task.site_id] == task.task_id:
                            del self._ready_tasks[task.site_id]
                        
                        cleared_count += 1
                        self.logger.debug(f"已清除任务: {task.task_id}")
                        
                    except Exception as e:
                        self.logger.error(f"清除任务 {task.task_id} 失败: {str(e)}")
                        continue
                
                # 提交所有更改
                await db.commit()
                
                self.logger.info(f"成功清除 {cleared_count}/{total_count} 个待运行任务")
                return {
                    "cleared_count": cleared_count,
                    "total_ready_count": total_count,
                    "site_id": site_id if site_id else "all"
                }
                
            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"清除待运行任务失败: {error_msg}")
                self.logger.debug("错误详情:", exc_info=True)
                await db.rollback()
                raise

    async def start_queue(self, db: AsyncSession) -> bool:
        """启动队列处理
        
        将所有PENDING任务转为QUEUED状态，后续由周期检查任务处理状态转换
        
        Args:
            db: 数据库会话
            
        Returns:
            bool: 是否成功启动队列处理
        """
        async with self._lock:
            try:
                # 1. 将所有PENDING任务转为QUEUED
                stmt = (
                    select(Task)
                    .where(Task.status == TaskStatus.PENDING)
                    .order_by(Task.created_at.asc())
                )
                result = await db.execute(stmt)
                pending_tasks = result.scalars().all()
                
                for task in pending_tasks:
                    await self._update_task_status(
                        db,
                        task.task_id,
                        TaskStatus.QUEUED,
                        "任务已加入队列"
                    )
                    # 确保任务在内存队列中
                    if task.task_id not in self._queues[task.site_id]:
                        self._queues[task.site_id].append(task.task_id)
                        self._task_info[task.task_id] = {
                            "queued_at": datetime.now(),
                            "site_id": task.site_id,
                        }
                
                self.logger.info(f"已将 {len(pending_tasks)} 个PENDING任务转为QUEUED状态")
                await db.commit()
                return True
                
            except Exception as e:
                self.logger.error(f"启动队列处理失败: {str(e)}")
                self.logger.debug("错误详情:", exc_info=True)
                await db.rollback()
                return False

    async def cleanup(self, db: AsyncSession):
        """清理所有队列"""
        async with self._lock:
            try:
                # 取消所有排队的任务
                for site_id, task_ids in self._queues.items():
                    for task_id in task_ids:
                        await self.cancel_task(task_id, db)
                
                # 清理状态
                self._queues.clear()
                self._task_info.clear()
                self._ready_tasks.clear()
                
            except Exception as e:
                self.logger.error(f"清理队列失败: {str(e)}")
                self.logger.debug("错误详情:", exc_info=True)

    async def remove_ready_task(self, task_id: str, site_id: str) -> None:
        """从 ready_tasks 中移除任务
        
        Args:
            task_id: 任务ID
            site_id: 站点ID
        """
        async with self._lock:
            if site_id in self._ready_tasks and self._ready_tasks[site_id] == task_id:
                del self._ready_tasks[site_id]
                self.logger.debug(f"从 ready_tasks 中移除任务: {task_id}")


# 全局队列管理器实例
queue_manager = QueueManager()