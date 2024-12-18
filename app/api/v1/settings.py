from typing import Any, Dict

from core.database import get_db
from core.logger import get_logger
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.settings import SettingsCreate, SettingsResponse, SettingsUpdate
from schemas.sitesetup import BaseResponse
from services.managers.setting_manager import SettingManager
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/settings", tags=["settings"])
logger = get_logger(name=__name__, site_id="settings_api")


@router.get("", response_model=SettingsResponse, summary="获取当前系统设置")
async def get_settings(db: AsyncSession = Depends(get_db)) -> SettingsResponse:
    """获取当前系统设置"""
    try:
        # 确保设置已初始化
        if not SettingManager.get_instance()._settings:
            logger.debug("设置未初始化，正在初始化...")
            await SettingManager.get_instance().initialize(db)
            
        # 获取所有设置
        settings_dict = await SettingManager.get_instance().get_all_settings()
        logger.debug("成功获取所有设置")
        return SettingsResponse(**settings_dict)
        
    except Exception as e:
        logger.error(f"获取设置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统设置失败: {str(e)}"
        )


# @router.post("", response_model=SettingsResponse)
# async def create_settings(
#     settings_data: SettingsCreate,
#     db: AsyncSession = Depends(get_db)
# ) -> SettingsResponse:
#     """创建新的系统设置（会覆盖现有设置）"""
#     try:
#         # 确保设置已初始化
#         if not settings._settings:
#             logger.debug("设置未初始化，正在初始化...")
#             await settings.initialize(db)
            
#         # 更新所有设置
#         logger.debug("正在更新所有设置")
#         await settings.update_settings(db, settings_data.model_dump())
        
#         # 获取更新后的设置
#         settings_dict = await settings.get_all_settings()
#         logger.debug("设置创建/更新成功")
#         return SettingsResponse(**settings_dict)
        
#     except Exception as e:
#         logger.error(f"创建设置失败: {str(e)}", exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"创建系统设置失败: {str(e)}"
#         )


@router.patch("", response_model=SettingsResponse, summary="更新系统设置（部分更新）")
async def update_settings(
    settings_data: SettingsUpdate,
    db: AsyncSession = Depends(get_db)
) -> SettingsResponse:
    """更新系统设置（部分更新）"""
    # TODO: 422 Unprocessable 
    try:
        # 确保设置已初始化
        if not SettingManager.get_instance()._settings:
            logger.debug("设置未初始化，正在初始化...")
            await SettingManager.get_instance().initialize(db)
            
        # 只更新非空值
        update_data = {k: v for k, v in settings_data.model_dump().items() if v is not None}
        if update_data:
            logger.debug(f"正在更新设置: {update_data}")
            await SettingManager.get_instance().update_settings(db, update_data)
        else:
            logger.debug("没有需要更新的有效设置")
        
        # 获取更新后的设置
        settings_dict = await SettingManager.get_instance().get_all_settings()
        logger.debug("设置更新成功")
        return SettingsResponse(**settings_dict)
        
    except Exception as e:
        logger.error(f"更新设置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新系统设置失败: {str(e)}"
        )


@router.post("/reset", response_model=SettingsResponse, summary="重置系统设置为环境变量和默认值")
async def reset_settings(db: AsyncSession = Depends(get_db)) -> SettingsResponse:
    """重置系统设置为环境变量和默认值"""
    try:
        logger.info("开始重置设置")
        # 重置设置
        await SettingManager.get_instance().reset_settings(db)
        
        # 获取重置后的设置
        settings_dict = await SettingManager.get_instance().get_all_settings()
        logger.info("设置重置完成")
        return SettingsResponse(**settings_dict)
        
    except Exception as e:
        logger.error(f"重置设置失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重置系统设置失败: {str(e)}"
        )


@router.get("/value/{key}", response_model=Dict[str, Any], summary="获取指定设置项的值")
async def get_setting_value(
    key: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """获取指定设置项的值"""
    try:
        # 确保设置已初始化
        if not SettingManager.get_instance()._settings:
            logger.debug("设置未初始化，正在初始化...")
            await SettingManager.get_instance().initialize(db)
            
        # 检查设置项是否存在
        if not hasattr(SettingManager.get_instance()._settings, key):
            logger.warning(f"尝试访问不存在的设置项: {key}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"设置项 {key} 不存在"
            )
            
        value = await SettingManager.get_instance().get_setting(key)
        logger.debug(f"获取设置项 {key} 的值: {value}")
        return {"key": key, "value": value}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取设置值失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取设置值失败: {str(e)}"
        )


@router.put("/value/{key}", response_model=BaseResponse, summary="设置指定配置项的值")
async def set_setting_value(
    key: str,
    value: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """设置指定配置项的值"""
    try:
        # 确保设置已初始化
        if not SettingManager.get_instance()._settings:
            logger.debug("设置未初始化，正在初始化...")
            await SettingManager.get_instance().initialize(db)
            
        # 检查设置项是否存在
        if not hasattr(SettingManager.get_instance()._settings, key):
            logger.warning(f"尝试设置不存在的设置项: {key}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"设置项 {key} 不存在"
            )
            
        # 更新设置值
        logger.debug(f"正在设置 {key} 的值: {value.get('value')}")
        await SettingManager.get_instance().set_setting(db, key, value.get("value"))
        
        # 获取更新后的值
        updated_value = await SettingManager.get_instance().get_setting(key)
        logger.debug(f"成功更新设置项 {key} 的值为: {updated_value}")
        return BaseResponse(
            code=status.HTTP_200_OK,
            message=f"成功更新设置项 {key} 的值为: {updated_value}",
            data={"key": key, "value": updated_value}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置配置值失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设置配置值失败: {str(e)}"
        ) 