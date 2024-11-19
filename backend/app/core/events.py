from app.db.session import engine
from app.models.sqlalchemy.models import Base
import os
from app.core.config import settings

async def startup_event():
    # 创建数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建导出目录
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)

async def shutdown_event():
    # 关闭数据库连接
    await engine.dispose()