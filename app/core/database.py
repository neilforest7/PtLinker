from core.config import database_settings
from core.logger import get_logger
from fastapi import Request
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool

_logger = get_logger(__name__, "database")

# 创建带连接池的异步引擎
from core.config import database_settings
from core.logger import get_logger
from fastapi import Request
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool

_logger = get_logger(__name__, "database")

# 创建带连接池的异步引擎
engine = create_async_engine(
    database_settings.DATABASE_URL,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=database_settings.DB_POOL_SIZE,
    max_overflow=database_settings.DB_MAX_OVERFLOW,
    pool_timeout=database_settings.DB_POOL_TIMEOUT,
    pool_recycle=database_settings.DB_POOL_RECYCLE,
    echo=database_settings.DB_ECHO,
)

# 创建会话工厂
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

class Base(DeclarativeBase):
    pass

# 数据库会话中间件
async def db_session_middleware(request: Request, call_next):
    """数据库会话中间件"""
    session = async_session()
    request.state.db = session
    try:
        response = await call_next(request)
        await session.commit()
        return response
    except Exception as e:
        await session.rollback()
        _logger.error(f"Database middleware error: {str(e)}")
        raise
    finally:
        await session.close()

# 用于API请求的数据库会话依赖
async def get_db(request: Request) -> AsyncSession:
    """从请求状态获取数据库会话"""
    return request.state.db

# 用于初始化的数据库会话获取函数
async def get_init_db() -> AsyncSession:
    """获取初始化用的数据库会话"""
    return async_session()

# 健康检查函数
async def check_database_health() -> bool:
    """检查数据库连接健康状态"""
    try:
        async with async_session() as session:
            await session.execute("SELECT 1")
        return True
    except Exception as e:
        _logger.error(f"Database health check failed: {str(e)}")
        return False

# 数据库初始化函数
async def init_db():
    """初始化数据库"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _logger.info("Database tables created successfully")
    except Exception as e:
        _logger.error(f"Database initialization failed: {str(e)}")
        _logger.error(f"Database initialization failed: {str(e)}")
        raise

# 数据库清理函数
async def cleanup_db():
    """清理数据库连接"""
    try:
        await engine.dispose()
        _logger.info("Database connections disposed successfully")
        _logger.info("Database connections disposed successfully")
    except Exception as e:
        _logger.error(f"Failed to dispose database connections: {str(e)}")
        raise        _logger.error(f"Failed to dispose database connections: {str(e)}")
        raise
