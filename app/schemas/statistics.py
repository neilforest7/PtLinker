from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

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
    user_class: Optional[str]
    uid: Optional[str]
    join_time: Optional[datetime]
    last_active: Optional[datetime]
    upload: Optional[float]
    download: Optional[float]
    ratio: Optional[float]
    bonus: Optional[float]
    seeding_score: Optional[float]
    hr_count: Optional[int]
    bonus_per_hour: Optional[float]
    seeding_size: Optional[float]
    seeding_count: Optional[int]
    task_id: str


class DailyIncrement(BaseModel):
    """每日数据增量统计"""
    date: date
    site_id: str
    upload_increment: Optional[float] = 0
    download_increment: Optional[float] = 0
    bonus_increment: Optional[float] = 0
    seeding_score_increment: Optional[float] = 0
    seeding_size_increment: Optional[float] = 0
    seeding_count_increment: Optional[int] = 0
    task_id: str
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


class LastSuccessTaskResult(BaseModel):
    """最后一次成功任务的结果数据"""
    daily_results: Dict[str, Any] = Field(..., description="每日结果数据，包含用户完整信息")
    daily_increments: Dict[str, Any] = Field(..., description="每日增量数据")
    last_success_time: datetime = Field(..., description="最后成功时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "daily_results": {
                    "username": "example_user",
                    "user_class": "VIP",
                    "uid": "12345",
                    "join_time": "2024-01-01T00:00:00",
                    "last_active": "2024-01-20T10:00:00",
                    "upload": 1024.5,
                    "download": 512.3,
                    "ratio": 2.0,
                    "bonus": 1000.0,
                    "seeding_score": 100.0,
                    "hr_count": 5,
                    "bonus_per_hour": 1.5,
                    "seeding_size": 2048.0,
                    "seeding_count": 50
                }
            }
        }


class LastSuccessTasksResponse(BaseModel):
    """所有站点最后一次成功任务的响应数据"""
    sites: Dict[str, LastSuccessTaskResult]  # 站点ID到结果的映射
    metadata: StatisticsMetadata  # 统计元数据


class StatisticsResponse(BaseModel):
    """统计响应数据"""
    time_range: Dict[str, date]
    metrics: Dict[str, Union[List[DailyResult], List[DailyIncrement], List[CheckInResult]]]
    summary: StatisticsSummary
    metadata: StatisticsMetadata 