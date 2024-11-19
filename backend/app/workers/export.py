import json
import os
from datetime import datetime
from typing import Optional

import pandas as pd
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.data import DataService


class ExportStatus:
    _tasks = {}  # 使用内存存储任务状态

    @classmethod
    def set_status(cls, task_id: str, status: dict):
        cls._tasks[task_id] = status

    @classmethod
    def get_status(cls, task_id: str):
        return cls._tasks.get(task_id)

class ExportWorker:
    @classmethod
    async def start_export(cls, format: str, task_id: Optional[str] = None):
        export_task_id = f"export_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        ExportStatus.set_status(export_task_id, {
            "status": "processing"
        })
        return export_task_id
    
    @classmethod
    def get_task_status(cls, task_id: str):
        return ExportStatus.get_status(task_id)
    
    @classmethod
    async def export(cls, task_id: str, format: str, filter_task_id: Optional[str] = None):
        try:
            async with AsyncSessionLocal() as db:
                data_service = DataService(db)
                data = await data_service.list_data(
                    task_id=filter_task_id,
                    limit=None  # 导出所有数据
                )
            
            # 准备导出文件路径
            filename = f"export_{task_id}.{format}"
            filepath = os.path.join(settings.EXPORT_DIR, filename)
            
            # 转换数据格式
            if format == "csv":
                df = pd.DataFrame([d.data for d in data])
                df.to_csv(filepath, index=False)
            elif format == "json":
                with open(filepath, 'w') as f:
                    json.dump([d.data for d in data], f)
            elif format == "excel":
                df = pd.DataFrame([d.data for d in data])
                df.to_excel(filepath, index=False)
            
            # 更新任务状态
            status = {
                "status": "completed",
                "downloadUrl": f"/exports/{filename}"
            }
            ExportStatus.set_status(task_id, status)
            
            return status
            
        except Exception as e:
            status = {
                "status": "failed",
                "error": str(e)
            }
            ExportStatus.set_status(task_id, status)
            return status