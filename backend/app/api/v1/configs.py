from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import uuid4
from app.db.session import get_db
from app.models.pydantic.schemas import (
    ConfigTemplate,
    CrawlerConfig as ConfigSchema
)
from app.services.config import ConfigService

router = APIRouter()

@router.get("/templates", response_model=List[ConfigTemplate])
async def list_templates(
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db)
):
    return await ConfigService(db).list_templates(category, tags)

@router.post("/templates", response_model=ConfigTemplate)
async def create_template(
    template: ConfigTemplate,
    db: AsyncSession = Depends(get_db)
):
    # 验证配置
    validation = await ConfigService(db).validate_config(template.config)
    if not validation["is_valid"]:
        raise HTTPException(
            status_code=400,
            detail=validation["errors"]
        )
    
    return await ConfigService(db).create_template(template)

@router.post("/validate")
async def validate_config(
    config: ConfigSchema,
    db: AsyncSession = Depends(get_db)
):
    validation = await ConfigService(db).validate_config(config)
    if not validation["is_valid"]:
        raise HTTPException(
            status_code=400,
            detail=validation["errors"]
        )
    return validation

@router.post("/test")
async def test_config(
    config: ConfigSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    test_id = str(uuid4())
    background_tasks.add_task(
        ConfigService(db).test_config,
        config
    )
    return {
        "test_id": test_id,
        "status": "processing"
    }

@router.get("/test/{test_id}")
async def get_test_result(
    test_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await ConfigService(db).get_test_result(test_id)
    if not result:
        raise HTTPException(status_code=404, detail="Test not found")
    return result 