from typing import List

from core.database import get_db
from core.logger import get_logger
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.siteconfig import (SiteConfigCreate, SiteConfigResponse,
                                SiteConfigUpdate)
from schemas.sitesetup import SiteSetup
from services.managers.site_manager import SiteManager
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/site-configs", tags=["site_configs"])
logger = get_logger(name=__name__, site_id="site_configs_api")


@router.get("", response_model=List[SiteConfigResponse])
async def get_site_configs(db: AsyncSession = Depends(get_db)) -> List[SiteConfigResponse]:
    """获取所有站点配置"""
    try:
        site_manager = SiteManager.get_instance()
        # 确保站点管理器已初始化
        if not site_manager._initialized:
            logger.debug("站点管理器未初始化，正在初始化...")
            await site_manager.initialize(db)
            
        # 获取所有站点配置
        sites = await site_manager.get_available_sites()
        site_configs = [site.site_config for site in sites.values() if site.site_config]
        logger.debug(f"成功获取 {len(site_configs)} 个站点配置")
        return [SiteConfigResponse.model_validate(config) for config in site_configs]
        
    except Exception as e:
        logger.error(f"获取站点配置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取站点配置失败: {str(e)}"
        )


@router.get("/{site_id}", response_model=SiteConfigResponse)
async def get_site_config(
    site_id: str,
    db: AsyncSession = Depends(get_db)
) -> SiteConfigResponse:
    """获取指定站点的配置"""
    try:
        site_manager = SiteManager.get_instance()

        # 确保站点管理器已初始化
        if not site_manager._initialized:
            logger.debug("站点管理器未初始化，正在初始化...")
            await site_manager.initialize(db)
            
        # 获取站点配置
        site_setup = await site_manager.get_site_setup(site_id)
        if not site_setup or not site_setup.site_config:
            logger.warning(f"站点配置不存在: {site_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"站点配置 {site_id} 不存在"
            )
            
        logger.debug(f"成功获取站点 {site_id} 的配置")
        return SiteConfigResponse.model_validate(site_setup.site_config)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取站点配置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取站点配置失败: {str(e)}"
        )


@router.post("", response_model=SiteConfigResponse)
async def create_site_config(
    new_site_config: SiteConfigCreate,
    db: AsyncSession = Depends(get_db)
) -> SiteConfigResponse:
    """创建新的站点配置"""
    try:
        site_manager = SiteManager.get_instance()
        # 确保站点管理器已初始化
        if not site_manager._initialized:
            logger.debug("站点管理器未初始化，正在初始化...")
            await site_manager.initialize(db)
            
        # 检查站点ID是否已存在
        existing_setup = await site_manager.get_site_setup(new_site_config.site_id)
        if existing_setup and existing_setup.site_config:
            logger.warning(f"站点配置已存在: {new_site_config.site_id}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"站点配置 {new_site_config.site_id} 已存在"
            )
            
        # 使用update_site_setup更新配置
        if not await site_manager.update_site_setup(
            db,
            site_id=new_site_config.site_id,
            new_site_config=new_site_config
        ):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"保存站点配置失败"
            )
            
        logger.info(f"成功创建站点配置: {new_site_config.site_id}")
        return SiteConfigResponse.model_validate(new_site_config)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建站点配置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建站点配置失败: {str(e)}"
        )


@router.put("/{site_id}", response_model=SiteConfigResponse)
async def update_site_config(
    site_id: str,
    site_config: SiteConfigUpdate,
    db: AsyncSession = Depends(get_db)
) -> SiteConfigResponse:
    """更新站点配置"""
    try:
        site_manager = SiteManager.get_instance()
        # 确保站点管理器已初始化
        if not site_manager._initialized:
            logger.debug("站点管理器未初始化，正在初始化...")
            await site_manager.initialize(db)
            
        # 检查站点是否存在
        existing_setup = await site_manager.get_site_setup(site_id)
        if not existing_setup or not existing_setup.site_config:
            logger.warning(f"站点配置不存在: {site_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"站点配置 {site_id} 不存在"
            )
            
        # 更新配置
        updated_config = existing_setup.site_config.copy(update=site_config.model_dump(exclude_unset=True))
        
        # 使用update_site_setup更新配置
        if not await site_manager.update_site_setup(
            db,
            site_id=site_id,
            new_site_config=updated_config
        ):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"保存站点配置失败"
            )
            
        logger.info(f"成功更新站点配置: {site_id}")
        return SiteConfigResponse.model_validate(updated_config)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新站点配置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新站点配置失败: {str(e)}"
        )


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site_config(
    site_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除站点配置"""
    try:
        site_manager = SiteManager.get_instance()
        # 确保站点管理器已初始化
        if not site_manager._initialized:
            logger.debug("站点管理器未初始化，正在初始化...")
            await site_manager.initialize(db)
            
        # 检查站点是否存在
        existing_setup = await site_manager.get_site_setup(site_id)
        if not existing_setup:
            logger.warning(f"站点配置不存在: {site_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"站点配置 {site_id} 不存在"
            )
            
        # 使用新的 delete_site_setup 函数删除所有相关配置
        if not await site_manager.delete_site_setup(db, site_id):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"删除站点配置失败"
            )
            
        logger.info(f"成功删除站点配置: {site_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除站点配置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除站点配置失败: {str(e)}"
        )


@router.post("/reload", status_code=status.HTTP_200_OK)
async def reload_site_configs(db: AsyncSession = Depends(get_db)):
    """重新加载所有站点配置"""
    try:
        logger.info("开始重新加载站点配置")
        site_manager = SiteManager.get_instance()
        
        # 重新初始化站点管理器
        await site_manager.initialize(db)
        
        # 获取重新加载后的站点数量
        sites = await site_manager.get_available_sites()
        logger.info(f"站点配置重新加载完成，共加载 {len(sites)} 个站点")
        
        return {"message": f"成功重新加载 {len(sites)} 个站点配置"}
        
    except Exception as e:
        logger.error(f"重新加载站点配置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重新加载站点配置失败: {str(e)}"
        ) 