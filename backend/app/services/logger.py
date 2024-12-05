import uuid
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.log import TaskLog, LogLevel
from app.core.logger import get_logger

class TaskLogger:
    def __init__(self, db: AsyncSession, task_id: str):
        self.db = db
        self.task_id = task_id
        self._batch_logs: List[TaskLog] = []
        self.logger = get_logger(task_id=task_id)

    async def _save_to_db(self, level: LogLevel, message: str) -> None:
        """保存日志到数据库"""
        log = TaskLog(
            log_id=str(uuid.uuid4()),
            task_id=self.task_id,
            level=level,
            message=message
        )
        self.db.add(log)
        await self.db.commit()

    async def _batch_save(self, level: LogLevel, message: str) -> None:
        """添加日志到批处理队列"""
        log = TaskLog(
            log_id=str(uuid.uuid4()),
            task_id=self.task_id,
            level=level,
            message=message
        )
        self._batch_logs.append(log)

    async def flush(self) -> None:
        """将批处理队列中的日志写入数据库"""
        if not self._batch_logs:
            return
        
        self.db.add_all(self._batch_logs)
        await self.db.commit()
        self._batch_logs.clear()

    async def debug(self, message: str, batch: bool = False) -> None:
        """记录调试级别的日志"""
        self.logger.debug(message)
        if batch:
            await self._batch_save(LogLevel.DEBUG, message)
        else:
            await self._save_to_db(LogLevel.DEBUG, message)

    async def info(self, message: str, batch: bool = False) -> None:
        """记录信息级别的日志"""
        self.logger.info(message)
        if batch:
            await self._batch_save(LogLevel.INFO, message)
        else:
            await self._save_to_db(LogLevel.INFO, message)

    async def warning(self, message: str, batch: bool = False) -> None:
        """记录警告级别的日志"""
        self.logger.warning(message)
        if batch:
            await self._batch_save(LogLevel.WARNING, message)
        else:
            await self._save_to_db(LogLevel.WARNING, message)

    async def error(self, message: str, batch: bool = False) -> None:
        """记录错误级别的日志"""
        self.logger.error(message)
        if batch:
            await self._batch_save(LogLevel.ERROR, message)
        else:
            await self._save_to_db(LogLevel.ERROR, message)

    async def log_dict(self, data: Dict[str, Any], level: LogLevel = LogLevel.INFO) -> None:
        """记录字典数据为格式化的日志"""
        log_func = getattr(self.logger, level.name.lower())
        for key, value in data.items():
            message = f"{key}: {value}"
            log_func(message)
            await self._batch_save(level, message)
        await self.flush() 