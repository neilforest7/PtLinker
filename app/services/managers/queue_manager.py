import asyncio
import traceback
from collections import defaultdict
from datetime import datetime, timezone
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
        self._running_tasks: Dict[str, str] = {}  # site_id -> task_id
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
        """获取待处理的任务列表，包括数据库中的READY状态任务
        
        Args:
            site_id: 可选的站点ID，如果提供则只返回该站点的任务
            db: 数据库会话
            
        Returns:
            List[TaskCreate]: 待处理任务列表
        """
        async with self._lock:
            try:
                pending_tasks = []
                
                # 1. 从数据库中获取READY状态的任务（优先从数据库获取，确保状态一致性）
                if db:
                    query = select(Task).where(Task.status == TaskStatus.READY)
                    if site_id:
                        query = query.where(Task.site_id == site_id)
                    
                    result = await db.execute(query)
                    db_tasks = result.scalars().all()
                    
                    # 将数据库任务转换为TaskCreate对象
                    for task in db_tasks:
                        pending_tasks.append(TaskCreate(
                            task_id=task.task_id,
                            site_id=task.site_id,
                            status=TaskStatus.READY,
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
                
                # 2. 从内存队列中获取任务（确保包含最新添加但还未持久化到数据库的任务）
                if site_id:
                    # 处理指定站点的任务
                    task_ids = self._queues[site_id]
                    for task_id in task_ids:
                        task_info = self._task_info.get(task_id)
                        if task_info and task_id not in [t.task_id for t in pending_tasks]:
                            pending_tasks.append(TaskCreate(
                                task_id=task_id,
                                site_id=site_id,
                                status=TaskStatus.READY,
                                created_at=task_info.get("queued_at"),
                                updated_at=datetime.now(),
                                task_metadata=task_info.get("task_metadata")
                            ))
                else:
                    # 处理所有站点的任务
                    for site_id, task_ids in self._queues.items():
                        for task_id in task_ids:
                            task_info = self._task_info.get(task_id)
                            if task_info and task_id not in [t.task_id for t in pending_tasks]:
                                pending_tasks.append(TaskCreate(
                                    task_id=task_id,
                                    site_id=site_id,
                                    status=TaskStatus.READY,
                                    created_at=task_info.get("queued_at"),
                                    updated_at=datetime.now(),
                                    task_metadata=task_info.get("task_metadata")
                                ))
                
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
                    status=TaskStatus.READY,
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
    
    async def get_next_task(self, site_id: str, db: AsyncSession) -> Optional[TaskResponse]:
        """获取下一个要执行的任务"""
        async with self._lock:
            try:
                # 检查是否有正在运行的任务
                if site_id in self._running_tasks:
                    return None
                
                # 检查队列是否为空
                if not self._queues[site_id]:
                    return None
                
                # 获取下一个任务
                task_id = self._queues[site_id].pop(0)
                
                # 更新任务状态为 PENDING
                await self._update_task_status(
                    db,
                    task_id,
                    TaskStatus.PENDING,
                    "任务准备执行",
                )
                
                # 记录运行中的任务
                self._running_tasks[site_id] = task_id
                
                # 获取更新后的任务
                stmt = select(Task).where(Task.task_id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if task:
                    return TaskResponse.model_validate(task)
                return None
                
            except Exception as e:
                error_msg = str(e)
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc()
                }
                self.logger.error(f"获取任务失败: {error_msg}")
                self.logger.debug("错误详情:", exc_info=True)
                return None
    
    async def complete_task(self, task_id: str, db: AsyncSession, 
                            status: TaskStatus = TaskStatus.SUCCESS, 
                            msg: str = None) -> bool:
        """完成任务"""
        async with self._lock:
            try:
                # 更新任务状态
                await self._update_task_status(
                    db,
                    task_id,
                    status,
                    msg=msg,
                    completed_at=datetime.now()
                )
                
                # 获取任务信息
                stmt = select(Task).where(Task.task_id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if task:
                    # 清理运行状态
                    site_id = task.site_id
                    if site_id in self._running_tasks and self._running_tasks[site_id] == task_id:
                        del self._running_tasks[site_id]
                    
                    if task_id in self._task_info:
                        del self._task_info[task_id]
                    
                    self.logger.info(f"任务 {task_id} 已完成，状态: {status}")
                    return True
                    
                return False
                
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
                
                if task:
                    # 如果任务在队列中，移除它
                    site_id = task.site_id
                    if task_id in self._queues[site_id]:
                        self._queues[site_id].remove(task_id)
                    
                    # 如果任务正在运行，清理运行状态
                    if site_id in self._running_tasks and self._running_tasks[site_id] == task_id:
                        del self._running_tasks[site_id]
                    
                    # 更新任务状态
                    await self._update_task_status(
                        db,
                        task_id,
                        TaskStatus.CANCELLED,
                        msg="任务已取消",
                        completed_at=datetime.now()
                    )
                    
                    if task_id in self._task_info:
                        del self._task_info[task_id]
                    
                    self.logger.info(f"任务 {task_id} 已取消")
                    return True
                    
                return False
                
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
    
    def get_queue_status(self, site_id: str) -> Dict:
        """获取队列状态"""
        return {
            "queued_tasks": len(self._queues[site_id]),
            "running_task": self._running_tasks.get(site_id),
            "queued_task_ids": self._queues[site_id]
        }
    
    async def cleanup(self, db: AsyncSession):
        """清理所有队列"""
        async with self._lock:
            try:
                # 取消所有排队的任务
                for site_id, task_ids in self._queues.items():
                    for task_id in task_ids:
                        await self.cancel_task(task_id, db)
                
                # 取消所有运行中的任务
                for site_id, task_id in list(self._running_tasks.items()):
                    await self.cancel_task(task_id, db)
                
                # 清理状态
                self._queues.clear()
                self._running_tasks.clear()
                self._task_info.clear()
                
            except Exception as e:
                error_msg = str(e)
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "traceback": traceback.format_exc()
                }
                self.logger.error(f"清理队列失败: {error_msg}")
                self.logger.debug("错误详情:", exc_info=True)
                
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
                            db,
                            task.task_id,
                            TaskStatus.CANCELLED,
                            msg="任务已取消",
                            completed_at=datetime.now()
                        )
                        
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


# 全局队列管理器实例
queue_manager = QueueManager()