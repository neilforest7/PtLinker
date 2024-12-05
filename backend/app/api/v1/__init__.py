from fastapi import APIRouter
from .tasks import router as tasks_router
from .crawlers import router as crawlers_router
from .config import router as config_router

# 创建主路由
router = APIRouter()

# 注册子路由
router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
router.include_router(crawlers_router, prefix="/crawlers", tags=["crawlers"])
router.include_router(config_router, prefix="/config", tags=["config"]) 