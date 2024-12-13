from core.database import get_db
from core.logger import get_logger, setup_logger
from fastapi import APIRouter, Depends, HTTPException
from models.models import Task
from services.managers.process_manager import process_manager
from services.managers.queue_manager import queue_manager
from services.managers.site_manager import SiteManager
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
setup_logger()
logger = get_logger(__name__, "QueueAPI")

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
        site_manager: 站点管理器
        
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
