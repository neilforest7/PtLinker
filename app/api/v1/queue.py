from typing import List, Optional

from core.database import get_db
from core.logger import get_logger, setup_logger
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from models.models import Task, TaskStatus
from schemas.sitesetup import BaseResponse
from schemas.task import TaskCreate
from services.managers.process_manager import process_manager
from services.managers.queue_manager import queue_manager
from services.managers.site_manager import SiteManager
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/queue", tags=["queue"])
setup_logger()
logger = get_logger(__name__, "queue_api")

def get_site_manager():
    return SiteManager.get_instance()

async def _start_tasks_background(tasks: List[TaskCreate], db: AsyncSession):
    """后台启动任务的函数
    
    Args:
        tasks: 要启动的任务列表
        db: 数据库会话
    """
    try:
        started_count = 0
        for task in tasks:
            try:
                logger.debug(f"正在启动任务: {task.task_id}")
                result = await process_manager.start_crawlertask(task, db)
                if result:
                    started_count += 1
            except Exception as e:
                logger.error(f"启动任务 {task.task_id} 失败: {str(e)}")
                continue
        
        logger.info(f"后台任务完成：成功启动 {started_count}/{len(tasks)} 个任务")
        
    except Exception as e:
        logger.error(f"后台启动任务失败: {str(e)}")
        logger.debug("错误详情:", exc_info=True)

@router.post("/start", response_model=BaseResponse, summary="启动队列中的所有待处理任务")
async def start_queue_tasks(
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """
    启动队列中所有待处理的任务
    
    Args:
        db: 数据库会话
        
    Returns:
        BaseResponse: 包含任务启动状态
    """
    try:
        logger.info("开始处理队列中的任务")
        
        # 获取当前PENDING任务数量
        stmt = select(Task).where(Task.status.in_([TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.READY]))
        result = await db.execute(stmt)
        pending_tasks = result.scalars().all()
        pending_count = len(pending_tasks)
        
        if pending_count == 0:
            return BaseResponse(
                code=status.HTTP_200_OK,
                message="队列中没有待处理的任务",
                data={"total_count": 0}
            )
        
        # 启动队列处理
        success = await queue_manager.start_queue(db)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="启动队列处理失败"
            )
        
        # 启动READY状态的任务
        started_tasks = await process_manager.start_crawlertask(db)
        started_count = len(started_tasks)
        
        return BaseResponse(
            code=status.HTTP_200_OK,
            message=f"已开始处理队列任务",
            data={
                "pending_count": pending_count,
                "started_count": started_count,
                "total_count": pending_count
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动队列任务失败: {str(e)}")
        logger.debug("错误详情:", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动队列任务失败: {str(e)}"
        )

@router.post("/{site_id}/start", response_model=BaseResponse, summary="启动指定站点的待处理任务")
async def start_site_queue_tasks(
    site_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    site_manager: SiteManager = Depends(get_site_manager)
) -> BaseResponse:
    """
    启动队列中指定站点的待处理任务
    
    Args:
        site_id: 站点ID
        background_tasks: 后台任务管理器
        db: 数据库会话
        site_manager: 站点管理器
        
    Returns:
        BaseResponse: 包含任务启动状态
    """
    try:
        logger.info(f"开始处理站点 {site_id} 的队列任务")
        
        # 验证站点是否存在
        site_setup = await site_manager.get_site_setup(site_id)
        if not site_setup:
            logger.error(f"站点不存在: {site_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"站点不存在: {site_id}"
            )
        
        # 获取队列中的任务
        tasks = await queue_manager.get_pending_tasks(site_id=site_id, db=db)
        task_count = len(tasks)
        logger.debug(f"获取到 {task_count} 个待处理任务")
        
        if task_count == 0:
            return BaseResponse(
                code=status.HTTP_200_OK,
                message=f"站点 {site_id} 没有待处理的任务",
                data={
                    "site_id": site_id,
                    "total_count": 0
                }
            )
        
        # 添加后台任务
        background_tasks.add_task(_start_tasks_background, tasks, db)
        
        return BaseResponse(
            code=status.HTTP_200_OK,
            message=f"已开始启动站点 {site_id} 的 {task_count} 个任务",
            data={
                "site_id": site_id,
                "total_count": task_count
            }
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动站点队列任务失败: {str(e)}")
        logger.debug("错误详情:", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动站点队列任务失败: {str(e)}"
        )

@router.delete("/clear", response_model=BaseResponse, summary="清除待运行的任务队列")
async def clear_pending_tasks(
    site_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    site_manager: SiteManager = Depends(get_site_manager)
) -> BaseResponse:
    """
    清除待运行的任务队列
    
    Args:
        site_id: 可选的站点ID，如果不提供则清除所有站点的待运行任务
        db: 数据库会话
        site_manager: 站点管理器
        
    Returns:
        BaseResponse: 包含清除的任务数量信息
    """
    try:
        logger.info(f"开始清除{'站点 ' + site_id if site_id else '所有站点'}的待运行任务")
        
        # 如果指定了站点ID，验证站点是否存在
        if site_id:
            site_setup = await site_manager.get_site_setup(site_id)
            if not site_setup:
                logger.error(f"站点不存在: {site_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"站点不存在: {site_id}"
                )
        
        # 清除任务
        result = await queue_manager.clear_pending_tasks(db, site_id)
        
        # 构造响应消息
        site_info = f"站点 {site_id}" if site_id else "所有站点"
        message = f"成功清除{site_info}的待运行任务：已清除 {result['cleared_count']}/{result['total_ready_count']} 个任务"
        
        logger.info(message)
        return BaseResponse(
            code=status.HTTP_200_OK,
            message=message,
            data={
                "site_id": result["site_id"],
                "cleared_count": result["cleared_count"],
                "total_ready_count": result["total_ready_count"]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"清除待运行任务失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )
