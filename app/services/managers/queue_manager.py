import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.logger import get_logger, setup_logger
from models.models import Task, TaskStatus
from schemas.task import TaskCreate, TaskResponse, TaskUpdate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class QueueManager:
    def __init__(self):
        self._queues: Dict[str, List[str]] = defaultdict(list)  # site_id -> [task_id]
        self._running_tasks: Dict[str, str] = {}  # site_id -> task_id
        self._task_info: Dict[str, Dict] = {}  # task_id -> task_info
        self._lock = asyncio.Lock()
        self._max_concurrency = 1
        setup_logger()
        self.logger = get_logger(name=__name__, site_id="queue_manager")

    async def initialize(self, max_concurrency: int = 1) -> None:
        """初始化队列管理器
        
        Args:
            max_concurrency: 最大并发数
        """
        self._max_concurrency = max_concurrency
        self.logger.info(f"Queue manager initialized with max concurrency: {max_concurrency}")
        
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
                
                # 1. 从内存队列中获取任务
                if site_id:
                    task_ids = self._queues[site_id]
                    for task_id in task_ids:
                        task_info = self._task_info.get(task_id)
                        if task_info:
                            pending_tasks.append(TaskCreate(
                                task_id=task_id,
                                site_id=site_id,
                                status=TaskStatus.READY,
                                created_at=task_info.get("queued_at"),
                                updated_at=datetime.now(timezone.utc)
                            ))
                else:
                    # 获取所有站点的任务
                    for site_id, task_ids in self._queues.items():
                        self.logger.debug(f"get_pending_tasks获取站点 {site_id} 的任务: {task_ids}")
                        for task_id in task_ids:
                            task_info = self._task_info.get(task_id)
                            if task_info:
                                pending_tasks.append(TaskCreate(
                                    task_id=task_id,
                                    site_id=site_id,
                                    status=TaskStatus.READY,
                                    created_at=task_info.get("queued_at"),
                                    updated_at=datetime.now(timezone.utc)
                                ))
                
                # 2. 从数据库中获取READY状态的任务
                if db:
                    query = select(Task).where(Task.status == TaskStatus.READY)
                    if site_id:
                        query = query.where(Task.site_id == site_id)
                    
                    result = await db.execute(query)
                    db_tasks = result.scalars().all()
                    
                    # 将数据库任务转换为TaskCreate对象
                    for task in db_tasks:
                        # 检查任务是否已经在内存队列中
                        if task.task_id not in [t.task_id for t in pending_tasks]:
                            pending_tasks.append(TaskCreate(
                                task_id=task.task_id,
                                site_id=task.site_id,
                                status=TaskStatus.READY,
                                created_at=task.created_at,
                                updated_at=task.updated_at
                            ))
                            # 同步到内存队列
                            if task.task_id not in self._queues[task.site_id]:
                                self._queues[task.site_id].append(task.task_id)
                                self._task_info[task.task_id] = {
                                    "queued_at": task.created_at,
                                    "site_id": task.site_id,
                                }
                
                self.logger.debug(f"获取到 {len(pending_tasks)} 个待处理任务")
                return pending_tasks
                
            except Exception as e:
                self.logger.error(f"获取待处理任务失败: {str(e)}")
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
                    status=TaskStatus(task.status.value),  # 转换枚举值
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                )
                db.add(db_task)
                await db.commit()
                await db.refresh(db_task)
                
                # 添加到队列
                self._queues[task.site_id].append(task.task_id)
                self._task_info[task.task_id] = {
                    "queued_at": datetime.now(timezone.utc),
                    "site_id": task.site_id,
                }
                
                self.logger.info(f"任务 {task.task_id} 已添加到队列")
                return TaskResponse(
                    task_id=db_task.task_id,
                    site_id=db_task.site_id,
                    status=db_task.status,
                    created_at=db_task.created_at,
                    updated_at=db_task.updated_at
                )
                
            except Exception as e:
                self.logger.error(f"添加任务失败: {str(e)}")
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
                
                # 更新任务状态
                stmt = select(Task).where(Task.task_id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if task:
                    task_update = TaskUpdate(
                        status=TaskStatus.PENDING,
                        created_at=datetime.now()
                    )
                    for key, value in task_update.model_dump(exclude_unset=True).items():
                        setattr(task, key, value)
                    await db.commit()
                    await db.refresh(task)
                    
                    # 记录运行中的任务
                    self._running_tasks[site_id] = task_id
                    task_response = TaskResponse(
                        task_id=task.task_id,
                        site_id=task.site_id,
                        status=task.status,
                        created_at=task.created_at,
                        updated_at=task.updated_at
                    )
                    return task_response
                    
                return None
                
            except Exception as e:
                self.logger.error(f"获取任务失败: {str(e)}")
                return None
    
    async def complete_task(self, task_id: str, db: AsyncSession, 
                            status: TaskStatus = TaskStatus.SUCCESS, 
                            error: str = None) -> bool:
        """完成任务"""
        async with self._lock:
            try:
                # 更新任务状态
                stmt = select(Task).where(Task.task_id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if task:
                    task_update = TaskUpdate(
                        status=status,
                        completed_at=datetime.now(),
                        error=error
                    )
                    for key, value in task_update.model_dump(exclude_unset=True).items():
                        setattr(task, key, value)
                    await db.commit()
                    
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
                self.logger.error(f"完成任务失败: {str(e)}")
                return False
    
    async def cancel_task(self, task_id: str, db: AsyncSession) -> bool:
        """取消任务"""
        async with self._lock:
            try:
                # 更新任务状态
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
                    task_update = TaskUpdate(
                        status=TaskStatus.CANCELLED,
                        completed_at=datetime.now(),
                        error="Task cancelled by user"
                    )
                    for key, value in task_update.model_dump(exclude_unset=True).items():
                        setattr(task, key, value)
                    await db.commit()
                    
                    if task_id in self._task_info:
                        del self._task_info[task_id]
                    
                    self.logger.info(f"任务 {task_id} 已取消")
                    return True
                    
                return False
                
            except Exception as e:
                self.logger.error(f"取消任务失败: {str(e)}")
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
            # 取消所有排队的任务
            for site_id, task_ids in self._queues.items():
                for task_id in task_ids:
                    await self.cancel_task(task_id, db)
            
            # 取消所有运行中的任务
            for site_id, task_id in self._running_tasks.items():
                await self.cancel_task(task_id, db)
            
            # 清理状态
            self._queues.clear()
            self._running_tasks.clear()
            self._task_info.clear()

# 全局队列管理器实例
queue_manager = QueueManager()