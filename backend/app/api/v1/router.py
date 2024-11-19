from fastapi import APIRouter
from app.api.v1 import tasks, configs, data

api_router = APIRouter()

api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(configs.router, prefix="/configs", tags=["configs"])
api_router.include_router(data.router, prefix="/data", tags=["data"]) 