from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import uuid4
from app.db.session import get_db
from app.models.pydantic.schemas import TaskCreate, TaskUpdate, TaskInDB
from app.models.sqlalchemy.models import TaskStatus
from app.services.task import TaskService
from app.services.crawler_manager import CrawlerManager

router = APIRouter()

@router.get("/", response_model=List[TaskInDB])
async def list_tasks(
    skip: int = 0,
    limit: int = 10,
    status: Optional[List[TaskStatus]] = None,
    db: AsyncSession = Depends(get_db)
):
    return await TaskService(db).list_tasks(skip, limit, status)

@router.post("/", response_model=TaskInDB)
async def create_task(
    task: TaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    task_id = str(uuid4())
    task_service = TaskService(db)
    
    # 创建任务记录
    db_task = await task_service.create_task(task_id, task)
    
    # 启动爬虫
    background_tasks.add_task(
        CrawlerManager().start_crawler,
        task_id,
        task.config,
        db
    )
    
    return db_task

@router.post("/{task_id}/pause")
async def pause_task(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    task_service = TaskService(db)
    task = await task_service.pause_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or cannot be paused")
    
    # 通知爬虫管理器暂停任务
    await CrawlerManager().pause_crawler(task_id)
    return {"status": "success"}

@router.post("/{task_id}/resume")
async def resume_task(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    task_service = TaskService(db)
    task = await task_service.resume_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or cannot be resumed")
    
    # 通知爬虫管理器恢复任务
    await CrawlerManager().resume_crawler(task_id)
    return {"status": "success"}

@router.post("/{task_id}/stop")
async def stop_task(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    task_service = TaskService(db)
    task = await task_service.stop_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or cannot be stopped")
    
    # 通知爬虫管理器停止任务
    await CrawlerManager().stop_crawler(task_id)
    return {"status": "success"} 