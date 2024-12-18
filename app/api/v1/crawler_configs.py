from typing import List

from core.database import get_db
from core.logger import get_logger
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.crawlerconfig import CrawlerConfigResponse, CrawlerConfigUpdate
from services.managers.site_manager import SiteManager
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/crawler-configs", tags=["crawler_configs"])
logger = get_logger(name=__name__, site_id="cr_conf_api")


@router.put("/{site_id}", response_model=CrawlerConfigResponse, summary="更新站点的爬虫配置")
async def update_crawler_config(
    site_id: str,
    crawler_config: CrawlerConfigUpdate,
    db: AsyncSession = Depends(get_db)
) -> CrawlerConfigResponse:
    """更新站点的爬虫配置"""
    try:
        # 记录接收到的原始配置数据
        logger.debug(f"接收到更新请求: site_id={site_id}, config={crawler_config.model_dump()}")
        
        site_manager = SiteManager.get_instance()
        # 确保站点管理器已初始化
        if not site_manager._initialized:
            logger.debug("站点管理器未初始化，正在初始化...")
            await site_manager.initialize(db)
            
        # 检查站点是否存在
        existing_setup = await site_manager.get_site_setup(site_id)
        if not existing_setup:
            logger.warning(f"站点不存在: {site_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"站点 {site_id} 不存在"
            )
            
        # 更新配置
        # 如果存在现有配置，则基于它更新；否则使用新的配置
        if existing_setup.crawler_config:
            # 记录现有配置
            logger.debug(f"现有配置: {existing_setup.crawler_config.model_dump()}")
            
            # 转换配置数据，只包含非空值
            crawler_config_data = crawler_config.model_dump(
                exclude_unset=True,  # 只包含显式设置的字段
                exclude_none=True    # 排除值为 None 的字段
            )
            logger.debug(f"更新字段: {crawler_config_data}")
            
            # 确保 site_id 正确
            crawler_config_data['site_id'] = site_id
            
            # 基于现有配置创建更新后的配置
            updated_config = existing_setup.crawler_config.copy(update=crawler_config_data)
            logger.debug(f"更新后的配置: {updated_config.model_dump()}")
        else:
            # 如果不存在配置，创建新的配置
            # 只使用提供的字段和必需字段
            crawler_config_data = crawler_config.model_dump(
                exclude_unset=True,
                exclude_none=True
            )
            logger.debug(f"创建新配置: {crawler_config_data}")
            
            # 确保 site_id 正确
            crawler_config_data['site_id'] = site_id
            
            # 使用默认值填充必需字段
            if 'enabled' not in crawler_config_data:
                crawler_config_data['enabled'] = True
            if 'use_proxy' not in crawler_config_data:
                crawler_config_data['use_proxy'] = False
            if 'fresh_login' not in crawler_config_data:
                crawler_config_data['fresh_login'] = False
            if 'captcha_skip' not in crawler_config_data:
                crawler_config_data['captcha_skip'] = False
            if 'headless' not in crawler_config_data:
                crawler_config_data['headless'] = True
                
            updated_config = CrawlerConfigUpdate(**crawler_config_data)
            logger.debug(f"创建的新配置: {updated_config.model_dump()}")
            
        # 使用update_site_setup更新配置
        if not await site_manager.update_site_setup(
            db,
            site_id=site_id,
            new_crawler_config=updated_config
        ):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"保存爬虫配置失败"
            )
            
        logger.info(f"成功更新爬虫配置: {site_id}")
        return CrawlerConfigResponse.model_validate(updated_config)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新爬虫配置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新爬虫配置失败: {str(e)}"
        )


@router.post("/{site_id}/reset", response_model=CrawlerConfigResponse, summary="重置站点的爬虫配置为默认值")
async def reset_crawler_config(
    site_id: str,
    db: AsyncSession = Depends(get_db)
) -> CrawlerConfigResponse:
    """重置站点的爬虫配置为默认值"""
    try:
        site_manager = SiteManager.get_instance()
        # 确保站点管理器已初始化
        if not site_manager._initialized:
            logger.debug("站点管理器未初始化，正在初始化...")
            await site_manager.initialize(db)
            
        # 检查站点是否存在
        existing_setup = await site_manager.get_site_setup(site_id)
        if not existing_setup:
            logger.warning(f"站点不存在: {site_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"站点 {site_id} 不存在"
            )
            
        # 创建默认配置
        default_config = CrawlerConfigUpdate(
            site_id=site_id,
            enabled=True,
            use_proxy=False,
            fresh_login=False,
            captcha_skip=False,
            headless=True
        )
        
        # 使用update_site_setup更新配置
        if not await site_manager.update_site_setup(
            db,
            site_id=site_id,
            new_crawler_config=default_config
        ):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"重置爬虫配置失败"
            )
            
        logger.info(f"成功重置爬虫配置: {site_id}")
        return CrawlerConfigResponse.model_validate(default_config)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置爬虫配置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重置爬虫配置失败: {str(e)}"
        )
