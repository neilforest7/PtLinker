import uuid
from datetime import datetime, timezone
from typing import List, Optional

from core.database import get_db
from core.logger import get_logger, setup_logger
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from models.models import Task, TaskStatus
from schemas.task import TaskCreate, TaskResponse, TaskUpdate
from services.managers.process_manager import ProcessManager
from services.managers.queue_manager import QueueManager
from services.managers.site_manager import SiteManager
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
setup_logger()
logger = get_logger(__name__, "TaskAPI")

def get_site_manager():
    return SiteManager.get_instance()

        
@router.post("/{site_id}", response_model=TaskResponse, summary="为指定站点创建新任务")
async def create_site_task(
    site_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    site_manager: SiteManager = Depends(get_site_manager),
    process_manager: ProcessManager = Depends(lambda: ProcessManager()),
    queue_manager: QueueManager = Depends(lambda: QueueManager())
) -> TaskResponse:
    """
    为指定站点创建新的爬虫任务
    
    Args:
        site_id: 站点ID
        db: 数据库会话
        site_manager: 站点管理器
        queue_manager: 队列管理器
        
    Returns:
        TaskResponse: 创建的任务信息
        
    Raises:
        HTTPException: 当站点不存在或创建任务失败时
    """
    try:
        logger.info(f"收到创建任务请求 - 站点: {site_id}")
        
        # 1. 验证站点是否存在且已配置
        site_setup = await site_manager.get_site_setup(site_id)
        if not site_setup:
            logger.error(f"站点不存在: {site_id}")
            raise HTTPException(status_code=404, detail=f"站点不存在: {site_id}")
            
        if not site_setup.crawler_config or not site_setup.crawler_config.enabled:
            logger.error(f"站点未启用或未配置: {site_id}")
            raise HTTPException(status_code=400, detail=f"站点未启用或未配置: {site_id}")
            
        # 2. 生成任务ID：{site_id}-YYYYMMDD-HHMMSS-4位uuid
        current_time = datetime.now(timezone.utc)
        task_id = f"{site_id}-{current_time.strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:4]}"
        
        # 3. 创建任务记录
        # db_task = Task(
        #     task_id=task_id,
        #     site_id=site_id,
        #     status=TaskStatus.READY,
        #     created_at=current_time,
        #     updated_at=current_time
        # )
        
        # # 4. 保存任务到数据库
        # logger.debug(f"保存任务到数据库 - 任务ID: {db_task.task_id}")
        # db.add(db_task)
        # await db.commit()
        
        # 5. 将任务添加到队列
        logger.debug(f"将任务添加到队列 - 任务ID: {task_id}")
        task_create = TaskCreate(
            task_id=task_id,
            site_id=site_id,
            status=TaskStatus.READY,
            created_at=current_time,
            updated_at=current_time
        )
        await queue_manager.add_task(task_create, db)
        
        # logger.info(f"任务创建成功 - 任务ID: {db_task.task_id}")
        # return TaskResponse.model_validate(db_task)
    
        # 6. 创建响应
        response = TaskResponse(
            task_id=task_id,
            site_id=site_id,
            status=TaskStatus.READY,
            created_at=current_time,
            updated_at=current_time
        )
        
        logger.info(f"任务创建成功 - 任务ID: {task_id}")
        return response
        
    except Exception as e:
        logger.error(f"创建任务失败: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")
        
@router.get("/{task_id}", response_model=TaskResponse, summary="获取任务信息")
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db)
) -> TaskResponse:
    """
    获取指定任务的信息
    
    Args:
        task_id: 任务ID
        db: 数据库会话
        
    Returns:
        TaskResponse: 任务信息
        
    Raises:
        HTTPException: 当任务不存在时
    """
    try:
        logger.info(f"获取任务信息 - 任务ID: {task_id}")
        
        # 查询任务
        stmt = select(Task).where(Task.task_id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            logger.error(f"任务不存在: {task_id}")
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
            
        logger.debug(f"获取任务信息成功 - 任务ID: {task_id}")
        return TaskResponse.from_orm(task)
        
    except Exception as e:
        logger.error(f"获取任务信息失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取任务信息失败: {str(e)}")
        
@router.get("/", response_model=List[TaskResponse], summary="获取任务列表")
async def list_tasks(
    site_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
) -> List[TaskResponse]:
    """
    获取任务列表，支持按站点和状态筛选
    
    Args:
        site_id: 站点ID（可选）
        status: 任务状态（可选）
        limit: 返回数量限制
        db: 数据库会话
        
    Returns:
        List[TaskResponse]: 任务列表
    """
    try:
        logger.info(f"获取任务列表 - 站点: {site_id}, 状态: {status}, 限制: {limit}")
        
        # 构建查询
        query = select(Task)
        if site_id:
            query = query.where(Task.site_id == site_id)
        if status:
            query = query.where(Task.status == TaskStatus(status))
        query = query.order_by(Task.created_at.desc()).limit(limit)
        
        # 执行查询
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        logger.debug(f"获取任务列表成功 - 共 {len(tasks)} 条记录")
        return [TaskResponse.from_orm(task) for task in tasks]
        
    except Exception as e:
        logger.error(f"获取任务列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")
        
@router.delete("/{task_id}", summary="取消任务")
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    queue_manager: QueueManager = Depends(lambda: QueueManager())
) -> dict:
    """
    取消指定的任务
    
    Args:
        task_id: 任务ID
        db: 数据库会话
        queue_manager: 队列管理器
        
    Returns:
        dict: 操作结果
        
    Raises:
        HTTPException: 当任务不存在或无法取消时
    """
    try:
        logger.info(f"取消任务请求 - 任务ID: {task_id}")
        
        # 1. 查询任务
        stmt = select(Task).where(Task.task_id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            logger.error(f"任务不存在: {task_id}")
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
            
        # 2. 检查任务是否可以取消
        if task.status in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            logger.warning(f"任务已完成或已取消，无法取消 - 任务ID: {task_id}, 状态: {task.status}")
            return {"message": f"任务已是终态: {task.status}"}
            
        # 3. 从队列中移除任务
        logger.debug(f"从队列中移除任务 - 任务ID: {task_id}")
        await queue_manager.remove_task(task_id)
        
        # 4. 更新任务状态
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        await db.commit()
        
        logger.info(f"任务取消成功 - 任务ID: {task_id}")
        return {"message": "任务已取消"}
        
    except Exception as e:
        logger.error(f"取消任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")
