import asyncio
import json
import signal
import uuid
import os
from datetime import datetime
from typing import Any, Dict, Optional, List
from pathlib import Path
from dotenv import load_dotenv

from process_manager import ProcessManager
from queue_manager import QueueManager
from utils.logger import get_logger, setup_logger
from ws_client import WebSocketClient


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
        
        # 加载所有站点配置
        self.sites = {}
        self._load_site_configs()
        
    def _load_site_configs(self):
        """加载所有站点配置"""
        config_dir = os.path.join(os.path.dirname(__file__),"config","site")
        
        # 遍历目录下的所有JSON文件
        for filename in os.listdir(config_dir):
            if filename.endswith('.json'):
                try:
                    # 读取JSON配置文件
                    with open(os.path.join(config_dir, filename), 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    site_id = config.get('site_id', '').lower()
                    if site_id:
                        self.sites[site_id] = {
                            'ws_client': WebSocketClient(crawler_id=site_id),
                            'queue_manager': QueueManager(),
                            'logger': get_logger(name=__name__, site_id=site_id),
                            'config': config
                        }
                        self.logger.info(f"Loaded configuration for site: {site_id}")
                except Exception as e:
                    self.logger.error(f"Error loading config from {filename}: {str(e)}")

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
            
            # 合并站点配置和任务配置
            task_config = {
                **site['config'],  # 基础站点配置
                **config  # 任务特定配置
            }
            task_data['config'] = task_config
            
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

    async def _handle_control_message(self, control_data: Dict[str, Any]):
        """统一处理控制消息"""
        try:
            control_type = control_data.get("control_type")
            if not control_type:
                self.logger.error("Invalid control data: missing control_type")
                return
            
            self.logger.info(f"Received control message: {control_type}")
            
            # 处理不同类型的��制消息
            if control_type == "stop":
                # 停止所有服务
                await self.stop()
                response_data = {"status": "stopping"}
            
            elif control_type == "get_configs":
                # 获取所有站点配置
                configs = {}
                for site_id, site in self.sites.items():
                    try:
                        site_config = await site['ws_client'].get_available_configs()
                        if site_config.get("status") == "success":
                            configs[site_id] = site_config.get("configs", {})
                    except Exception as e:
                        self.logger.error(f"Error getting config for site {site_id}: {str(e)}")
                
                response_data = {
                    "status": "success",
                    "configs": configs
                }
            
            elif control_type == "status":
                # 获取所有站点状态
                statuses = {}
                for site_id, site in self.sites.items():
                    try:
                        queue_size = await site['queue_manager'].get_queue_size()
                        process_info = self.process_manager.get_process_info()
                        statuses[site_id] = {
                            "status": "running" if process_info else "ready",
                            "queue_size": queue_size,
                            "process_info": process_info if process_info else {}
                        }
                    except Exception as e:
                        self.logger.error(f"Error getting status for site {site_id}: {str(e)}")
                        statuses[site_id] = {"status": "error", "error": str(e)}
                
                response_data = {
                    "status": "success",
                    "statuses": statuses
                }
            
            else:
                self.logger.warning(f"Unhandled control type: {control_type}")
                response_data = {
                    "status": "error",
                    "error": f"Unsupported control type: {control_type}"
                }
            
            # 向所有站点广播控制响应
            for site in self.sites.values():
                try:
                    await site['ws_client'].send_control_response(control_type, response_data)
                except Exception as e:
                    self.logger.error(f"Error sending control response: {str(e)}")
                    
        except Exception as e:
            self.logger.error(f"Error handling control message: {str(e)}")
            # 发送错误响应
            response_data = {
                "status": "error",
                "error": str(e)
            }
            for site in self.sites.values():
                try:
                    await site['ws_client'].send_control_response(control_type, response_data)
                except Exception as send_error:
                    self.logger.error(f"Error sending error response: {str(send_error)}")

    async def stop_site(self, site_id: str):
        """停止指定站点的服务"""
        try:
            site = self.sites.get(site_id)
            if not site:
                self.logger.error(f"Invalid site_id: {site_id}")
                return
                
            # 停止WebSocket客户端
            await site['ws_client'].disconnect()
            
            # 停止队列管理器
            await site['queue_manager'].stop()
            
            self.logger.info(f"Stopped services for site {site_id}")
            
        except Exception as e:
            self.logger.error(f"Error stopping services for site {site_id}: {str(e)}")

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
                            "status": "ready" if not process_info else "running",
                            "data": {
                                "queue_size": queue_size,
                                "process_info": process_info if process_info else {},
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        }
                        
                        # 发送控制响应
                        await site['ws_client'].send_control_response("status_update", status_data)
                        
                    except Exception as e:
                        site['logger'].error(f"Error updating status for site {site_id}: {str(e)}")
                
            except Exception as e:
                self.logger.error(f"Error in status update loop: {str(e)}")
            
            await asyncio.sleep(5)

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
                
                # 注册统一的控制消息处理器
                site['ws_client'].register_control_handler(
                    "control",  # 控制消息类型
                    lambda data: self._handle_control_message(data)  # 处理函数
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