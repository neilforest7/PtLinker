from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.database import engine, Base
from app.api.v1 import router as api_router

# 启动时创建数据库表
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 创建数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # 关闭数据库连接
    await engine.dispose()

app = FastAPI(
    title="PtLinker API",
    description="PT站点爬虫管理API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 注册API路由
app.include_router(api_router, prefix="/api/v1") 