from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.events import startup_event, shutdown_event
from app.api.v1.router import api_router
from app.api.websockets import ws_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动事件
    await startup_event()
    yield
    # 关闭事件
    await shutdown_event()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan
)

# CORS 设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router) 