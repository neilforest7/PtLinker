from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.schemas.task import TaskCreate, TaskResponse, BatchTaskCreate, BatchTaskResponse
from app.models.task import Task, TaskStatus
from app.core.database import get_db
from app.services.crawler_executor import CrawlerExecutorManager
from app.services.logger import TaskLogger
import uuid
from datetime import datetime
import importlib
import sys
import os

router = APIRouter(tags=["tasks"])

async def _start_crawler_task(crawler_id: str, config: dict, task_id: str, db: AsyncSession):
    """启动爬虫任务的具体实现"""
    logger = TaskLogger(db, task_id)
    try:
        # 导入爬虫模块
        crawler_module = importlib.import_module(f"crawlers.site_config.{crawler_id}")
        
        # 获取爬虫类
        crawler_class = getattr(crawler_module, f"{crawler_id.capitalize()}Crawler")
        
        # 创建爬虫实例
        crawler = crawler_class(config)
        
        # 执行爬虫
        await logger.info(f"Starting crawler task for {crawler_id}")
        result = await crawler.run()
        
        # 更新任务状态
        await logger.info("Task completed successfully")
        return result
        
    except Exception as e:
        await logger.error(f"Task failed: {str(e)}")
        raise

@router.post("/batch", response_model=BatchTaskResponse)
async def create_batch_tasks(
    batch: BatchTaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """批量创建爬虫任务"""
    tasks = []
    failed_sites = []
    base_config = batch.config or {}

    # 检查是否有太多运行中的任务
    current_tasks = CrawlerExecutorManager.get_running_tasks_count()
    if current_tasks + len(batch.site_ids) > 5:  # 限制最大并发任务数为5
        raise HTTPException(
            status_code=429,
            detail="Too many tasks would be created. Please wait for some tasks to complete."
        )

    for site_id in batch.site_ids:
        try:
            # 创建任务记录
            task_id = str(uuid.uuid4())
            db_task = Task(
                task_id=task_id,
                crawler_id=site_id,
                config=base_config.copy(),  # 使用基础配置
                status=TaskStatus.PENDING
            )
            db.add(db_task)
            await db.commit()
            await db.refresh(db_task)
            
            # 在后台启动任务
            logger = TaskLogger(db, task_id)
            await logger.info(f"Task created for site {site_id}")
            
            background_tasks.add_task(
                CrawlerExecutorManager.start_task,
                db=db,
                task=db_task,
                crawler_func=_start_crawler_task
            )
            
            tasks.append(db_task)
        except Exception as e:
            failed_sites.append(site_id)
            continue

    return BatchTaskResponse(
        tasks=tasks,
        total_count=len(tasks),
        failed_sites=failed_sites
    )

@router.post("", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """创建新的爬虫任务"""
    # 检查是否有太多运行中的任务
    if CrawlerExecutorManager.get_running_tasks_count() >= 5:  # 限制并发任务数为5
        raise HTTPException(
            status_code=429,
            detail="Too many running tasks. Please wait for some tasks to complete."
        )
    
    # 创建任务记录
    task_id = str(uuid.uuid4())
    db_task = Task(
        task_id=task_id,
        crawler_id=task.crawler_id,
        config=task.config,
        status=TaskStatus.PENDING
    )
    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)
    
    # 在后台启动任务
    logger = TaskLogger(db, task_id)
    await logger.info("Task created, starting execution")
    
    background_tasks.add_task(
        CrawlerExecutorManager.start_task,
        db=db,
        task=db_task,
        crawler_func=_start_crawler_task
    )
    
    return db_task

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """获取特定任务的详细信息"""
    result = await db.execute(select(Task).filter(Task.task_id == task_id))
    task = result.scalar_one_or_none()
    
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 添加运行状态信息
    if CrawlerExecutorManager.is_task_running(task_id):
        task.status = TaskStatus.RUNNING
    
    return task

@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 10,
    status: Optional[TaskStatus] = None,
    crawler_id: Optional[str] = None
):
    """获取任务列表，支持分页和过滤"""
    query = select(Task).order_by(Task.created_at.desc())
    
    # 添加过滤条件
    conditions = []
    if status:
        conditions.append(Task.status == status)
    if crawler_id:
        conditions.append(Task.crawler_id == crawler_id)
    
    if conditions:
        query = query.filter(and_(*conditions))
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # 更新运行中任务的状态
    tasks_list = list(tasks)
    for task in tasks_list:
        if CrawlerExecutorManager.is_task_running(task.task_id):
            task.status = TaskStatus.RUNNING
    
    return tasks_list

@router.delete("/{task_id}", status_code=204)
async def cancel_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """取消指定的任务"""
    result = await db.execute(select(Task).filter(Task.task_id == task_id))
    task = result.scalar_one_or_none()
    
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
        raise HTTPException(status_code=400, detail="Task cannot be cancelled")
    
    logger = TaskLogger(db, task_id)
    
    # 尝试取消运行中的任务
    if CrawlerExecutorManager.is_task_running(task_id):
        await logger.warning("Cancelling running task")
        cancelled = await CrawlerExecutorManager.cancel_task(task_id)
        if not cancelled:
            await logger.error("Failed to cancel task")
            raise HTTPException(status_code=500, detail="Failed to cancel task")
    
    # 更新任务状态
    task.status = TaskStatus.FAILED
    task.error = "Task cancelled by user"
    await db.commit()
    
    await logger.info("Task cancelled successfully")