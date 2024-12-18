from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Union

from core.logger import get_logger
from models.models import CheckInResult as DBCheckInResult
from models.models import Result, Task, TaskStatus
from schemas.statistics import (CalculationType, CheckInResult, DailyIncrement,
                                DailyResult, MetricType, StatisticsMetadata,
                                StatisticsRequest, StatisticsResponse,
                                StatisticsSummary, TimeUnit)
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text


class StatisticsService:
    def __init__(self):
        self.logger = get_logger(name=__name__, site_id="StatsSvc")

    async def get_statistics(
        self,
        db: AsyncSession,
        request: StatisticsRequest
    ) -> StatisticsResponse:
        """获取统计数据"""
        try:
            # 1. 处理时间范围
            start_date, end_date = self._get_date_range(request.start_date, request.end_date)
            
            # 2. 初始化响应数据
            metrics_data = {}
            
            # 3. 根据请求的指标类型获取数据
            for metric in request.metrics:
                if metric == MetricType.DAILY_RESULTS:
                    metrics_data[metric] = await self._get_daily_results(
                        db, start_date, end_date, request.site_id, request.calculation
                    )
                elif metric == MetricType.DAILY_INCREMENTS:
                    metrics_data[metric] = await self._get_daily_increments(
                        db, start_date, end_date, request.site_id
                    )
                elif metric == MetricType.CHECKINS:
                    metrics_data[metric] = await self._get_checkin_results(
                        db, start_date, end_date, request.site_id
                    )
            
            # 4. 计算汇总数据
            summary = await self._calculate_summary(metrics_data)
            
            # 5. 生成响应
            return StatisticsResponse(
                time_range={"start": start_date, "end": end_date},
                metrics=metrics_data,
                summary=summary,
                metadata=StatisticsMetadata(
                    generated_at=datetime.now(),
                    applied_filters={
                        "site_id": [request.site_id] if request.site_id else [],
                        "time_unit": request.time_unit.value,
                        "calculation": request.calculation.value
                    }
                )
            )
            
        except Exception as e:
            self.logger.error(f"获取统计数据失败: {str(e)}")
            raise

    def _get_date_range(
        self,
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> tuple[date, date]:
        """获取日期范围，默认为最近7天"""
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=6)
        return start_date, end_date

    async def _get_daily_results(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
        site_id: Optional[str],
        calculation: CalculationType
    ) -> List[DailyResult]:
        """获取每日最后结果统计"""
        try:
            # 构建基础查询
            query = (
                select(Task, Result)
                .join(Result, Task.task_id == Result.task_id)
                .where(
                    and_(
                        func.date(Task.created_at) >= start_date,
                        func.date(Task.created_at) <= end_date,
                        Task.status == TaskStatus.SUCCESS
                    )
                )
            )
            
            # 添加站点过滤
            if site_id:
                query = query.where(Task.site_id == site_id)
            
            # 执行查询
            result = await db.execute(query)
            rows = result.all()
            
            # 按日期和站点分组，获取每天的最后一条记录
            daily_results = {}
            for task, result in rows:
                key = (task.site_id, task.created_at.date())
                if key not in daily_results or task.created_at > daily_results[key][0].created_at:
                    daily_results[key] = (task, result)
            
            # 转换为响应格式
            return [
                DailyResult(
                    date=task.created_at.date(),
                    site_id=task.site_id,
                    username=result.username,
                    upload=result.upload,
                    download=result.download,
                    ratio=result.ratio,
                    bonus=result.bonus,
                    seeding_size=result.seeding_size,
                    seeding_count=result.seeding_count,
                    task_id=task.task_id
                )
                for (_, _), (task, result) in daily_results.items()
            ]
            
        except Exception as e:
            self.logger.error(f"获取每日结果统计失败: {str(e)}")
            raise

    async def _get_daily_increments(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
        site_id: Optional[str]
    ) -> List[DailyIncrement]:
        """获取每日数据增量统计"""
        try:
            # 获取每日最后结果
            daily_results = await self._get_daily_results(
                db, start_date, end_date, site_id, CalculationType.LAST
            )
            
            # 按站点分组
            site_results = {}
            for result in daily_results:
                if result.site_id not in site_results:
                    site_results[result.site_id] = []
                site_results[result.site_id].append(result)
            
            # 计算每日增量
            increments = []
            for site_id, results in site_results.items():
                # 按日期排序
                results.sort(key=lambda x: x.date)
                
                # 计算每日增量
                for i in range(1, len(results)):
                    prev = results[i-1]
                    curr = results[i]
                    
                    increments.append(DailyIncrement(
                        date=curr.date,
                        site_id=site_id,
                        upload_increment=curr.upload - prev.upload if curr.upload and prev.upload else None,
                        bonus_increment=curr.bonus - prev.bonus if curr.bonus and prev.bonus else None,
                        seeding_size_increment=curr.seeding_size - prev.seeding_size if curr.seeding_size and prev.seeding_size else None,
                        seeding_count_increment=curr.seeding_count - prev.seeding_count if curr.seeding_count and prev.seeding_count else None,
                        reference_task_id=curr.task_id
                    ))
            
            return increments
            
        except Exception as e:
            self.logger.error(f"获取每日增量统计失败: {str(e)}")
            raise

    async def _get_checkin_results(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
        site_id: Optional[str]
    ) -> List[CheckInResult]:
        """获取签到结果统计"""
        try:
            # 构建查询
            query = (
                select(Task, DBCheckInResult)
                .join(DBCheckInResult, Task.task_id == DBCheckInResult.task_id)
                .where(
                    and_(
                        func.date(DBCheckInResult.checkin_date) >= start_date,
                        func.date(DBCheckInResult.checkin_date) <= end_date
                    )
                )
            )
            
            # 添加站点过滤
            if site_id:
                query = query.where(Task.site_id == site_id)
            
            # 执行查询
            result = await db.execute(query)
            rows = result.all()
            
            # 按日期和站点分组，处理多次签到结果
            daily_checkins = {}
            for task, checkin in rows:
                # 使用签到日期的日期部分作为键
                key = (task.site_id, checkin.checkin_date.date())
                current_result = checkin.result.lower()
                
                if key not in daily_checkins:
                    daily_checkins[key] = {
                        'task': task,
                        'checkin': checkin,
                        'success': current_result in ['success', 'already']
                    }
                else:
                    # 如果当前结果是成功的，更新为最新的成功记录
                    if current_result in ['success', 'already']:
                        daily_checkins[key]['success'] = True
                        if checkin.checkin_date > daily_checkins[key]['checkin'].checkin_date:
                            daily_checkins[key]['task'] = task
                            daily_checkins[key]['checkin'] = checkin
            
            # 转换为响应格式
            return [
                CheckInResult(
                    date=info['checkin'].checkin_date.date(),
                    site_id=info['task'].site_id,
                    checkin_status='success' if info['success'] else 'failed',
                    checkin_time=info['checkin'].checkin_date,
                    task_id=info['task'].task_id
                )
                for key, info in daily_checkins.items()
            ]
            
        except Exception as e:
            self.logger.error(f"获取签到结果统计失败: {str(e)}")
            raise

    async def _calculate_summary(
        self,
        metrics_data: Dict[str, Union[List[DailyResult], List[DailyIncrement], List[CheckInResult]]]
    ) -> StatisticsSummary:
        """计算汇总数据"""
        try:
            total_sites = set()
            total_upload_increment = 0.0
            total_bonus_increment = 0.0
            successful_checkins = 0
            
            # 统计站点数
            for metric_type, data in metrics_data.items():
                for item in data:
                    total_sites.add(item.site_id)
            
            # 统计增量数据
            if MetricType.DAILY_INCREMENTS in metrics_data:
                for increment in metrics_data[MetricType.DAILY_INCREMENTS]:
                    total_upload_increment += increment.upload_increment or 0
                    total_bonus_increment += increment.bonus_increment or 0
            
            # 统计签到数据
            if MetricType.CHECKINS in metrics_data:
                successful_checkins = len(metrics_data[MetricType.CHECKINS])
            
            return StatisticsSummary(
                total_sites=len(total_sites),
                total_upload_increment=total_upload_increment,
                total_bonus_increment=total_bonus_increment,
                successful_checkins=successful_checkins
            )
            
        except Exception as e:
            self.logger.error(f"计算汇总数据失败: {str(e)}")
            raise


# 全局统计服务实例
statistics_service = StatisticsService() 