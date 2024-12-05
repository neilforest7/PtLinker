import asyncio
import websockets
import json
from datetime import datetime
from loguru import logger
from typing import Optional, Dict, Any

class WebSocketStatusSink:
    def __init__(self, task_id: str, site_id: str):
        self.task_id = task_id
        self.site_id = site_id
        self.websocket = None
        self._connected = False
        self._status = "idle"
        self._result = None

    async def connect(self) -> bool:
        """连接到WebSocket服务器"""
        if self._connected:
            return True
            
        try:
            self.websocket = await websockets.connect(
                f"ws://localhost:8000/ws/tasks/{self.task_id}",
                ping_interval=20,
                ping_timeout=10
            )
            self._connected = True
            # 发送初始状态
            await self.update_status("idle")
            return True
        except Exception as e:
            print(f"Failed to connect to WebSocket status sink: {str(e)}")
            return False

    async def disconnect(self):
        """断开WebSocket连接"""
        self._connected = False
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None

    async def update_status(self, status: str, result: Dict[str, Any] = None):
        """更新爬虫状态"""
        if not self._connected:
            return

        self._status = status
        if result is not None:
            self._result = result

        message = {
            "type": "status",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "site_id": self.site_id,
                "status": self._status,
                "result": self._result
            }
        }

        try:
            await self.websocket.send(json.dumps(message))
        except Exception as e:
            print(f"Failed to send status update: {str(e)}")
            self._connected = False

class WebSocketLogSink:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.websocket = None
        self._queue = asyncio.Queue()
        self._task = None
        self._connected = False

    async def __call__(self, message):
        """处理loguru的日志消息"""
        try:
            record = message.record
            log_entry = {
                "type": "log",
                "timestamp": record["time"].isoformat(),
                "data": {
                    "level": record["level"].name.lower(),
                    "message": record["message"],
                    "metadata": {
                        "name": record["name"],
                        "function": record["function"],
                        "file": record["file"].name,
                        "line": record["line"],
                        "site_id": record.get("extra", {}).get("site_id", "unknown"),
                        "task_id": self.task_id
                    }
                }
            }
            
            # 如果已连接，将日志放入队列
            if self._connected:
                await self._queue.put(log_entry)
                
                # 如果发送任务还没启动，启动它
                if self._task is None or self._task.done():
                    self._task = asyncio.create_task(self._send_logs())
            
        except Exception as e:
            # 如果出错，记录到标准输出
            print(f"WebSocket log sink error: {str(e)}")

    async def _send_logs(self):
        """异步发送队列中的日志"""
        try:
            while self._connected:
                # 获取所有待发送的日志
                logs = []
                try:
                    while True:
                        log = self._queue.get_nowait()
                        logs.append(log)
                except asyncio.QueueEmpty:
                    if not logs:
                        await asyncio.sleep(0.1)
                        continue
                
                # 批量发送日志
                if logs:
                    try:
                        await self.websocket.send(json.dumps(logs))
                    except Exception as e:
                        print(f"Failed to send logs via WebSocket: {str(e)}")
                        self._connected = False
                        break
        
        except Exception as e:
            print(f"WebSocket log sender error: {str(e)}")
            self._connected = False

    async def connect(self) -> bool:
        """连接到WebSocket服务器"""
        if self._connected:
            return True
            
        try:
            self.websocket = await websockets.connect(
                f"ws://localhost:8000/ws/tasks/{self.task_id}",
                ping_interval=20,
                ping_timeout=10
            )
            self._connected = True
            
            # 添加到loguru
            logger.configure(handlers=[{"sink": self}])
            
            return True
        except Exception as e:
            print(f"Failed to connect to WebSocket: {str(e)}")
            return False

    async def disconnect(self):
        """断开WebSocket连接"""
        self._connected = False
        
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None
            
        # 取消发送任务
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None