from typing import List, Optional

from core.database import get_db
from core.logger import get_logger
from fastapi import APIRouter, Depends, HTTPException, Query, status
from schemas.siteconfig import (SiteConfigCreate, SiteConfigResponse,
                                SiteConfigUpdate)
from schemas.sitesetup import SiteSetup
from schemas.sitesetup import BaseResponse
from services.managers.site_manager import SiteManager
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/site-configs", tags=["site_configs"])
logger = get_logger(name=__name__, site_id="siteconf_api")


@router.get("", response_model=List[SiteConfigResponse], summary="获取所有站点配置")
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


@router.get("/{site_id}", response_model=SiteConfigResponse, summary="获取指定站点的配置")
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


@router.post("", response_model=SiteConfigResponse, summary="创建新的站点配置")
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


@router.put("/{site_id}", response_model=SiteConfigResponse, summary="更新站点配置")
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


@router.delete("/{site_id}", response_model=BaseResponse, summary="删除站点配置")
async def delete_site_config(
    site_id: str,
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
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
        return BaseResponse(
            code=status.HTTP_200_OK,
            message=f"成功删除站点配置: {site_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除站点配置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除站点配置失败: {str(e)}"
        )


@router.post("/reload", response_model=BaseResponse, summary="重新加载站点配置")
async def reload_site_configs(
    site_id: Optional[str] = None,
    all_sites: bool = Query(False, description="是否重载所有站点配置"),
    from_local: bool = Query(False, description="是否从本地文件重新加载配置"),
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """重新加载站点配置
    
    Args:
        site_id: 指定要重载的站点ID（可选）
        all_sites: 是否重载所有站点配置
        from_local: 是否从本地文件重新加载配置
        db: 数据库会话
        
    Returns:
        BaseResponse: 包含重载结果的信息
    """
    try:
        logger.info("开始重新加载站点配置")
        site_manager = SiteManager.get_instance()
        
        if not site_id and not all_sites:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="必须指定 site_id 或设置 all_sites=true"
            )
            
        if site_id and all_sites:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能同时指定 site_id 和 all_sites=true"
            )
            
        if site_id:
            # 重载单个站点
            logger.info(f"重新加载站点配置: {site_id}")
            
            if from_local:
                # 从本地文件加载配置
                local_setup = await site_manager._load_local_site_setup(site_id)
                if not local_setup:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"本地配置文件未找到: {site_id}"
                    )
                    
                # 保存到数据库并更新内存中的配置
                if not await site_manager._persist_site_setup(db, local_setup):
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"保存配置到数据库失败: {site_id}"
                    )
                    
                logger.info(f"从本地文件重新加载站点配置成功: {site_id}")
                return BaseResponse(
                    code=status.HTTP_200_OK,
                    message=f"成功从本地文件重新加载站点配置: {site_id}",
                )
                
            else:
                # 从数据库重新加载配置
                site_setups = await site_manager._load_site_setup(db)
                if site_id not in site_setups:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"站点配置不存在: {site_id}"
                    )
                    
                # 更新内存中的配置
                site_manager._sites[site_id] = site_setups[site_id]
                logger.info(f"从数据库重新加载站点配置成功: {site_id}")
                return BaseResponse(
                    code=status.HTTP_200_OK,
                    message=f"成功从数据库重新加载站点配置: {site_id}",
                    data={
                        "reloaded_site_id": site_id,
                        "reload_type": "database"
                    }
                )
            
        else:  # all_sites = True
            # 重新初始化站点管理器
            if from_local:
                # 从本地文件加载所有站点配置
                site_setups = {}
                local_setups = await site_manager.load_local_site_setups()
                for site_id, local_setup in local_setups.items():
                    # 保存到数据库
                    if await site_manager._persist_site_setup(db, local_setup):
                        site_setups[site_id] = local_setup
                
                # 更新内存中的配置
                site_manager._sites = site_setups
            else:
                # 从数据库重新加载所有配置
                site_setups = await site_manager._load_site_setup(db)
                site_manager._sites = site_setups
            
            logger.info(f"{'从本地文件' if from_local else '从数据库'}重新加载所有站点配置")
            return BaseResponse(
                code=status.HTTP_200_OK,
                message=f"成功{'从本地文件' if from_local else '从数据库'}重新加载 {len(site_setups)} 个站点配置",
                data={
                    "reloaded_site_ids": list(site_setups.keys()),
                    "site_count": len(site_setups),
                    "reload_type": "local" if from_local else "database",
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新加载站点配置失败: {str(e)}")
        logger.debug("错误详情:", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重新加载站点配置失败: {str(e)}"
        ) 