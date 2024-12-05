from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from app.schemas.config import CrawlerConfig, ConfigUpdateResponse
from app.core.config import get_settings
import os
from dotenv import load_dotenv, set_key
import json
from app.core.logger import get_logger

router = APIRouter(tags=["config"])
_logger = get_logger(service="config_api")

def _convert_to_env_key(key: str) -> str:
    """将配置键转换为环境变量格式"""
    return key.upper()

def _load_current_config() -> Dict[str, Any]:
    """加载当前的环境变量配置"""
    env_path = os.path.join("..", "Crawler_py", ".env")
    if not os.path.exists(env_path):
        raise HTTPException(status_code=404, detail="Crawler .env file not found")
    
    load_dotenv(env_path)
    config = {}
    
    # 从CrawlerConfig模型中获取所有字段
    for field_name, field in CrawlerConfig.model_fields.items():
        env_key = _convert_to_env_key(field_name)
        value = os.getenv(env_key)
        if value is not None:
            # 根据字段类型转换值
            if isinstance(field.default, bool):
                config[field_name] = value.lower() == "true"
            elif isinstance(field.default, int):
                config[field_name] = int(value)
            elif isinstance(field.default, float):
                config[field_name] = float(value)
            elif isinstance(field.default, list):
                config[field_name] = value.split(",") if value else []
            else:
                config[field_name] = value
                
    return config

def _update_env_file(updates: Dict[str, Any]) -> None:
    """更新.env文件中的配置"""
    env_path = os.path.join("..", "Crawler_py", ".env")
    
    for key, value in updates.items():
        env_key = _convert_to_env_key(key)
        # 处理列表类型的值
        if isinstance(value, list):
            value = ",".join(value)
        # 将值转换为字符串
        set_key(env_path, env_key, str(value))

@router.get("/crawler", response_model=CrawlerConfig)
async def get_crawler_config():
    """获取爬虫配置"""
    logger_ctx = get_logger(service="get_crawler_config")
    try:
        config = _load_current_config()
        logger_ctx.info("Fetching crawler configuration")
        return CrawlerConfig(**config)
    except Exception as e:
        logger_ctx.error(f"Failed to get crawler configuration: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load config: {str(e)}")

@router.patch("/crawler", response_model=ConfigUpdateResponse)
async def update_crawler_config(updates: Dict[str, Any]):
    """更新爬虫配置"""
    logger_ctx = get_logger(service="update_crawler_config")
    try:
        # 验证更新的字段
        current_config = _load_current_config()
        validated_updates = {}
        
        for key, value in updates.items():
            if key not in CrawlerConfig.model_fields:
                raise HTTPException(status_code=400, detail=f"Invalid config field: {key}")
            validated_updates[key] = value
        
        # 更新配置文件
        _update_env_file(validated_updates)
        
        logger_ctx.info("Configuration updated successfully")
        return ConfigUpdateResponse(
            success=True,
            message="Configuration updated successfully",
            updated_fields=validated_updates
        )
    except Exception as e:
        logger_ctx.error(f"Failed to update crawler configuration: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")

@router.post("/crawler/reset", response_model=ConfigUpdateResponse)
async def reset_crawler_config():
    """重置爬虫配置为默认值"""
    logger_ctx = get_logger(service="reset_crawler_config")
    try:
        default_config = CrawlerConfig().model_dump()
        _update_env_file(default_config)
        
        logger_ctx.info("Configuration reset to defaults")
        return ConfigUpdateResponse(
            success=True,
            message="Configuration reset to defaults",
            updated_fields=default_config
        )
    except Exception as e:
        logger_ctx.error(f"Failed to reset crawler configuration: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reset config: {str(e)}") 