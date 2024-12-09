import asyncio
import json
import signal
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, List
from pathlib import Path
from dotenv import load_dotenv

from process_manager import ProcessManager
from queue_manager import QueueManager
from utils.logger import get_logger, setup_logger
from ws_client import WebSocketClient
from main import SITE_CONFIGS


class CrawlerService:
    """爬虫服务类"""
    def __init__(self):
        # 加载环境变量
        env_path = Path(__file__).parent.parent / '.env'
        load_dotenv(env_path)
        
        self.logger = get_logger(name=__name__, site_id="main")
        self._stop_event = asyncio.Event()
        self._status_update_task = None
        
        # 创建一个共享的进程管理器
        self.process_manager = ProcessManager()
        
        # 为每个站点创建WebSocket客户端和队列管理器
        self.sites = {}
        for site_id in SITE_CONFIGS.keys():
            site_id = site_id.lower()
            self.sites[site_id] = {
                'ws_client': WebSocketClient(crawler_id=site_id),
                'queue_manager': QueueManager(),
                'logger': get_logger(name=__name__, site_id=site_id)
            }
            self.logger.info(f"Initialized services for site: {site_id}")

    async def _handle_task(self, task_data: Dict[str, Any], site_id: str):
        """处理接收到的任务"""
        try:
            task_id = task_data.get("task_id")
            config = task_data.get("config", {})
            site = self.sites.get(site_id)
            
            if not task_id or not site:
                self.logger.error(f"Invalid task data: missing task_id or invalid site_id: {site_id}")
                return
            
            site['logger'].info(f"Received task {task_id} for site {site_id}")
            
            # 发送任务开始状态
            await site['ws_client'].send_status("task_started", {
                "task_id": task_id,
                "site_id": site_id,
                "started_at": datetime.utcnow().isoformat()
            })
            
            # 执行爬虫任务
            try:
                result = await self.process_manager.execute_task(task_data)
                site['logger'].info(f"Task {task_id} completed successfully")
                
                # 发送任务完成状态
                await site['ws_client'].send_status("task_completed", {
                    "task_id": task_id,
                    "site_id": site_id,
                    "result": result,
                    "completed_at": datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                error_msg = f"Failed to execute task {task_id}: {str(e)}"
                site['logger'].error(error_msg)
                await site['ws_client'].send_status("task_failed", {
                    "task_id": task_id,
                    "site_id": site_id,
                    "error": error_msg,
                    "failed_at": datetime.utcnow().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error handling task for site {site_id}: {str(e)}")
            if task_id:
                await self.sites[site_id]['ws_client'].send_status("task_failed", {
                    "task_id": task_id,
                    "error": str(e),
                    "failed_at": datetime.utcnow().isoformat()
                })

    async def _update_status_loop(self):
        """定期更新所有爬虫状态"""
        while not self._stop_event.is_set():
            try:
                for site_id, site in self.sites.items():
                    try:
                        # 获取队列状态
                        queue_size = await site['queue_manager'].get_queue_size()
                        
                        # 获取进程状态
                        try:
                            process_info = self.process_manager.get_process_info()
                        except Exception as e:
                            site['logger'].warning(f"Failed to get process info: {str(e)}")
                            process_info = None
                        
                        # 构建状态数据
                        status_data = {
                            "crawler_id": site_id,
                            "status": "ready",  # 默认状态为ready
                            "queue_size": queue_size,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
                        # 如果有进程信息，添加到状态数据中
                        if process_info:
                            status_data["status"] = "running"
                            status_data["process_info"] = process_info
                        
                        # 发送状态更新
                        await site['ws_client'].send_status("status_update", status_data)
                        
                    except Exception as e:
                        site['logger'].error(f"Error updating status for site {site_id}: {str(e)}")
                
            except Exception as e:
                self.logger.error(f"Error in status update loop: {str(e)}")
            
            # 等待下一次更新
            await asyncio.sleep(5)  # 每5秒更新一次状态

    async def start(self):
        """启动所有站点的服务"""
        self.logger.info("Starting crawler services for all sites")
        
        # 首先启动进程管理器
        try:
            await self.process_manager.start()
            self.logger.info("Process manager started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start process manager: {str(e)}")
            raise
        
        # 启动所有站点的服务
        for site_id, site in self.sites.items():
            try:
                # 连接WebSocket
                if not await site['ws_client'].connect():
                    self.logger.error(f"Failed to connect WebSocket for site {site_id}")
                    continue
                    
                # 注册任务处理器
                site['ws_client'].register_task_handler(
                    lambda data, sid=site_id: self._handle_task(data, sid)
                )
                
                # 启动消息接收循环
                asyncio.create_task(site['ws_client'].receive_messages())
                
                self.logger.info(f"Started services for site {site_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to start services for site {site_id}: {str(e)}")
        
        # 启动状态更新循环
        self._status_update_task = asyncio.create_task(self._update_status_loop())
        
        self.logger.info("All crawler services started successfully")

    async def stop(self):
        """停止所有站点的服务"""
        self.logger.info("Stopping all crawler services...")
        self._stop_event.set()
        
        # 取消状态更新任务
        if self._status_update_task:
            self._status_update_task.cancel()
            try:
                await self._status_update_task
            except asyncio.CancelledError:
                pass
        
        # 停止所有站点的服务
        for site_id, site in self.sites.items():
            try:
                # 停止WebSocket客户端
                await site['ws_client'].disconnect()
                
                # 停止队列管理器
                await site['queue_manager'].stop()
                
                self.logger.info(f"Stopped services for site {site_id}")
                
            except Exception as e:
                self.logger.error(f"Error stopping services for site {site_id}: {str(e)}")
        
        # 最后停止进程管理器
        try:
            await self.process_manager.stop()
            self.logger.info("Process manager stopped")
        except Exception as e:
            self.logger.error(f"Error stopping process manager: {str(e)}")
        
        self.logger.info("All crawler services stopped")

    def _signal_handler(self, signum, frame):
        """处理系统信号"""
        self.logger.info(f"Received signal {signum}")
        asyncio.create_task(self.stop())