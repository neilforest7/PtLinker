import uuid
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.log import TaskLog, LogLevel

class TaskLogger:
    def __init__(self, db: AsyncSession, task_id: str):
        self.db = db
        self.task_id = task_id
        self._batch_logs: List[TaskLog] = []

    async def _log(self, level: LogLevel, message: str):
        log = TaskLog(
            log_id=str(uuid.uuid4()),
            task_id=self.task_id,
            level=level,
            message=message
        )
        self.db.add(log)
        await self.db.commit()

    async def _batch_log(self, level: LogLevel, message: str):
        """添加日志到批处理队列"""
        log = TaskLog(
            log_id=str(uuid.uuid4()),
            task_id=self.task_id,
            level=level,
            message=message
        )
        self._batch_logs.append(log)

    async def flush(self):
        """将批处理队列中的日志写入数据库"""
        if not self._batch_logs:
            return
        
        self.db.add_all(self._batch_logs)
        await self.db.commit()
        self._batch_logs.clear()

    async def debug(self, message: str, batch: bool = False):
        if batch:
            await self._batch_log(LogLevel.DEBUG, message)
        else:
            await self._log(LogLevel.DEBUG, message)

    async def info(self, message: str, batch: bool = False):
        if batch:
            await self._batch_log(LogLevel.INFO, message)
        else:
            await self._log(LogLevel.INFO, message)

    async def warning(self, message: str, batch: bool = False):
        if batch:
            await self._batch_log(LogLevel.WARNING, message)
        else:
            await self._log(LogLevel.WARNING, message)

    async def error(self, message: str, batch: bool = False):
        if batch:
            await self._batch_log(LogLevel.ERROR, message)
        else:
            await self._log(LogLevel.ERROR, message)

    async def log_dict(self, data: Dict[str, Any], level: LogLevel = LogLevel.INFO):
        """记录字典数据为格式化的日志"""
        for key, value in data.items():
            await self.info(f"{key}: {value}", batch=True)
        await self.flush() 