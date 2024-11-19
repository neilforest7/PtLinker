from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from app.db.session import get_db
from app.models.pydantic.schemas import CrawledDataInDB
from app.services.data import DataService
from app.workers.export import ExportWorker

router = APIRouter()

@router.get("/", response_model=List[CrawledDataInDB])
async def list_data(
    skip: int = 0,
    limit: int = 10,
    task_id: Optional[str] = None,
    url: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    return await DataService(db).list_data(
        skip=skip,
        limit=limit,
        task_id=task_id,
        url=url
    )

@router.post("/export")
async def export_data(
    background_tasks: BackgroundTasks,
    format: str,
    task_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    if format not in ["csv", "json", "excel"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported export format"
        )
    
    export_task_id = await ExportWorker.start_export(format, task_id)
    background_tasks.add_task(
        ExportWorker.export,
        export_task_id,
        format,
        task_id
    )
    
    return {
        "task_id": export_task_id,
        "status": "processing"
    }

@router.get("/export/{task_id}")
async def get_export_status(task_id: str):
    status = ExportWorker.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Export task not found")
    return status

@router.post("/batch")
async def create_data_batch(
    batch_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    task_id = batch_data["taskId"]
    data_items = batch_data["data"]
    
    data_service = DataService(db)
    results = []
    
    for item in data_items:
        result = await data_service.create_data(
            task_id=task_id,
            url=item["url"],
            data=item["data"]
        )
        results.append(result)
    
    return {
        "status": "success",
        "count": len(results)
    }