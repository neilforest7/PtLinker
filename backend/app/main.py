
from contextlib import asynccontextmanager
from app.core.database import engine, Base
from app.api.v1 import tasks, websockets, crawlers, config
from app.core.logger import setup_logger, get_logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
_logger = get_logger(service="app")

# 启动时创建数据库表
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    _logger.info("Starting application")
    try:
        # 创建数据库表
        _logger.info("Creating database tables")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _logger.info("Database tables created successfully")
        yield
    except Exception as e:
        _logger.error(f"Failed to initialize application: {str(e)}", exc_info=True)
        raise
    finally:
        # 关闭数据库连接
        _logger.info("Closing database connection")
        await engine.dispose()
        _logger.info("Application shutdown complete")

app = FastAPI(
    title="PtLinker API",
    description="PT站点爬虫管理API",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(websockets.router, tags=["websockets"])
app.include_router(crawlers.router, prefix="/api/v1/crawlers", tags=["crawlers"])
app.include_router(config.router, prefix="/api/v1/config", tags=["config"])

# 健康检查
@app.get("/health")
async def health_check():
    """健康检查端点"""
    logger_ctx = get_logger(service="health_check")
    logger_ctx.debug("Health check requested")
    return {"status": "ok"} 