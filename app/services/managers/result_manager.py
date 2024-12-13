from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from core.logger import get_logger, setup_logger
from sqlalchemy import and_, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import CheckInResult, Result, Task
from schemas.result import CheckInResultBase, ResultCreate


class ResultManager:
    """结果管理器，用于管理爬虫结果和签到结果的保存"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            setup_logger()
            self.logger = get_logger(name=__name__, site_id="ResultMgr")
            self._session = None
            ResultManager._initialized = True
            
    async def initialize(self, session: AsyncSession) -> None:
        """初始化管理器"""
        self._session = session
        self.logger.info("ResultManager initialized")
        
    @property
    def session(self) -> AsyncSession:
        if not self._session:
            raise RuntimeError("ResultManager not initialized. Call initialize() first.")
        return self._session
        
    async def save_result(self, result_data: ResultCreate) -> Optional[Result]:
        """保存爬虫结果"""
        try:
            # 1. 检查任务是否存在
            stmt = select(Task).where(Task.task_id == result_data.task_id)
            result = await self.session.execute(stmt)
            task = result.scalar_one_or_none()
            
            if not task:
                self.logger.error(f"任务不存在: {result_data.task_id}")
                return None
                
            # 2. 创建结果记录
            result = Result(
                task_id=result_data.task_id,
                site_id=result_data.site_id,
                username=result_data.username,
                user_class=result_data.user_class,
                uid=result_data.uid,
                join_time=result_data.join_time,
                last_active=result_data.last_active,
                upload=result_data.upload,
                download=result_data.download,
                ratio=result_data.ratio,
                bonus=result_data.bonus,
                seeding_score=result_data.seeding_score,
                hr_count=result_data.hr_count,
                bonus_per_hour=result_data.bonus_per_hour,
                seeding_size=result_data.seeding_size,
                seeding_count=result_data.seeding_count
            )
            
            # 3. 保存到数据库
            self.session.add(result)
            await self.session.commit()
            await self.session.refresh(result)
            
            self.logger.info(f"保存爬虫结果成功 - 任务ID: {result_data.task_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"保存爬虫结果失败: {str(e)}")
            await self.session.rollback()
            return None
            
    async def save_checkin_result(
        self, 
        site_id: str,
        result: str,
        checkin_date: Optional[datetime] = None
    ) -> Optional[CheckInResult]:
        """
        保存签到结果，每次都创建新记录
        
        Args:
            site_id: 站点ID
            result: 签到结果
            checkin_date: 签到日期，默认为当前日期
        """
        try:
            # 使用当前日期作为签到日期（如果未提供）
            if not checkin_date:
                checkin_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 创建签到结果记录
            checkin_result = CheckInResult(
                site_id=site_id,
                result=result,
                checkin_date=checkin_date,
                last_run_at=datetime.now()
            )
            
            # 保存到数据库
            self.session.add(checkin_result)
            await self.session.commit()
            await self.session.refresh(checkin_result)
            
            self.logger.info(f"保存签到结果成功 - 站点ID: {site_id}")
            return checkin_result
            
        except Exception as e:
            self.logger.error(f"保存签到结果失败: {str(e)}")
            await self.session.rollback()
            return None
            
    async def get_latest_results(self, site_id: str, limit: int = 10) -> List[Result]:
        """获取站点最新的多个爬虫结果"""
        try:
            # 通过join Task表来获取最新的结果
            stmt = (
                select(Result)
                .join(Task)
                .where(Result.site_id == site_id)
                .order_by(Task.completed_at.desc())
                .limit(limit)
            )
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
            
        except Exception as e:
            self.logger.error(f"获取最新结果失败: {str(e)}")
            return []
            
    async def get_latest_result(self, site_id: str) -> Optional[Result]:
        """获取站点最新的爬虫结果"""
        results = await self.get_latest_results(site_id, limit=1)
        return results[0] if results else None
            
    async def get_latest_checkin_results(self, site_id: str, limit: int = 10) -> List[CheckInResult]:
        """获取站点最新的多个签到结果"""
        try:
            stmt = (
                select(CheckInResult)
                .where(CheckInResult.site_id == site_id)
                .order_by(CheckInResult.last_run_at.desc())
                .limit(limit)
            )
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
            
        except Exception as e:
            self.logger.error(f"获取最新签到结果失败: {str(e)}")
            return []
            
    async def get_latest_checkin_result(self, site_id: str) -> Optional[CheckInResult]:
        """获取站点最新的签到结果"""
        results = await self.get_latest_checkin_results(site_id, limit=1)
        return results[0] if results else None
            
    async def get_results_by_task(self, task_id: str) -> List[Result]:
        """获取指定任务的所有爬虫结果"""
        try:
            stmt = select(Result).where(Result.task_id == task_id)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
            
        except Exception as e:
            self.logger.error(f"获取任务结果失败: {str(e)}")
            return []
            
    async def get_results_by_date_range(
        self,
        site_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Result]:
        """获取指定日期范围内的爬虫结果"""
        try:
            stmt = (
                select(Result)
                .join(Task)
                .where(
                    and_(
                        Result.site_id == site_id,
                        Task.completed_at.between(start_date, end_date)
                    )
                )
                .order_by(Task.completed_at.desc())
            )
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
            
        except Exception as e:
            self.logger.error(f"获取日期范围内的爬虫结果��败: {str(e)}")
            return []
            
    async def get_checkin_result_by_date(
        self, 
        site_id: str, 
        checkin_date: datetime
    ) -> Optional[CheckInResult]:
        """获取指定日期的签到结果"""
        try:
            # 将日期时间设置为当天的开始时间
            date_start = checkin_date.replace(hour=0, minute=0, second=0, microsecond=0)
            date_end = date_start.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            stmt = (
                select(CheckInResult)
                .where(
                    and_(
                        CheckInResult.site_id == site_id,
                        CheckInResult.checkin_date.between(date_start, date_end)
                    )
                )
            )
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            self.logger.error(f"获取指定日期签到结果失败: {str(e)}")
            return None
            
    async def get_checkin_results_by_date_range(
        self,
        site_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[CheckInResult]:
        """获取指定日期范围内的签到结果"""
        try:
            stmt = (
                select(CheckInResult)
                .where(
                    and_(
                        CheckInResult.site_id == site_id,
                        CheckInResult.checkin_date.between(start_date, end_date)
                    )
                )
                .order_by(CheckInResult.checkin_date.desc())
            )
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
            
        except Exception as e:
            self.logger.error(f"获取日期范围内的签到结果失败: {str(e)}")
            return []
            
    async def get_site_statistics(self, site_id: str, days: int = 30) -> Dict[str, Any]:
        """获取站点统计信息"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 获取时间范围内的爬虫结果
            crawl_results = await self.get_results_by_date_range(site_id, start_date, end_date)
            
            # 获取时间范围内的签到结果
            checkin_results = await self.get_checkin_results_by_date_range(site_id, start_date, end_date)
            
            # 计算统计信息
            stats = {
                "site_id": site_id,
                "period_days": days,
                "crawl_count": len(crawl_results),
                "checkin_count": len(checkin_results),
                "checkin_success_rate": sum(1 for r in checkin_results if r.result == "success") / len(checkin_results) if checkin_results else 0,
                "latest_crawl": crawl_results[0] if crawl_results else None,
                "latest_checkin": checkin_results[0] if checkin_results else None,
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取站点统计信息失败: {str(e)}")
            return {
                "site_id": site_id,
                "error": str(e)
            } 