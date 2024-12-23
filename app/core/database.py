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

# 数据库会话上下文管理器
class DatabaseSessionManager:
    def __init__(self):
        self._session: AsyncSession | None = None
        self.logger = get_logger(__name__, "db_manager")
        
    async def __aenter__(self) -> AsyncSession:
        self._session = async_session()
        return self._session
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            if exc_type:
                await self._session.rollback()
                self.logger.error(f"Session rollback due to: {exc_type.__name__}")
            await self._session.close()
            self._session = None

# 全局数据库会话管理器实例
db_manager = DatabaseSessionManager()

# 数据库会话中间件
async def db_session_middleware(request: Request, call_next):
    """数据库会话中间件"""
    async with db_manager as session:
        # 将数据库会话添加到请求状态
        request.state.db = session
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            _logger.error(f"Database middleware error: {str(e)}")
            raise

# 用于API请求的数据库会话依赖
async def get_db(request: Request) -> AsyncSession:
    """从请求状态获取数据库会话"""
    return request.state.db

# 用于初始化的数据库会话获取函数
async def get_init_db() -> AsyncSession:
    """获取初始化用的数据库会话"""
    async with db_manager as session:
        return session

# 健康检查函数
async def check_database_health() -> bool:
    """检查数据库连接健康状态"""
    try:
        async with db_manager as session:
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
        raise

# 数据库清理函数
async def cleanup_db():
    """清理数据库连接"""
    try:
        await engine.dispose()
        _logger.info("Database connections disposed successfully")
    except Exception as e:
        _logger.error(f"Failed to dispose database connections: {str(e)}")
        raise