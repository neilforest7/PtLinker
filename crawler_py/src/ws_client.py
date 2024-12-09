import asyncio
import json
import websockets
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Awaitable
from utils.logger import get_logger

class WebSocketClient:
    def __init__(self, crawler_id: str, base_url: str = "ws://localhost:8000"):
        self.base_url = base_url
        self.crawler_id = crawler_id
        self.websocket = None
        self.connected = False
        self.reconnect_interval = 5  # 重连间隔（秒）
        self.logger = get_logger(name=__name__, site_id=crawler_id)
        self._stop_event = asyncio.Event()
        self._heartbeat_task = None
        self._task_handlers = {}
        self._control_handlers = {}
        self._start_time = time.time()  # 初始化启动时间

    def register_task_handler(self, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """注册任务处理器"""
        self._task_handlers["task"] = handler
        self.logger.debug("Task handler registered")

    def register_control_handler(self, control_type: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """注册控制消息处���器"""
        self._control_handlers[control_type] = handler
        self.logger.debug(f"Control handler registered for type: {control_type}")

    async def connect(self) -> bool:
        """连接到WebSocket服务器"""
        if self.connected:
            return True

        try:
            self.logger.info(f"Connecting to WebSocket server with crawler_id: {self.crawler_id}")
            self.websocket = await websockets.connect(
                f"{self.base_url}/ws/crawler",
                ping_interval=20,
                ping_timeout=10,
                max_size=None  # 允许接收大消息
            )
            
            # 发送认证消息
            auth_message = {
                "type": "auth",
                "crawler_id": self.crawler_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.logger.debug(f"Sending auth message: {auth_message}")
            await self.websocket.send(json.dumps(auth_message))
            
            # 等待认证响应
            response = await self.websocket.recv()
            response_data = json.loads(response)
            self.logger.debug(f"Received auth response: {response_data}")
            
            if response_data.get("type") == "auth" and response_data.get("status") == "success":
                self.connected = True
                self.logger.info("Successfully connected and authenticated to WebSocket server")
                
                # 启动心跳任务
                if self._heartbeat_task is None or self._heartbeat_task.done():
                    self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                    self._start_time = time.time()  # 重置启动时间
                
                return True
            else:
                self.logger.error("Authentication failed")
                await self.websocket.close()
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to WebSocket server: {str(e)}", exc_info=True)
            return False

    async def disconnect(self):
        """断开WebSocket连接"""
        self._stop_event.set()
        
        if self._heartbeat_task:
            try:
                self._heartbeat_task.cancel()
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self.websocket:
            try:
                await self.websocket.close()
                self.logger.info("WebSocket connection closed")
            except Exception as e:
                self.logger.error(f"Error closing WebSocket connection: {str(e)}")
            finally:
                self.websocket = None
                self.connected = False

    async def _heartbeat_loop(self):
        """发送心跳包"""
        while not self._stop_event.is_set():
            try:
                if self.connected:
                    await self.send_status("heartbeat", {
                        "timestamp": datetime.utcnow().isoformat(),
                        "uptime": self._get_uptime()
                    })
                await asyncio.sleep(60)  # 每60秒发送一次心跳
            except Exception as e:
                self.logger.error(f"Heartbeat error: {str(e)}")
                await asyncio.sleep(5)

    async def reconnect(self):
        """重新连接服务器"""
        while not self._stop_event.is_set():
            if not self.connected:
                self.logger.info("Attempting to reconnect...")
                if await self.connect():
                    break
                await asyncio.sleep(self.reconnect_interval)

    async def send_status(self, status: str, data: Optional[Dict[str, Any]] = None):
        """发送状态更新"""
        if not self.websocket:
            self.logger.error("WebSocket connection not established")
            return False
            
        try:
            # 构建状态消息
            message = {
                "type": "status",
                "status": status,
                "data": {
                    "crawler_id": self.crawler_id,
                    "status": status,
                    "timestamp": datetime.utcnow().isoformat(),
                    **(data or {})
                }
            }
            
            await self.websocket.send(json.dumps(message))
            self.logger.debug(f"Status sent: {status}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send status: {str(e)}")
            return False

    async def send_log(self, level: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        """发送志消息"""
        if not self.connected:
            return

        log_message = {
            "type": "log",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "level": level,
                "message": message,
                "metadata": metadata or {}
            }
        }

        try:
            await self.websocket.send(json.dumps(log_message))
        except Exception as e:
            self.logger.error(f"Failed to send log: {str(e)}")
            self.connected = False
            asyncio.create_task(self.reconnect())

    async def receive_messages(self):
        """接收并处理消息"""
        while not self._stop_event.is_set():
            try:
                if not self.connected:
                    await self.reconnect()
                    continue

                message = await self.websocket.recv()
                data = json.loads(message)
                self.logger.debug(f"Received message: {data}")
                
                # 处理不同类型的消息
                message_type = data.get("type")
                if message_type == "task":
                    await self._handle_task_message(data.get("data", {}))
                elif message_type == "control":
                    await self._handle_control_message(data.get("data", {}))
                else:
                    self.logger.warning(f"Unknown message type: {message_type}")
                
            except websockets.ConnectionClosed:
                self.logger.warning("WebSocket connection closed")
                self.connected = False
            except json.JSONDecodeError:
                self.logger.error("Invalid JSON message received")
            except Exception as e:
                self.logger.error(f"Error processing message: {str(e)}")
                await asyncio.sleep(1)

    async def _handle_task_message(self, data: Dict[str, Any]):
        """处理任务消息"""
        try:
            task_id = data.get("task_id")
            if not task_id:
                self.logger.error("Received task message without task_id")
                return

            self.logger.info(f"Processing task: {task_id}")
            
            # 发送任务接收确认
            await self.send_status("task_received", {
                "task_id": task_id,
                "received_at": datetime.utcnow().isoformat()
            })

            # 调用注册的任务处理器
            handler = self._task_handlers.get("task")
            if handler:
                try:
                    await handler(data)
                except Exception as e:
                    self.logger.error(f"Task handler error for task {task_id}: {str(e)}")
                    # 发送任务失败状态
                    await self.send_status("task_failed", {
                        "task_id": task_id,
                        "error": str(e),
                        "failed_at": datetime.utcnow().isoformat()
                    })
            else:
                self.logger.warning("No task handler registered")
                await self.send_status("task_rejected", {
                    "task_id": task_id,
                    "reason": "No task handler available"
                })

        except Exception as e:
            self.logger.error(f"Error handling task message: {str(e)}")

    async def _handle_control_message(self, data: Dict[str, Any]):
        """处理控制消息"""
        try:
            control_type = data.get("control_type")
            if not control_type:
                self.logger.error("Received control message without control_type")
                return

            self.logger.info(f"Processing control message: {control_type}")

            # 处理内置控制命令
            if control_type == "ping":
                await self.send_status("pong", {
                    "timestamp": datetime.utcnow().isoformat()
                })
                return

            if control_type == "stop":
                await self.send_status("stopping", {
                    "timestamp": datetime.utcnow().isoformat()
                })
                self._stop_event.set()
                return

            # 调用注册的控制消息处理器
            handler = self._control_handlers.get(control_type)
            if handler:
                try:
                    await handler(data)
                except Exception as e:
                    self.logger.error(f"Control handler error for type {control_type}: {str(e)}")
                    await self.send_status("control_failed", {
                        "control_type": control_type,
                        "error": str(e)
                    })
            else:
                self.logger.warning(f"No handler registered for control type: {control_type}")
                await self.send_status("control_rejected", {
                    "control_type": control_type,
                    "reason": "Unsupported control type"
                })

        except Exception as e:
            self.logger.error(f"Error handling control message: {str(e)}")

    def _get_uptime(self) -> float:
        """获取服务运行时间（秒）"""
        return time.time() - self._start_time

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._start_time = time.time()
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.disconnect()