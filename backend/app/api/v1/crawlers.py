from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.crawler import (
    CrawlerInfo,
    CrawlerStatus,
    CrawlerListResponse,
    CrawlerDetailResponse
)
from app.schemas.site import SiteSummary
from app.services.crawler_manager import CrawlerManager

router = APIRouter(tags=["crawlers"])

@router.get("", response_model=CrawlerListResponse)
async def list_crawlers(db: AsyncSession = Depends(get_db)):
    """获取所有可用的爬虫列表"""
    try:
        crawler_manager = CrawlerManager(db)
        return await crawler_manager.list_crawlers()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list crawlers: {str(e)}")

@router.get("/{crawler_id}", response_model=CrawlerDetailResponse)
async def get_crawler(crawler_id: str, db: AsyncSession = Depends(get_db)):
    """获取特定爬虫的详细信息"""
    try:
        crawler_manager = CrawlerManager(db)
        return await crawler_manager.get_crawler_detail(crawler_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Crawler {crawler_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get crawler details: {str(e)}")

@router.get("/{crawler_id}/status", response_model=CrawlerStatus)
async def get_crawler_status(crawler_id: str, db: AsyncSession = Depends(get_db)):
    """获取爬虫的运行状态"""
    try:
        crawler_manager = CrawlerManager(db)
        return await crawler_manager.get_crawler_status(crawler_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Crawler {crawler_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get crawler status: {str(e)}")

@router.get("/{crawler_id}/site", response_model=SiteSummary)
async def get_site_status(crawler_id: str, db: AsyncSession = Depends(get_db)):
    """获取爬虫关联站点的状态"""
    try:
        crawler_manager = CrawlerManager(db)
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
        crawler_manager = CrawlerManager(db)
        is_valid = crawler_manager.validate_config(crawler_id, config)
        return {
            "valid": is_valid,
            "message": "Configuration is valid" if is_valid else "Configuration is invalid"
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Crawler {crawler_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate config: {str(e)}") 