from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.crawler import (
    CrawlerInfo,
    CrawlerStatus,
    CrawlerListResponse,
    CrawlerProcessStatus
)
from app.services.crawler_manager import crawler_manager
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
        # 获取爬虫列表
        crawlers = await crawler_manager.list_crawlers()
        
        # 转换为CrawlerInfo对象列表
        crawler_info_list = []
        for crawler in crawlers:
            info = CrawlerInfo(
                crawler_id=crawler["crawler_id"],
                name=crawler["name"],
                description=crawler["description"],
                site_id=crawler["site_id"]
            )
            crawler_info_list.append(info)
        
        return CrawlerListResponse(
            crawlers=crawler_info_list,
            total=len(crawler_info_list)
        )
    except Exception as e:
        logger_ctx.error(f"Failed to list crawlers: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list crawlers: {str(e)}")

@router.get("/{crawler_id}/status", response_model=CrawlerStatus)
async def get_crawler_status(crawler_id: str):
    """获取爬虫状态"""
    logger_ctx = get_logger(crawler_id=crawler_id)
    try:
        status = await crawler_manager.get_crawler_status(crawler_id)
        return CrawlerStatus(
            crawler_id=crawler_id,
            is_connected=status.get("is_connected", False),
            status=status.get("status", "unknown"),
            last_updated=status.get("last_updated", datetime.now().isoformat()),
            connected_at=status.get("connected_at"),
            disconnected_at=status.get("disconnected_at"),
            error=status.get("error"),
            system_status=status.get("system_status", {}),
            config_status=status.get("config_status", {}),
            metadata=status.get("metadata", {})
        )
    except Exception as e:
        logger_ctx.error(f"Failed to get crawler status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get crawler status: {str(e)}"
        )

@router.post("/{crawler_id}/control")
async def control_crawler(
    crawler_id: str,
    action: str,
    data: Dict[str, Any] = None
):
    """控制爬虫系统
    
    Args:
        crawler_id: 爬虫ID
        action: 控制动作 (restart/reload_config/clear_cache等)
        data: 附加数据
    """
    logger_ctx = get_logger(crawler_id=crawler_id)
    try:
        success = await crawler_manager.send_system_control(
            crawler_id,
            action,
            data or {}
        )
        if success:
            return {
                "status": "success",
                "message": f"Control action '{action}' sent successfully",
                "crawler_id": crawler_id
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send control action '{action}'"
            )
    except Exception as e:
        logger_ctx.error(f"Failed to control crawler: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to control crawler: {str(e)}"
        )

@router.get("/{crawler_id}/process", response_model=CrawlerProcessStatus)
async def get_crawler_process(crawler_id: str):
    """获取爬虫进程的详细状态"""
    logger_ctx = get_logger(crawler_id=crawler_id)
    try:
        running_tasks = CrawlerExecutorManager.get_running_tasks_for_crawler(crawler_id)
        if not running_tasks:
            return CrawlerProcessStatus(is_running=False)
        
        process_status = await get_process_status(running_tasks[0])
        
        # 获取系统状态
        status = await crawler_manager.get_crawler_status(crawler_id)
        system_status = status.get("system_status", {})
        
        # 合并进程和系统状态
        return CrawlerProcessStatus(
            **process_status.dict(),
            system_memory_usage=system_status.get("memory_usage"),
            system_cpu_usage=system_status.get("cpu_usage"),
            system_disk_usage=system_status.get("disk_usage"),
            process_count=system_status.get("process_count"),
            thread_count=system_status.get("thread_count")
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get process status: {str(e)}"
        )

@router.post("/{crawler_id}/kill")
async def kill_crawler_process(
    crawler_id: str,
    force: bool = False
):
    """强制终止爬虫进程
    
    Args:
        crawler_id: 爬虫ID
        force: 是否强制终止（发送SIGKILL信号）
    """
    logger_ctx = get_logger(crawler_id=crawler_id)
    try:
        running_tasks = CrawlerExecutorManager.get_running_tasks_for_crawler(crawler_id)
        if not running_tasks:
            raise HTTPException(status_code=404, detail="No running process found")
        
        task_id = running_tasks[0]
        success = await CrawlerExecutorManager.cancel_task(
            task_id,
            force=force,
            metadata={
                "kill_time": datetime.utcnow().isoformat(),
                "force_kill": force
            }
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to kill process")
        
        return {
            "status": "success",
            "message": f"Process killed successfully (force={force})",
            "crawler_id": crawler_id,
            "task_id": task_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to kill process: {str(e)}"
        )

async def get_process_status(task_id: str) -> CrawlerProcessStatus:
    """获取进程状态信息"""
    try:
        process = CrawlerExecutorManager.get_process(task_id)
        if not process or not process.process or process.process.returncode is not None:
            return CrawlerProcessStatus(is_running=False)
        
        pid = process.process.pid
        ps_process = psutil.Process(pid)
        
        # 获取更详细的进程信息
        with ps_process.oneshot():
            memory_info = ps_process.memory_info()
            io_counters = ps_process.io_counters()
            
            return CrawlerProcessStatus(
                pid=pid,
                start_time=datetime.fromtimestamp(ps_process.create_time()),
                cpu_percent=ps_process.cpu_percent(),
                memory_percent=ps_process.memory_percent(),
                memory_rss=memory_info.rss,
                memory_vms=memory_info.vms,
                io_read_bytes=io_counters.read_bytes,
                io_write_bytes=io_counters.write_bytes,
                thread_count=ps_process.num_threads(),
                is_running=True,
                last_health_check=datetime.utcnow()
            )
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
        return CrawlerProcessStatus(is_running=False) 