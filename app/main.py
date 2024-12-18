import traceback
from contextlib import asynccontextmanager

import uvicorn
from api.v1 import settings as settings_api
from api.v1 import site_configs, tasks, statistics, queue, crawler_configs
from core.database import cleanup_db, get_db, init_db
from core.logger import get_logger, setup_logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.crawler.task_config import BaseTaskConfig
from services.managers.process_manager import ProcessManager
from services.managers.queue_manager import QueueManager
from services.managers.result_manager import ResultManager
from services.managers.setting_manager import SettingManager
from services.managers.site_manager import SiteManager
from sqlalchemy.ext.asyncio import AsyncSession

setup_logger()
_logger = get_logger(name=__name__, site_id="Main")

# 全局管理器实例
process_manager = ProcessManager()
queue_manager = QueueManager()
site_manager = SiteManager()
setting_manager = SettingManager()
result_manager = ResultManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    db: AsyncSession | None = None
    try:
        _logger.info("Starting application")
        # setup_logger()
        # _logger = get_logger(name=__name__, site_id="lifespan")
        # 1. 初始化数据库
        _logger.info("Initializing database")
        try:
            await init_db()
            _logger.info("Database initialized successfully")
        except Exception as init_error:
            error_msg = f"Failed to initialize database: {init_error.__class__.__name__}"
            _logger.error(error_msg)
            _logger.debug(traceback.format_exc())
            raise

        # 2. 获取数据库会话
        _logger.debug("Getting database session")
        try:
            db = await anext(get_db())
            _logger.debug("Database session acquired")
        except Exception as session_error:
            error_msg = f"Failed to get database session: {session_error.__class__.__name__}"
            _logger.error(error_msg)
            _logger.debug(traceback.format_exc())
            raise

        # 3. 初始化所有管理器
        _logger.info("Initializing managers")
        try:
            # 按依赖顺序初始化
            _logger.debug("Initializing settings manager")
            await setting_manager.initialize(db)
            
            _logger.debug("Initializing site manager")
            site_manager = SiteManager.get_instance()
            await site_manager.initialize(db)
            
            _logger.debug("Initializing queue manager")
            await queue_manager.initialize(max_concurrency=await setting_manager.get_setting("crawler_max_concurrency"))
            
            _logger.debug("Initializing process manager")
            await process_manager.initialize(queue_manager=queue_manager, db=db)
            
            _logger.debug("Initializing result manager")
            await result_manager.initialize(db)
            
            _logger.info("All managers initialized successfully")
        except Exception as manager_error:
            error_msg = f"Failed to initialize managers: {manager_error.__class__.__name__}"
            _logger.error(error_msg)
            _logger.debug(traceback.format_exc())
            raise

        # 4. 初始化任务配置
        _logger.debug("Initializing task config")
        try:
            BaseTaskConfig.set_site_manager(site_manager)
            _logger.info("Task config initialized successfully")
        except Exception as config_error:
            error_msg = f"Failed to initialize task config: {config_error.__class__.__name__}"
            _logger.error(error_msg)
            _logger.debug(traceback.format_exc())
            raise
        
        _logger.info("Application startup complete")
        
        # 保持应用运行
        try:
            yield
            _logger.info("Application received shutdown signal")
        except Exception as e:
            error_msg = f"Application runtime error: {e.__class__.__name__}"
            _logger.error(error_msg)
            _logger.debug(traceback.format_exc())
            raise
        
    except Exception as e:
        error_msg = f"Failed to initialize application: {e.__class__.__name__}"
        _logger.error(error_msg)
        _logger.debug(traceback.format_exc())
        raise
    finally:
        _logger.info("Starting cleanup process")
        cleanup_errors = []
        
        # 1. 清理进程管理器
        if process_manager:
            try:
                _logger.debug("Cleaning up process manager")
                await process_manager.cleanup()
            except Exception as e:
                error_msg = f"Process manager cleanup failed: {e.__class__.__name__}"
                cleanup_errors.append(error_msg)
                _logger.error(error_msg)
                _logger.debug(traceback.format_exc())
        
        # 2. 清理队列管理器
        if queue_manager:
            try:
                _logger.debug("Cleaning up queue manager")
                await queue_manager.cleanup(db)
            except Exception as e:
                error_msg = f"Queue manager cleanup failed: {e.__class__.__name__}"
                cleanup_errors.append(error_msg)
                _logger.error(error_msg)
                _logger.debug(traceback.format_exc())
        
        # 3. 关闭数据库会话
        if db is not None:
            try:
                _logger.debug("Closing database session")
                await db.close()
            except Exception as e:
                error_msg = f"Database session cleanup failed: {e.__class__.__name__}"
                cleanup_errors.append(error_msg)
                _logger.error(error_msg)
                _logger.debug(traceback.format_exc())
        
        # 4. 清理数据库连接
        try:
            await cleanup_db()
        except Exception as e:
            error_msg = f"Database cleanup failed: {e.__class__.__name__}"
            cleanup_errors.append(error_msg)
            _logger.error(error_msg)
            _logger.debug(traceback.format_exc())
            
        if cleanup_errors:
            _logger.error("Cleanup completed with errors:")
            for error in cleanup_errors:
                _logger.error(f"  - {error}")
        else:
            _logger.info("Cleanup completed successfully")
            
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
app.include_router(queue.router, prefix="/api/v1/queue", tags=["queue"])
app.include_router(settings_api.router, prefix="/api/v1", tags=["settings"])
app.include_router(site_configs.router, prefix="/api/v1", tags=["site_configs"])
app.include_router(crawler_configs.router, prefix="/api/v1", tags=["crawler_configs"])
app.include_router(statistics.router, prefix="/api/v1/statistics", tags=["statistics"])

# 健康检查
@app.get("/health")
async def health_check():
    """健康检查端点"""
    logger_ctx = get_logger(name=__name__, site_id="HealthCheck")
    logger_ctx.debug("Health check requested")
    return {"status": "ok"}

if __name__ == "__main__":
    # 配置uvicorn以支持长连接
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式下启用热重载
        workers=1,    # 使用单进程以确保管理器状态一致
        timeout_keep_alive=120,  # 保持连接活跃时间（秒）
        backlog=2048,  # 连接队列大小
        limit_concurrency=1000,  # 并发连接限制
        limit_max_requests=None,  # 不限制最大请求数
        timeout_graceful_shutdown=60,  # 优雅关闭超时时间（秒）
        log_level="info",
        access_log=True
    ) 