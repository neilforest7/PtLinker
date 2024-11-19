import asyncio
import json
from typing import Dict, Any, Optional
from pathlib import Path
import subprocess
import sys
from app.core.config import settings
from app.services.task import TaskService, TaskStatus
from app.api.websockets import manager

class CrawlerManager:
    def __init__(self):
        self._crawlers = {}  # 存储活跃的爬虫进程
    
    async def start_crawler(self, task_id: str, config: Dict[str, Any], db_session):
        # 配置爬虫
        crawler_config = {
            "taskId": task_id,
            "startUrls": [config["start_url"]],
            "selectors": config["selectors"],
        }
        
        # 启动爬虫进程
        crawler_process = subprocess.Popen(...)
        
        # 监控进程
        asyncio.create_task(self._monitor_crawler(...))
    
    async def _monitor_crawler(
        self,
        task_id: str,
        process: subprocess.Popen,
        task_service: TaskService
    ):
        try:
            while True:
                # 检查进程是否还在运行
                if process.poll() is not None:
                    break
                
                # 读取输出
                output = process.stdout.readline()
                if output:
                    try:
                        data = json.loads(output)
                        if data["type"] == "progress":
                            await task_service.update_task_status(
                                task_id=task_id,
                                status=TaskStatus.RUNNING,
                                progress=data["progress"]
                            )
                        elif data["type"] == "log":
                            await manager.broadcast(f"logs_{task_id}", {
                                "type": "task:log",
                                "data": {
                                    "message": data["message"],
                                    "level": data["level"],
                                    "timestamp": data["timestamp"]
                                }
                            })
                    except json.JSONDecodeError:
                        # 普通日志输出
                        await manager.broadcast(f"logs_{task_id}", {
                            "type": "task:log",
                            "data": {
                                "message": output.strip(),
                                "level": "info",
                                "timestamp": None
                            }
                        })
                
                await asyncio.sleep(0.1)
            
            # 进程结束后检查退出码
            if process.returncode == 0:
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    progress=100
                )
            else:
                error = process.stderr.read()
                await task_service.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error=error
                )
                
        finally:
            # 清理资源
            if task_id in self._crawlers:
                del self._crawlers[task_id]
            
            # 删除配置文件
            config_path = Path(f"temp/config_{task_id}.json")
            if config_path.exists():
                config_path.unlink()
    
    async def stop_crawler(self, task_id: str) -> bool:
        if task_id in self._crawlers:
            process = self._crawlers[task_id]
            process.terminate()
            return True
        return False
    
    async def cleanup(self):
        # 停止所有爬虫进程
        for task_id, process in self._crawlers.items():
            process.terminate()
        self._crawlers.clear()
        
        # 清理临时文件
        temp_dir = Path("temp")
        if temp_dir.exists():
            for config_file in temp_dir.glob("config_*.json"):
                config_file.unlink() 