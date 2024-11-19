from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set, List, Any
import json
from app.core.config import settings

ws_router = APIRouter()

# 连接管理器
class ConnectionManager:
    def __init__(self):
        # 所有活跃连接
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "tasks": set(),  # 任务状态订阅
            "logs": set(),   # 日志订阅
        }
    
    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
    
    def disconnect(self, websocket: WebSocket, channel: str):
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
    
    async def broadcast(self, channel: str, message: dict):
        if channel not in self.active_connections:
            return
        
        dead_connections = set()
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                dead_connections.add(connection)
        
        # 清理断开的连接
        for dead in dead_connections:
            self.active_connections[channel].discard(dead)

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def broadcast(self, channel: str, message: Any):
        if channel in self.active_connections:
            for connection in self.active_connections[channel]:
                await connection.send_json(message)

manager = ConnectionManager()

@ws_router.websocket("/ws/tasks")
async def websocket_tasks(websocket: WebSocket):
    await manager.connect(websocket, "tasks")
    try:
        while True:
            # 保持连接活跃
            data = await websocket.receive_text()
            # 可以处理客户端发来的消息，如心跳检测
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, "tasks")

@ws_router.websocket("/ws/logs/{task_id}")
async def websocket_logs(websocket: WebSocket, task_id: str):
    channel = f"logs_{task_id}"
    await manager.connect(websocket, channel)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel) 