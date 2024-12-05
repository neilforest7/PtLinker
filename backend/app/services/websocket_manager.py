from typing import Dict, Set
from fastapi import WebSocket
import json
from datetime import datetime
from app.core.logger import get_logger

class ConnectionManager:
    def __init__(self):
        # 存储每个任务的活跃连接
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.logger = get_logger(service="websocket_manager")

    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = set()
        self.active_connections[task_id].add(websocket)
        self.logger.info(f"WebSocket connection established for task {task_id}")

    async def disconnect(self, websocket: WebSocket, task_id: str):
        self.active_connections[task_id].remove(websocket)
        if not self.active_connections[task_id]:
            del self.active_connections[task_id]
        self.logger.info(f"WebSocket connection closed for task {task_id}")

    async def broadcast_to_task(self, task_id: str, message_type: str, data: dict):
        if task_id not in self.active_connections:
            self.logger.debug(f"No active connections for task {task_id}")
            return
        
        message = {
            "type": message_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        # 将消息发送给所有订阅该任务的连接
        failed_connections = set()
        for connection in self.active_connections[task_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                self.logger.error(f"Failed to send message to connection for task {task_id}: {str(e)}")
                failed_connections.add(connection)
        
        # 清理失败的连接
        for connection in failed_connections:
            self.active_connections[task_id].remove(connection)
            self.logger.warning(f"Removed failed connection for task {task_id}")

    async def send_log(self, task_id: str, level: str, message: str, metadata: dict = None):
        """发送日志消息"""
        logger_ctx = get_logger(task_id=task_id)
        logger_ctx.log(level, message)
        await self.broadcast_to_task(task_id, "log", {
            "level": level,
            "message": message,
            "metadata": metadata or {}
        })

    async def send_status(self, task_id: str, status: str, progress: dict = None):
        """发送状态更新"""
        logger_ctx = get_logger(task_id=task_id)
        logger_ctx.info(f"Task status updated to: {status}")
        await self.broadcast_to_task(task_id, "status", {
            "status": status,
            "progress": progress or {}
        })

# 创建全局连接管理器实例
manager = ConnectionManager() 