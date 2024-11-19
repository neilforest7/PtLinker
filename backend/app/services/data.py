from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.sqlalchemy.models import CrawledData
from typing import Optional, List
import json

class DataService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def list_data(
        self,
        skip: int = 0,
        limit: int = 10,
        task_id: Optional[str] = None,
        url: Optional[str] = None
    ) -> List[CrawledData]:
        query = select(CrawledData)
        
        # 添加过滤条件
        if task_id:
            query = query.where(CrawledData.task_id == task_id)
        
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def create_data(self, task_id: str, url: str, data: dict):
        db_data = CrawledData(
            task_id=task_id,
            url=url,
            data=data
        )
        self.db.add(db_data)
        await self.db.commit()
        await self.db.refresh(db_data)
        return db_data 