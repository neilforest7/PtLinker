from typing import Optional

from core.database import get_db
from core.logger import get_logger, setup_logger
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.crawlercredential import (CrawlerCredentialCreate,
                                        CrawlerCredentialResponse,
                                        CrawlerCredentialUpdate)
from services.managers.site_manager import SiteManager
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/credentials", tags=["credentials"])
setup_logger()
logger = get_logger(__name__, "cred_api")


@router.get("/{site_id}", response_model=CrawlerCredentialResponse, summary="获取站点凭证")
async def get_site_credential(
    site_id: str,
    db: AsyncSession = Depends(get_db)
) -> CrawlerCredentialResponse:
    """
    获取指定站点的凭证信息
    
    Args:
        site_id: 站点ID
        db: 数据库会话
        
    Returns:
        CrawlerCredentialResponse: 站点凭证信息
    """
    try:
        site_manager = SiteManager.get_instance()
        if not site_manager._initialized:
            await site_manager.initialize(db)
            
        # 获取站点配置
        site_setup = await site_manager.get_site_setup(site_id)
        if not site_setup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"站点 {site_id} 不存在"
            )
            
        if not site_setup.crawler_credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"站点 {site_id} 的凭证不存在"
            )
            
        return CrawlerCredentialResponse.model_validate(site_setup.crawler_credential)
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"获取站点凭证失败: {str(e)}"
        logger.error(error_msg)
        logger.debug("错误详情:", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.put("/{site_id}", response_model=CrawlerCredentialResponse, summary="更新站点凭证")
async def update_site_credential(
    site_id: str,
    credential: CrawlerCredentialUpdate,
    db: AsyncSession = Depends(get_db)
) -> CrawlerCredentialResponse:
    """
    更新指定站点的凭证信息
    
    Args:
        site_id: 站点ID
        credential: 要更新的凭证信息，所有字段都是可选的
        db: 数据库会话
        
    Returns:
        CrawlerCredentialResponse: 更新后的站点凭证信息
    """
    try:
        site_manager = SiteManager.get_instance()
        if not site_manager._initialized:
            await site_manager.initialize(db)
            
        # 获取站点配置
        site_setup = await site_manager.get_site_setup(site_id)
        if not site_setup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"站点 {site_id} 不存在"
            )
            
        # 准备更新数据
        credential_data = credential.model_dump(exclude_unset=True)
        credential_data['site_id'] = site_id
        
        # 如果存在现有凭证，则基于它更新
        if site_setup.crawler_credential:
            updated_credential = site_setup.crawler_credential.copy(update=credential_data)
        else:
            # 如果不存在，创建新的凭证
            credential_data['site_id'] = site_id  # 添加必需的 site_id
            updated_credential = CrawlerCredentialCreate(**credential_data)
            
        # 更新凭证
        if not await site_manager.update_site_setup(
            db,
            site_id=site_id,
            new_crawler_credential=updated_credential
        ):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"保存凭证失败"
            )
            
        logger.info(f"成功更新站点凭证: {site_id}")
        return CrawlerCredentialResponse.model_validate(updated_credential)
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"更新站点凭证失败: {str(e)}"
        logger.error(error_msg)
        logger.debug("错误详情:", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        ) 