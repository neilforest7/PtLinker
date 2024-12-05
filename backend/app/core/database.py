from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import get_settings
from app.core.logger import get_logger
from typing import AsyncGenerator

settings = get_settings()
_logger = get_logger(service="database")

# 创建异步引擎
try:
    _logger.info("Creating database engine")
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,  # 设置为True会输出SQL语句
        future=True
    )
    _logger.debug("Database engine created successfully")
except Exception as e:
    _logger.error(f"Failed to create database engine: {str(e)}", exc_info=True)
    raise

# 创建会话工厂
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 声明基类
Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    session = async_session()
    logger_ctx = get_logger(service="database")
    try:
        logger_ctx.debug("Database session created")
        yield session
    except Exception as e:
        logger_ctx.error(f"Database session error: {str(e)}", exc_info=True)
        await session.rollback()
        raise
    finally:
        logger_ctx.debug("Closing database session")
        await session.close() 