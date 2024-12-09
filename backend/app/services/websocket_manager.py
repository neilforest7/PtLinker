from typing import Dict, Set
from fastapi import WebSocket
import json
from datetime import datetime
from app.core.logger import get_logger
from app.models.task import Task, TaskStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class ConnectionManager:
    def __init__(self):
        # 存储爬虫连接
        self.crawler_connections: Dict[str, WebSocket] = {}
        # 存储任务监控连接
        self.task_connections: Dict[str, Set[WebSocket]] = {}
        self.logger = get_logger(service="websocket_manager")

    async def connect(self, crawler_id: str, websocket: WebSocket):
        """注册爬虫连接"""
        self.crawler_connections[crawler_id] = websocket
        self.logger.info(f"Crawler {crawler_id} connected")

    async def disconnect(self, crawler_id: str):
        """断开爬虫连接"""
        if crawler_id in self.crawler_connections:
            del self.crawler_connections[crawler_id]
            self.logger.info(f"Crawler {crawler_id} disconnected")

    async def connect_task(self, task_id: str, websocket: WebSocket):
        """注册任���监控连接"""
        if task_id not in self.task_connections:
            self.task_connections[task_id] = set()
        self.task_connections[task_id].add(websocket)
        self.logger.info(f"Task monitor connected for task {task_id}")

    async def disconnect_task(self, task_id: str):
        """断开任务监控连接"""
        if task_id in self.task_connections:
            del self.task_connections[task_id]
            self.logger.info(f"Task monitor disconnected for task {task_id}")

    async def send_to_crawler(self, crawler_id: str, message_type: str, data: dict):
        """向特定爬虫发送消息"""
        if crawler_id not in self.crawler_connections:
            error_msg = f"Crawler {crawler_id} not connected"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        message = {
            "type": message_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        try:
            await self.crawler_connections[crawler_id].send_json(message)
            self.logger.debug(f"Message sent to crawler {crawler_id}: {message_type}")
        except Exception as e:
            self.logger.error(f"Failed to send message to crawler {crawler_id}: {str(e)}")
            del self.crawler_connections[crawler_id]
            raise RuntimeError(f"Failed to send message to crawler: {str(e)}")

    async def broadcast_to_task(self, task_id: str, message_type: str, data: dict):
        """向任务的所有监控连接广播消息"""
        if task_id not in self.task_connections:
            return
        
        message = {
            "type": message_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        failed_connections = set()
        for connection in self.task_connections[task_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                self.logger.error(f"Failed to send message to task monitor: {str(e)}")
                failed_connections.add(connection)
        
        # 清理失败的连接
        for connection in failed_connections:
            self.task_connections[task_id].remove(connection)

    async def send_log(self, task_id: str, level: str, message: str, metadata: dict = None):
        """发送日志消息到任务监控"""
        await self.broadcast_to_task(task_id, "log", {
            "level": level,
            "message": message,
            "metadata": metadata or {}
        })

    async def send_status(self, task_id: str, status: str, data: dict = None):
        """发送状态更新到任务监控"""
        data = data or {}
        status_data = {
            "task_id": task_id,
            "status": status
        }
        status_data.update(data)
        await self.broadcast_to_task(task_id, "status", status_data)

    async def send_task_status(self, task_id: str, db: AsyncSession):
        """发送当前任务状态"""
        # 从数据库获取任务状态
        stmt = select(Task).where(Task.task_id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            self.logger.warning(f"Task {task_id} not found in database")
            await self.send_status(task_id, "not_found", {
                "task_id": task_id,
                "error": "Task not found"
            })
            return
            
        # 构建任务状态数据
        status_data = {
            "task_id": task_id,
            "status": task.status.value if task.status else "unknown",
            "crawler_id": task.crawler_id,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if hasattr(task, 'started_at') and task.started_at else None,
            "completed_at": task.completed_at.isoformat() if hasattr(task, 'completed_at') and task.completed_at else None,
            "error": task.error if task.error else None,
            "result": task.result if task.result else None
        }
        
        await self.send_status(task_id, status_data["status"], status_data)

# 创建全局连接管理器实例
manager = ConnectionManager() 