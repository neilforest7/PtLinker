import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from core.logger import get_logger, setup_logger
from typing import AsyncGenerator

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "ptlinker.db")

# 数据库URL
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
# setup_logger()
_logger = get_logger(name=__name__, site_id="database")

# 声明基类
Base = declarative_base()

# 创建异步引擎
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # 设置为True会输出SQL语句
    future=True,
    connect_args={
        "check_same_thread": False,  # SQLite特定配置
    },
)

# 创建会话工厂
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def init_db() -> None:
    """初始化数据库"""
    try:
        _logger.info("Initializing database")
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        # 创建所有表
        _logger.debug("Creating database tables")
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn))
        _logger.debug("Database tables created successfully")
            
        _logger.info("Database initialized successfully")
    except Exception as e:
        _logger.error(f"Database initialization failed: {e.__class__.__name__}")
        _logger.debug(f"Error details: {str(e)}", exc_info=True)
        raise

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    session = async_session()
    _logger.debug("Database session created")
    try:
        yield session
    except Exception as e:
        _logger.error(f"Database session error: {e.__class__.__name__}")
        _logger.debug(f"Error details: {str(e)}", exc_info=True)
        raise

async def cleanup_db() -> None:
    """清理数据库连接"""
    try:
        _logger.debug("Disposing database engine")
        await engine.dispose()
        _logger.debug("Database engine disposed successfully")
    except Exception as e:
        _logger.error(f"Failed to dispose database engine: {e.__class__.__name__}")
        _logger.debug(f"Error details: {str(e)}", exc_info=True)
        raise 