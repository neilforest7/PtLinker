import asyncio
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime
from utils.logger import get_logger

class QueueManager:
    def __init__(
        self,
        max_batch_size: int = 5,
        max_queue_size: int = 100,
        batch_interval: float = 1.0
    ):
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        self.max_batch_size = max_batch_size
        self.batch_interval = batch_interval
        self.logger = get_logger(name=__name__, site_id="queue_manager")
        self._stop_event = asyncio.Event()
        self._processing = False
        self._task_handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]] = {}
        self._tasks_info: Dict[str, Dict[str, Any]] = {}  # 存储任务信息

    async def start(self):
        """启动队列处理"""
        if self._processing:
            return
            
        self._processing = True
        self._stop_event.clear()
        self.logger.info("Queue manager started")
        asyncio.create_task(self._process_queue())

    async def stop(self):
        """停止队列处理并清理所有任务"""
        self._stop_event.set()
        self._processing = False
        self.logger.info("Queue manager stopping...")
        
        # 获取所有待处理的任务ID
        pending_tasks = []
        while not self.queue.empty():
            try:
                task = self.queue.get_nowait()
                task_id = task.get("task_id")
                if task_id:
                    pending_tasks.append(task_id)
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break
                
        # 清理任务信息
        self._tasks_info.clear()
        
        self.logger.info(f"Queue manager stopped, {len(pending_tasks)} tasks cleared")
        return pending_tasks

    async def add_task(self, task_data: Dict[str, Any]) -> bool:
        """添加任务到队列"""
        try:
            task_id = task_data.get("task_id")
            if not task_id:
                self.logger.error("Task ID is required")
                return False
                
            # 添加时间戳和状态信息
            task_data["queued_at"] = datetime.utcnow().isoformat()
            self._tasks_info[task_id] = {
                "status": "queued",
                "queued_at": task_data["queued_at"],
                "task_type": task_data.get("type", "unknown")
            }
            
            # 尝试添加到队列
            await self.queue.put(task_data)
            self.logger.info(f"Task added to queue: {task_id}")
            return True
            
        except asyncio.QueueFull:
            self.logger.error("Queue is full, task rejected")
            return False
        except Exception as e:
            self.logger.error(f"Failed to add task to queue: {str(e)}")
            return False

    def register_handler(self, task_type: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """注册任务处理器"""
        self._task_handlers[task_type] = handler
        self.logger.debug(f"Registered handler for task type: {task_type}")

    async def _process_queue(self):
        """处理队列中的任务"""
        while not self._stop_event.is_set():
            try:
                # 收集一批任务
                batch = await self._collect_batch()
                if not batch:
                    await asyncio.sleep(self.batch_interval)
                    continue

                # 按类型分组任务
                tasks_by_type = self._group_tasks_by_type(batch)
                
                # 处理每种类型的任务
                for task_type, tasks in tasks_by_type.items():
                    handler = self._task_handlers.get(task_type)
                    if handler:
                        try:
                            await handler(tasks)
                            self.logger.info(f"Processed {len(tasks)} tasks of type {task_type}")
                        except Exception as e:
                            self.logger.error(f"Error processing tasks of type {task_type}: {str(e)}")
                    else:
                        self.logger.warning(f"No handler registered for task type: {task_type}")

            except Exception as e:
                self.logger.error(f"Error in queue processing: {str(e)}")
                await asyncio.sleep(1)

    async def _collect_batch(self) -> List[Dict[str, Any]]:
        """收集一批任务"""
        batch = []
        try:
            # 获取第一个任务（阻塞）
            first_task = await self.queue.get()
            batch.append(first_task)
            
            # 非阻塞地收集更多任务
            while len(batch) < self.max_batch_size:
                try:
                    task = self.queue.get_nowait()
                    batch.append(task)
                except asyncio.QueueEmpty:
                    break
                    
        except Exception as e:
            self.logger.error(f"Error collecting batch: {str(e)}")
            
        return batch

    def _group_tasks_by_type(self, tasks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按类型分组任务"""
        grouped = {}
        for task in tasks:
            task_type = task.get("type", "default")
            if task_type not in grouped:
                grouped[task_type] = []
            grouped[task_type].append(task)
        return grouped

    async def get_queue_size(self) -> int:
        """获取当前队列大小"""
        return self.queue.qsize()

    def is_queue_full(self) -> bool:
        """检查队列是否已满"""
        return self.queue.full()

    def is_queue_empty(self) -> bool:
        """检查队列是否为空"""
        return self.queue.empty()

    async def get_queue_status(self) -> Dict[str, Any]:
        """获取队列的详细状态"""
        try:
            current_size = self.queue.qsize()
            return {
                "queue_size": current_size,
                "max_size": self.queue.maxsize,
                "is_full": self.queue.full(),
                "is_empty": self.queue.empty(),
                "is_processing": self._processing,
                "tasks_info": self._tasks_info,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error getting queue status: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def remove_task(self, task_id: str) -> bool:
        """从队列中移除指定的任务"""
        try:
            # 创建临时队列
            temp_queue = asyncio.Queue(maxsize=self.queue.maxsize)
            removed = False
            
            # 遍历原队列
            while not self.queue.empty():
                try:
                    task = self.queue.get_nowait()
                    if task.get("task_id") != task_id:
                        await temp_queue.put(task)
                    else:
                        removed = True
                        self._tasks_info.pop(task_id, None)
                except asyncio.QueueEmpty:
                    break
            
            # 恢复队列
            while not temp_queue.empty():
                try:
                    task = temp_queue.get_nowait()
                    await self.queue.put(task)
                except asyncio.QueueEmpty:
                    break
            
            if removed:
                self.logger.info(f"Task {task_id} removed from queue")
            return removed
            
        except Exception as e:
            self.logger.error(f"Error removing task {task_id}: {str(e)}")
            return False
 