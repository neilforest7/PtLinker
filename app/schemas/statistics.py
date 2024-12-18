from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field


class TimeUnit(str, Enum):
    """时间聚合单位"""
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class CalculationType(str, Enum):
    """计算方式"""
    LAST = "last"
    MAX = "max"
    MIN = "min"
    AVG = "avg"
    SUM = "sum"


class MetricType(str, Enum):
    """统计指标类型"""
    DAILY_RESULTS = "daily_results"
    DAILY_INCREMENTS = "daily_increments"
    CHECKINS = "checkins"


class StatisticsRequest(BaseModel):
    """统计请求参数"""
    site_id: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    metrics: List[MetricType] = Field(default_factory=lambda: list(MetricType))
    include_fields: Optional[List[str]] = None
    exclude_fields: Optional[List[str]] = None
    group_by: Optional[List[str]] = None
    time_unit: TimeUnit = TimeUnit.DAY
    calculation: CalculationType = CalculationType.LAST


class DailyResult(BaseModel):
    """每日最后结果统计"""
    date: date
    site_id: str
    username: Optional[str]
    upload: Optional[float]
    download: Optional[float]
    ratio: Optional[float]
    bonus: Optional[float]
    seeding_size: Optional[float]
    seeding_count: Optional[int]
    task_id: str


class DailyIncrement(BaseModel):
    """每日数据增量统计"""
    date: date
    site_id: str
    upload_increment: Optional[float] = 0
    bonus_increment: Optional[float] = 0
    seeding_size_increment: Optional[float] = 0
    seeding_count_increment: Optional[int] = 0
    reference_task_id: str


class CheckInResult(BaseModel):
    """签到统计"""
    date: date
    site_id: str
    checkin_status: str
    checkin_time: datetime
    task_id: str


class StatisticsSummary(BaseModel):
    """统计汇总数据"""
    total_sites: int
    total_upload_increment: float
    total_bonus_increment: float
    successful_checkins: int


class StatisticsMetadata(BaseModel):
    """统计元数据"""
    generated_at: datetime
    applied_filters: Dict[str, Union[str, List[str]]]


class StatisticsResponse(BaseModel):
    """统计响应数据"""
    time_range: Dict[str, date]
    metrics: Dict[str, Union[List[DailyResult], List[DailyIncrement], List[CheckInResult]]]
    summary: StatisticsSummary
    metadata: StatisticsMetadata 