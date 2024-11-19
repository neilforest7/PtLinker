from app.services.crawler_manager import CrawlerManager
from app.db.session import AsyncSessionLocal
from typing import Dict, Any

class CrawlerStatus:
    _tasks = {}

    @classmethod
    def set_status(cls, task_id: str, status: dict):
        cls._tasks[task_id] = status

    @classmethod
    def get_status(cls, task_id: str):
        return cls._tasks.get(task_id)

class CrawlerWorker:
    @classmethod
    async def start_task(cls, task_id: str, config: Dict[str, Any]):
        CrawlerStatus.set_status(task_id, {
            "status": "processing"
        })
        return task_id
    
    @classmethod
    def get_task_status(cls, task_id: str):
        return CrawlerStatus.get_status(task_id)
    
    @classmethod
    async def crawl(cls, task_id: str, config: Dict[str, Any]):
        async with AsyncSessionLocal() as db:
            crawler_manager = CrawlerManager()
            try:
                success = await crawler_manager.start_crawler(task_id, config, db)
                status = {
                    "status": "success" if success else "error",
                    "task_id": task_id
                }
            except Exception as e:
                status = {
                    "status": "error",
                    "task_id": task_id,
                    "error": str(e)
                }
            
            CrawlerStatus.set_status(task_id, status)
            return status
 