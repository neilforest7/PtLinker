import uuid
from datetime import datetime, timezone
from typing import List, Optional

from core.database import get_db
from core.logger import get_logger, setup_logger
from fastapi import (APIRouter, BackgroundTasks, Depends, HTTPException, Query,
                        status)
from models.models import Task, TaskStatus
from schemas.task import TaskCreate, TaskResponse, TaskUpdate
from services.managers.process_manager import ProcessManager
from services.managers.queue_manager import QueueManager
from services.managers.site_manager import SiteManager
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/tasks", tags=["tasks"])
logger = get_logger(__name__, "task_api")

def get_site_manager():
    return SiteManager.get_instance()

@router.post("/retry-failed", response_model=List[TaskResponse], summary="重试所有站点的最近失败任务")
async def retry_failed_tasks(
    db: AsyncSession = Depends(get_db),
    site_manager: SiteManager = Depends(get_site_manager),
    queue_manager: QueueManager = Depends(lambda: QueueManager())
) -> List[TaskResponse]:
    """
    获取每个站点最近的失败/取消任务并重新添加到队列中
    
    Returns:
        List[TaskResponse]: 重新添加到队列的任务列表
    """
    try:
        logger.info("开始处理重试失败/取消任务请求")
        responses = []
        
        # 1. 获取所有可用站点
        sites = await site_manager.get_available_sites()
        logger.debug(f"获取到 {len(sites)} 个站点")
        
        # 2. 对每个站点获取最近的任务
        for site_id in sites.keys():
            try:
                # 先查询该站点最近的任务（不考虑状态）
                stmt = (
                    select(Task)
                    .where(Task.site_id == site_id)
                    .order_by(Task.created_at.desc())
                    .limit(1)
                )
                result = await db.execute(stmt)
                latest_task = result.scalar_one_or_none()
                
                # 如果找到最近的任务且状态为失败，则重试
                if latest_task and (latest_task.status == TaskStatus.FAILED or latest_task.status == TaskStatus.CANCELLED):
                    logger.debug(f"站点 {site_id} 的最近任务 {latest_task.task_id} 状态为失败/取消，准备重试")
                    
                    # 生成新的任务ID
                    current_time = datetime.now()
                    new_task_id = f"{site_id}-{current_time.strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:4]}"
                    
                    # 创建新任务
                    task_create = TaskCreate(
                        task_id=new_task_id,
                        site_id=site_id,
                        status=TaskStatus.READY,
                        created_at=current_time,
                        updated_at=current_time,
                        task_metadata=latest_task.task_metadata  # 保留原任务的元数据
                    )
                    
                    # 添加到队列
                    response = await queue_manager.add_task(task_create, db)
                    if response:
                        responses.append(response)
                        logger.info(f"站点 {site_id} 的重试任务已添加到队列: {new_task_id}")
                    else:
                        logger.error(f"站点 {site_id} 的重试任务添加失败")
                else:
                    if not latest_task:
                        logger.debug(f"站点 {site_id} 没有任何任务记录")
                    else:
                        logger.debug(f"站点 {site_id} 的最近任务 {latest_task.task_id} 状态为 {latest_task.status}，不需要重试")
                    
            except Exception as e:
                logger.error(f"处理站点 {site_id} 的任务时出错: {str(e)}")
                continue
        
        if not responses:
            logger.info("没有找到需要重试的失败/取消任务")
            return []
            
        logger.info(f"成功重新添加 {len(responses)} 个失败/取消任务到队列")
        return responses
        
    except Exception as e:
        logger.error(f"重试失败/取消任务时发生错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重试失败/取消任务失败: {str(e)}"
        )

@router.post("", response_model=List[TaskResponse], summary="创建任务")
async def create_task(
    site_id: Optional[str] = None,
    create_for_all_sites: bool = Query(False, description="是否为所有站点创建任务"),
    db: AsyncSession = Depends(get_db),
    site_manager: SiteManager = Depends(get_site_manager),
    queue_manager: QueueManager = Depends(lambda: QueueManager())
) -> List[TaskResponse]:
    """创建任务
    
    Args:
        site_id: 指定站点ID（可选）
        create_for_all_sites: 是否为所有站点创建任务
        db: 数据库会话
        site_manager: 站点管理器
        queue_manager: 队列管理器
        
    Returns:
        List[TaskResponse]: 创建的任务列表
        
    Note:
        - 如果指定了 site_id，则只为该站点创建任务
        - 如果设置了 create_for_all_sites=True，则为所有启用的站点创建任务
        - 如果两者都未指定，则返回错误
        - 单个站点创建失败不会影响其他站点的任务创建
    """
    try:
        responses = []
        
        if not site_id and not create_for_all_sites:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="必须指定 site_id 或设置 create_for_all_sites=true"
            )
        
        # 获取需要创建任务的站点列表
        if create_for_all_sites:
            logger.info("正在为所有站点创建任务")
            site_setups = await site_manager.get_available_sites()
            site_ids = list(site_setups.keys())
        else:
            logger.info(f"正在为站点 {site_id} 创建任务")
            site_ids = [site_id]
            
        # 为每个站点创建任务
        for current_site_id in site_ids:
            try:
                # 1. 验证站点是否存在且已配置
                site_setup = await site_manager.get_site_setup(current_site_id)
                if not site_setup:
                    logger.warning(f"站点不存在或未配置: {current_site_id}")
                    continue
                    
                if not site_setup.crawler_config or not site_setup.crawler_config.enabled:
                    logger.warning(f"站点未启用或未配置爬虫参数: {current_site_id}")
                    continue
                    
                if not site_setup.crawler_config.enabled:
                    logger.warning(f"站点已禁用: {current_site_id}")
                    continue
                    
                # 2. 生成任务ID：{site_id}-YYYYMMDD-HHMMSS-4位uuid
                current_time = datetime.now()
                task_id = f"{current_site_id}-{current_time.strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:4]}"
                
                # 3. 创建任务
                task_create = TaskCreate(
                    task_id=task_id,
                    site_id=current_site_id,
                    status=TaskStatus.READY,
                    created_at=current_time,
                    updated_at=current_time
                )
                
                # 4. 将任务添加到队列
                logger.debug(f"将任务添加到队列 - 任务ID: {task_id}")
                response = await queue_manager.add_task(task_create, db)
                
                if response:
                    responses.append(response)
                    logger.info(f"站点 {current_site_id} 的任务 {task_id} 创建成功")
                else:
                    logger.error(f"站点 {current_site_id} 的任务创建失败")
                    
            except Exception as e:
                logger.error(f"站点 {current_site_id} 的任务创建失败: {str(e)}")
                continue
        
        if not responses:
            if create_for_all_sites:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="所有站点的任务创建均失败"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"站点 {site_id} 的任务创建失败"
                )
            
        return responses
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建任务失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建任务失败: {str(e)}"
        )

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
