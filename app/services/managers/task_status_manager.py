import traceback
from datetime import datetime, timezone
from typing import Dict, Optional

from core.logger import get_logger
from models.models import Task, TaskStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TaskStatusManager:
    """任务状态管理器"""
    _instance = None
    
    def __init__(self):
        self.logger = get_logger(name=__name__, site_id="TaskStatMgr")
    
    @classmethod
    def get_instance(cls) -> 'TaskStatusManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def update_task_status(
        self,
        db: AsyncSession,
        task_id: str,
        status: TaskStatus,
        msg: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = datetime.now(),
        error_details: Optional[Dict] = None,
        task_metadata: Optional[Dict] = None,
        site_id: Optional[str] = None  # 用于日志记录
    ) -> bool:
        """更新任务状态
        
        Args:
            db: 数据库会话
            task_id: 任务ID
            status: 新的任务状态
            msg: 状态消息
            completed_at: 完成时间
            error_details: 详细错误信息
            task_metadata: 任务元数据
            site_id: 站点ID（可选，用于日志记录）
            
        Returns:
            bool: 更新是否成功
        """
        try:
            stmt = select(Task).where(Task.task_id == task_id)
            result = await db.execute(stmt)
            task = result.scalar_one_or_none()
            
            if task:
                task.status = status
                task.updated_at = datetime.now()
                
                if msg:
                    task.msg = msg
                if error_details:
                    task.error_details = error_details
                if completed_at:
                    task.completed_at = completed_at
                if updated_at:
                    task.updated_at = updated_at
                if task_metadata:
                    # 创建新的字典来触发SQLAlchemy的更改检测
                    current_metadata = dict(task.task_metadata or {})
                    current_metadata.update(task_metadata)
                    task.task_metadata = current_metadata  # 重新赋值整个字典
                    
                    self.logger.warning(f"更新后的 task_metadata: {task.task_metadata}")
                
                # 标记字段为已修改
                db.add(task)
                await db.commit()
                
                log_context = f"[站点: {site_id or task.site_id}] " if site_id or task.site_id else ""
                self.logger.info(f"{log_context}任务 {task_id} 状态更新为 {status.value}")
                if msg:
                    self.logger.debug(f"{log_context}任务状态消息: {msg}")
                
                return True
                
        except Exception as e:
            error_msg = str(e)
            log_context = f"[站点: {site_id}] " if site_id else ""
            self.logger.error(f"{log_context}更新任务 {task_id} 状态失败: {error_msg}")
            await db.rollback()
            return False
    
    async def get_task_status(self, db: AsyncSession, task_id: str) -> TaskStatus:
        """获取任务状态"""
        stmt = select(Task).where(Task.task_id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        return task.status if task else TaskStatus.READY

# 全局任务状态管理器实例
task_status_manager = TaskStatusManager.get_instance() 