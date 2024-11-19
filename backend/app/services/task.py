from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.sqlalchemy.models import Task, TaskStatus
from app.models.pydantic.schemas import TaskCreate, TaskUpdate
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.api.websockets import manager

class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def list_tasks(
        self,
        skip: int = 0,
        limit: int = 10,
        status: Optional[List[TaskStatus]] = None
    ) -> List[Task]:
        query = select(Task)
        
        if status:
            query = query.filter(Task.status.in_(status))
            
        query = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_active_tasks(self) -> List[Task]:
        """获取所有活跃任务（运行中或暂停）"""
        return await self.list_tasks(
            status=[TaskStatus.RUNNING, TaskStatus.PAUSED],
            limit=None
        )
    
    async def create_task(self, task_id: str, task: TaskCreate) -> Task:
        db_task = Task(
            id=task_id,
            name=task.name,
            config=task.config,
            status=TaskStatus.PENDING,
            stats={
                "pages_crawled": 0,
                "items_scraped": 0,
                "start_time": None,
            }
        )
        self.db.add(db_task)
        await self.db.commit()
        await self.db.refresh(db_task)
        
        # 广播任务创建事件
        await self._broadcast_task_event(db_task, "task:created")
        return db_task
    
    async def get_task(self, task_id: str):
        query = select(Task).where(Task.id == task_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def update_task(self, task_id: str, task_update: TaskUpdate):
        task = await self.get_task(task_id)
        if not task:
            return None
            
        update_data = task_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(task, field, value)
            
        await self.db.commit()
        await self.db.refresh(task)
        return task
    
    async def delete_task(self, task_id: str):
        task = await self.get_task(task_id)
        if not task:
            return False
            
        await self.db.delete(task)
        await self.db.commit()
        return True
    
    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: Optional[int] = None,
        error: Optional[str] = None,
        stats_update: Optional[Dict[str, Any]] = None
    ) -> Optional[Task]:
        task = await self.get_task(task_id)
        if not task:
            return None
        
        # 更新状态
        old_status = task.status
        task.status = status
        
        # 更新进度
        if progress is not None:
            task.progress = progress
            
        # 更新错误信息
        if error is not None:
            task.error = error
            if task.stats.get("errors") is None:
                task.stats["errors"] = []
            task.stats["errors"].append({
                "message": error,
                "timestamp": datetime.now().isoformat()
            })
        
        # 更新统计信息
        if stats_update:
            task.stats.update(stats_update)
        
        # 处理特殊状态转换
        if old_status != status:
            if status == TaskStatus.RUNNING:
                if not task.stats.get("start_time"):
                    task.stats["start_time"] = datetime.now().isoformat()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]:
                task.stats["end_time"] = datetime.now().isoformat()
                if task.stats.get("start_time"):
                    start_time = datetime.fromisoformat(task.stats["start_time"])
                    end_time = datetime.fromisoformat(task.stats["end_time"])
                    task.stats["total_time"] = (end_time - start_time).total_seconds()
        
        await self.db.commit()
        await self.db.refresh(task)
        
        # 广播任务更新事件
        await self._broadcast_task_event(task, "task:updated")
        return task
    
    async def pause_task(self, task_id: str) -> Optional[Task]:
        """暂停任务"""
        task = await self.get_task(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return None
            
        return await self.update_task_status(
            task_id,
            TaskStatus.PAUSED,
            stats_update={"paused_at": datetime.now().isoformat()}
        )
    
    async def resume_task(self, task_id: str) -> Optional[Task]:
        """恢复任务"""
        task = await self.get_task(task_id)
        if not task or task.status != TaskStatus.PAUSED:
            return None
            
        return await self.update_task_status(
            task_id,
            TaskStatus.RUNNING,
            stats_update={"resumed_at": datetime.now().isoformat()}
        )
    
    async def stop_task(self, task_id: str) -> Optional[Task]:
        """停止任务"""
        task = await self.get_task(task_id)
        if not task or task.status not in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
            return None
            
        # 先将状态设置为正在停止
        await self.update_task_status(task_id, TaskStatus.STOPPING)
        return task
    
    async def _broadcast_task_event(self, task: Task, event_type: str):
        """广播任务事件"""
        await manager.broadcast("tasks", {
            "type": event_type,
            "data": {
                "taskId": task.id,
                "status": task.status.value,
                "progress": task.progress,
                "error": task.error,
                "stats": task.stats,
                "timestamp": datetime.now().isoformat()
            }
        })