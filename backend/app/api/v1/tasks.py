from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.schemas.task import TaskCreate, TaskResponse, BatchTaskCreate, BatchTaskResponse
from app.models.task import Task, TaskStatus
from app.core.database import get_db
from app.services.crawler_executor import CrawlerExecutorManager
from app.core.logger import get_logger
from app.services.websocket_manager import manager
import time
from datetime import datetime

router = APIRouter(tags=["tasks"])
logger = get_logger(service="tasks_api")

def generate_task_id(crawler_id: str) -> str:
    """生成任务ID，格式为: {site_id}-{timestamp}"""
    timestamp = int(time.time())
    return f"{crawler_id.lower()}-{timestamp}"

@router.post("", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """创建新的爬虫任务"""
    logger_ctx = get_logger(crawler_id=task.crawler_id)
    
    # 检查是否有太多运行中的任务
    if CrawlerExecutorManager.get_running_tasks_count() >= 20:
        logger_ctx.warning("Too many running tasks")
        raise HTTPException(
            status_code=429,
            detail="Too many running tasks. Please wait for some tasks to complete."
        )
    
    # 创建任务记录
    task_id = generate_task_id(task.crawler_id)
    logger_ctx = get_logger(task_id=task_id)
    logger_ctx.info("Creating new task")
    
    db_task = Task(
        task_id=task_id,
        crawler_id=task.crawler_id,
        status=TaskStatus.PENDING,
        created_at=datetime.utcnow()
    )
    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)
    
    # 在后台启动任务
    logger_ctx.debug("Starting background task")
    background_tasks.add_task(
        CrawlerExecutorManager.start_task,
        db=db,
        task=db_task
    )
    
    return db_task

@router.post("/batch", response_model=BatchTaskResponse)
async def create_batch_tasks(
    batch: BatchTaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """批量创建爬虫任务"""
    logger_ctx = get_logger(service="batch_create")
    tasks = []
    failed_sites = []

    # 检查是否有太多运行中的任务
    current_tasks = CrawlerExecutorManager.get_running_tasks_count()
    if current_tasks + len(batch.site_ids) > 15:
        logger_ctx.warning(f"Too many tasks would be created: {current_tasks} running + {len(batch.site_ids)} new")
        raise HTTPException(
            status_code=429,
            detail="Too many tasks would be created. Please wait for some tasks to complete."
        )

    for site_id in batch.site_ids:
        try:
            # 创建任务记录
            task_id = generate_task_id(site_id)
            logger_ctx.info(f"Creating task for site {site_id}", task_id=task_id)
            
            db_task = Task(
                task_id=task_id,
                crawler_id=site_id,
                status=TaskStatus.PENDING,
                created_at=datetime.utcnow()
            )
            db.add(db_task)
            await db.commit()
            await db.refresh(db_task)
            
            # 在后台启动任务
            logger_ctx.debug(f"Starting background task for {site_id}", task_id=task_id)
            background_tasks.add_task(
                CrawlerExecutorManager.start_task,
                db=db,
                task=db_task
            )
            
            tasks.append(db_task)
        except Exception as e:
            logger_ctx.error(f"Failed to create task for site {site_id}: {str(e)}", exc_info=True)
            failed_sites.append(site_id)
            continue

    return BatchTaskResponse(
        tasks=tasks,
        failed_sites=failed_sites,
        total_created=len(tasks),
        total_failed=len(failed_sites)
    )

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """获取特定任务的详细信息"""
    logger_ctx = get_logger(task_id=task_id)
    
    result = await db.execute(select(Task).filter(Task.task_id == task_id))
    task = result.scalar_one_or_none()
    
    if task is None:
        logger_ctx.warning("Task not found")
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 添加运行状态信息
    if CrawlerExecutorManager.is_task_running(task_id):
        task.status = TaskStatus.RUNNING
        logger_ctx.debug("Task is currently running")
    
    return task

@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """取消正在运行的任务"""
    logger_ctx = get_logger(task_id=task_id)
    
    # 检查任务是否存在
    result = await db.execute(select(Task).filter(Task.task_id == task_id))
    task = result.scalar_one_or_none()
    
    if task is None:
        logger_ctx.warning("Task not found")
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Task not found",
                "task_id": task_id
            }
        )
    
    # 检查任务是否可以取消
    if task.status in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        logger_ctx.info(f"Task already in final state: {task.status}")
        return {
            "status": "info",
            "message": f"Task already {task.status.lower()}, no need to cancel",
            "task_id": task_id,
            "task_status": task.status
        }
    
    # 检查任务是否正在运行
    if not CrawlerExecutorManager.is_task_running(task_id):
        logger_ctx.info("Task is not running")
        return {
            "status": "info",
            "message": "Task is not currently running",
            "task_id": task_id,
            "task_status": task.status
        }
    
    # 取消任务
    success = await CrawlerExecutorManager.cancel_task(task_id)
    if success:
        # 更新任务状态
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.utcnow()
        await db.commit()
        
        # 发送取消状态到WebSocket
        await manager.send_status(task_id, "cancelled")
        logger_ctx.info("Task cancelled successfully")
        
        return {
            "status": "success",
            "message": "Task cancelled successfully",
            "task_id": task_id,
            "task_status": TaskStatus.CANCELLED
        }
    else:
        logger_ctx.error("Failed to cancel task")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to cancel task",
                "task_id": task_id
            }
        )

@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    crawler_id: Optional[str] = None,
    limit: int = Query(default=10, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """获取任务列表，支持过滤和分页"""
    query = select(Task)
    
    # 添加过滤条件
    filters = []
    if status:
        filters.append(Task.status == status)
    if crawler_id:
        filters.append(Task.crawler_id == crawler_id)
    
    if filters:
        query = query.filter(and_(*filters))
    
    # 添加排序和分页
    query = query.order_by(Task.created_at.desc()).offset(offset).limit(limit)
    
    # 执行查询
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # 更新运行状态
    for task in tasks:
        if CrawlerExecutorManager.is_task_running(task.task_id):
            task.status = TaskStatus.RUNNING
    
    return tasks