from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.crawler import (
    CrawlerInfo,
    CrawlerStatus,
    CrawlerListResponse,
    CrawlerDetailResponse,
    CrawlerProcessStatus
)
from app.schemas.site import SiteSummary
from app.services.crawler_manager import CrawlerManager
from app.services.crawler_executor import CrawlerExecutorManager
from app.core.logger import get_logger
import psutil
from datetime import datetime

router = APIRouter(tags=["crawlers"])
_logger = get_logger(service="crawlers_api")

@router.get("", response_model=CrawlerListResponse)
async def list_crawlers(db: AsyncSession = Depends(get_db)):
    """获取所有可用的爬虫列表"""
    logger_ctx = get_logger(service="list_crawlers")
    logger_ctx.info("Fetching crawler list")
    try:
        crawler_manager = CrawlerManager()
        crawlers = await crawler_manager.list_crawlers()
        
        # 添加进程状态信息
        for crawler in crawlers:
            running_tasks = CrawlerExecutorManager.get_running_tasks_for_crawler(crawler.crawler_id)
            if running_tasks:
                crawler.process_status = await get_process_status(running_tasks[0])
        
        return CrawlerListResponse(
            crawlers=crawlers,
            total=len(crawlers)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list crawlers: {str(e)}")

@router.get("/{crawler_id}", response_model=CrawlerDetailResponse)
async def get_crawler(crawler_id: str, db: AsyncSession = Depends(get_db)):
    """获取特定爬虫的详细信息"""
    logger_ctx = get_logger(crawler_id=crawler_id)
    logger_ctx.info("Fetching crawler details")
    try:
        crawler_manager = CrawlerManager()
        crawler_detail = await crawler_manager.get_crawler_detail(crawler_id)
        
        # 添加进程状态信息
        running_tasks = CrawlerExecutorManager.get_running_tasks_for_crawler(crawler_id)
        if running_tasks:
            crawler_detail.status.process_status = await get_process_status(running_tasks[0])
        
        return crawler_detail
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Crawler {crawler_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get crawler details: {str(e)}")

@router.get("/{crawler_id}/status", response_model=CrawlerStatus)
async def get_crawler_status(crawler_id: str, db: AsyncSession = Depends(get_db)):
    """获取爬虫的运行状态"""
    logger_ctx = get_logger(crawler_id=crawler_id)
    try:
        crawler_manager = CrawlerManager()
        status = await crawler_manager.get_crawler_status(crawler_id)
        
        # 添加进程状态信息
        running_tasks = CrawlerExecutorManager.get_running_tasks_for_crawler(crawler_id)
        if running_tasks:
            status.process_status = await get_process_status(running_tasks[0])
            status.status = "running"
        else:
            status.status = "idle"
        
        return status
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Crawler {crawler_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get crawler status: {str(e)}")

@router.get("/{crawler_id}/process", response_model=CrawlerProcessStatus)
async def get_crawler_process(crawler_id: str):
    """获取爬虫进程的详细状态"""
    logger_ctx = get_logger(crawler_id=crawler_id)
    try:
        running_tasks = CrawlerExecutorManager.get_running_tasks_for_crawler(crawler_id)
        if not running_tasks:
            return CrawlerProcessStatus(is_running=False)
        
        return await get_process_status(running_tasks[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get process status: {str(e)}")

@router.post("/{crawler_id}/kill")
async def kill_crawler_process(crawler_id: str):
    """强制终止爬虫进程"""
    logger_ctx = get_logger(crawler_id=crawler_id)
    try:
        running_tasks = CrawlerExecutorManager.get_running_tasks_for_crawler(crawler_id)
        if not running_tasks:
            raise HTTPException(status_code=404, detail="No running process found")
        
        task_id = running_tasks[0]
        success = await CrawlerExecutorManager.cancel_task(task_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to kill process")
        
        return {"status": "success", "message": "Process killed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to kill process: {str(e)}")

async def get_process_status(task_id: str) -> CrawlerProcessStatus:
    """获取进程状态信息"""
    try:
        process = CrawlerExecutorManager.get_process(task_id)
        if not process or not process.process or process.process.returncode is not None:
            return CrawlerProcessStatus(is_running=False)
        
        pid = process.process.pid
        ps_process = psutil.Process(pid)
        
        return CrawlerProcessStatus(
            pid=pid,
            start_time=datetime.fromtimestamp(ps_process.create_time()),
            cpu_percent=ps_process.cpu_percent(),
            memory_percent=ps_process.memory_percent(),
            is_running=True,
            last_health_check=datetime.utcnow()
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
        return CrawlerProcessStatus(is_running=False)

@router.get("/{crawler_id}/site", response_model=SiteSummary)
async def get_site_status(crawler_id: str, db: AsyncSession = Depends(get_db)):
    """获取爬虫关联站点的状态"""
    try:
        crawler_manager = CrawlerManager()
        status = await crawler_manager.get_crawler_status(crawler_id)
        site_status = status.get("site_status")
        if not site_status:
            site_status = {
                "site_id": crawler_id,
                "name": crawler_id,
                "status": "unknown",
                "last_check_time": None,
                "user_stats": None,
                "browser_state": None
            }
        return site_status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get site status: {str(e)}")

@router.post("/{crawler_id}/validate")
async def validate_crawler_config(
    crawler_id: str,
    config: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """验证爬虫配置"""
    try:
        crawler_manager = CrawlerManager()
        is_valid = crawler_manager.validate_config(crawler_id, config)
        return {
            "valid": is_valid,
            "message": "Configuration is valid" if is_valid else "Configuration is invalid"
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Crawler {crawler_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate config: {str(e)}") 