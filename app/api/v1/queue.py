from core.database import get_db
from core.logger import get_logger, setup_logger
from fastapi import APIRouter, Depends, HTTPException
from models.models import Task
from services.managers.process_manager import process_manager
from services.managers.queue_manager import queue_manager
from services.managers.site_manager import SiteManager
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

router = APIRouter()
setup_logger()
logger = get_logger(__name__, "queue_api")

def get_site_manager():
    return SiteManager.get_instance()

@router.post("/start", summary="启动队列中的所有待处理任务")
async def start_queue_tasks(
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    启动队列中所有待处理的任务
    
    Args:
        db: 数据库会话
        
    Returns:
        dict: 包含启动的任务数量
    """
    try:
        logger.info("开始处理队列中的任务")
        
        # 获取队列中的任务
        tasks = await queue_manager.get_pending_tasks(db=db)
        logger.debug(f"获取到 {len(tasks)} 个待处理任务")
        started_count = 0
        
        # 启动每个任务
        for task in tasks:
            try:
                logger.debug(f"正在启动任务: {task.task_id}")
                result = await process_manager.start_crawlertask(task, db)
                if result:
                    started_count += 1
            except Exception as e:
                logger.error(f"启动任务 {task.task_id} 失败: {str(e)}")
                continue
        
        logger.info(f"成功启动 {started_count}/{len(tasks)} 个任务")
        return {
            "message": f"成功启动 {started_count}/{len(tasks)} 个任务",
            "started_count": started_count,
            "total_count": len(tasks)
        }
        
    except Exception as e:
        logger.error(f"启动队列任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"启动队列任务失败: {str(e)}")

@router.post("/{site_id}/start", summary="启动指定站点的待处理任务")
async def start_site_queue_tasks(
    site_id: str,
    db: AsyncSession = Depends(get_db),
    site_manager: SiteManager = Depends(get_site_manager)
) -> dict:
    """
    启动队列中指定站点的待处理任务
    
    Args:
        site_id: 站点ID
        db: 数据库会话
        site_manager: ��点管理器
        
    Returns:
        dict: 包含启动的任务数量
    """
    try:
        logger.info(f"开始处理站点 {site_id} 的队列任务")
        
        # 验证站点是否存在
        site_setup = await site_manager.get_site_setup(site_id)
        if not site_setup:
            logger.error(f"站点不存在: {site_id}")
            raise HTTPException(status_code=404, detail=f"站点不存在: {site_id}")
        
        # 获取队列中的任务
        tasks = await queue_manager.get_pending_tasks(site_id=site_id, db=db)
        logger.debug(f"获取到 {len(tasks)} 个待处理任务")
        started_count = 0
        
        # 启动每个任务
        for task in tasks:
            try:
                logger.debug(f"正在启动任务: {task.task_id}")
                result = await process_manager.start_crawlertask(task, db)
                if result:
                    started_count += 1
            except Exception as e:
                logger.error(f"启动任务 {task.task_id} 失败: {str(e)}")
                continue
        
        logger.info(f"成功启动站点 {site_id} 的 {started_count}/{len(tasks)} 个任务")
        return {
            "message": f"成功启动站点 {site_id} 的 {started_count}/{len(tasks)} 个任务",
            "site_id": site_id,
            "started_count": started_count,
            "total_count": len(tasks)
        }
        
    except Exception as e:
        logger.error(f"启动站点队列任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"启动站点队列任务失败: {str(e)}")

@router.delete("/clear", summary="清除待运行的任务队列")
async def clear_pending_tasks(
    site_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    site_manager: SiteManager = Depends(get_site_manager)
) -> dict:
    """
    清除待运行的任务队列
    
    Args:
        site_id: 可选的站点ID，如果不提供则清除所有站点的待运行任务
        db: 数据库会话
        site_manager: 站点管理器
        
    Returns:
        dict: 包含清除的任务数量信息
    """
    try:
        logger.info(f"开始清除{'站点 ' + site_id if site_id else '所有站点'}的待运行任务")
        
        # 如果指定了站点ID，验证站点是否存在
        if site_id:
            site_setup = await site_manager.get_site_setup(site_id)
            if not site_setup:
                logger.error(f"站点不存在: {site_id}")
                raise HTTPException(status_code=404, detail=f"站点不存在: {site_id}")
        
        # 清除任务
        result = await queue_manager.clear_pending_tasks(db, site_id)
        
        # 构造响应消息
        site_info = f"站点 {site_id}" if site_id else "所有站点"
        message = f"成功清除{site_info}的待运行任务：已清除 {result['cleared_count']}/{result['total_ready_count']} 个任务"
        
        logger.info(message)
        return {
            "message": message,
            "site_id": result["site_id"],
            "cleared_count": result["cleared_count"],
            "total_ready_count": result["total_ready_count"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"清除待运行任务失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)
