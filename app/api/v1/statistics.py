from datetime import date
from http.client import HTTPException
from typing import Dict, List, Optional

from core.database import get_db
from core.logger import get_logger, setup_logger
from fastapi import APIRouter, Depends, Query, status
from schemas.statistics import (CalculationType, MetricType, StatisticsRequest,
                                StatisticsResponse, TimeUnit)
from services.statistics_service import statistics_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
setup_logger()
logger = get_logger(__name__, "stats_api")


@router.get("", response_model=StatisticsResponse, summary="获取统计数据")
async def get_statistics(
    site_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    metrics: List[MetricType] = Query(default=list(MetricType)),
    include_fields: Optional[List[str]] = Query(default=None),
    exclude_fields: Optional[List[str]] = Query(default=None),
    group_by: Optional[List[str]] = Query(default=None),
    time_unit: TimeUnit = TimeUnit.DAY,
    calculation: CalculationType = CalculationType.LAST,
    db: AsyncSession = Depends(get_db)
) -> StatisticsResponse:
    """
    获取站点数据统计信息，支持多种统计指标和聚合方式。
    
    ### 参数说明
    - **site_id**: 站点ID，可选。如果不指定，则统计所有站点数据
    - **start_date**: 统计开始日期，格式：YYYY-MM-DD。如果不指定，默认为7天前
    - **end_date**: 统计结束日期，格式：YYYY-MM-DD。如果不指定，默认为今天
    - **metrics**: 要统计的指标列表，可选值：
        - `daily_results`: 每日最新数据（上传量、下载量、魔力值等）
        - `daily_increments`: 每日增量数据（上传增量、魔力值增量等）
        - `checkins`: 签到数据（签到状态、时间等）
    - **include_fields**: 要包含的字段列表，可选。例如：["upload", "download", "bonus"]
    - **exclude_fields**: 要排除的字段列表，可选。例如：["seeding_size", "seeding_count"]
    - **group_by**: 分组维度列表，可选。例如：["site_id", "date"]
    - **time_unit**: 时间聚合单位，可选值：
        - `day`: 按天聚合（默认）
        - `week`: 按周聚合
        - `month`: 按月聚合
    - **calculation**: 聚合计算方式，可选值：
        - `last`: 取最后一条记录（默认）
        - `max`: 取最大值
        - `min`: 取最小值
        - `avg`: 取平均值
        - `sum`: 取总和
    
    ### 返回数据说明
    返回一个 StatisticsResponse 对象，包含：
    - **time_range**: 实际统计的时间范围
        - start: 开始日期
        - end: 结束日期
    - **metrics**: 各项统计指标的数据
        - daily_results: 每日最新数据列表
        - daily_increments: 每日增量数据列表
        - checkins: 签到数据列表
    - **summary**: 汇总数据
        - total_sites: 统计的站点总数
        - total_upload_increment: 总上传量增量
        - total_bonus_increment: 总魔力值增量
        - successful_checkins: 成功签到次数
    - **metadata**: 统计元数据
        - generated_at: 统计生成时间
        - applied_filters: 应用的过滤条件
    
    ### 使用示例
    1. 获取指定站点最近7天的所有统计数据：
    ```
    GET /api/v1/statistics?site_id=example_site
    ```
    
    2. 获取所有站点指定日期范围的签到统计：
    ```
    GET /api/v1/statistics?start_date=2024-01-01&end_date=2024-01-31&metrics=checkins
    ```
    
    3. 获取指定站点的每日上传和魔力值增量：
    ```
    GET /api/v1/statistics?site_id=example_site&metrics=daily_increments&include_fields=upload_increment,bonus_increment
    ```
    
    4. 按月统计所有站点的数据，并计算平均值：
    ```
    GET /api/v1/statistics?time_unit=month&calculation=avg
    ```
    
    ### 错误处理
    - 如果提供的日期格式不正确，将返回 400 错误
    - 如果请求的站点不存在，将返回相应的错误信息
    - 如果查询过程中发生错误，将返回 500 错误
    """
    try:
        logger.info(f"开始获取统计数据 - 站点: {site_id}, 时间范围: {start_date} 到 {end_date}")
        
        # 构造请求对象
        request = StatisticsRequest(
            site_id=site_id,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            include_fields=include_fields,
            exclude_fields=exclude_fields,
            group_by=group_by,
            time_unit=time_unit,
            calculation=calculation
        )
        
        # 获取统计数据
        response = await statistics_service.get_statistics(db, request)
        
        logger.info("统计数据获取成功")
        return response
        
    except Exception as e:
        error_msg = f"获取统计数据失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.get("/last-success", response_model=Dict[str, Dict], summary="获取每个站点最后一次成功任务的数据")
async def get_last_success_tasks(
    site_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Dict]:
    """
    获取每个站点最后一次成功任务的数据
    
    Args:
        site_id: 可选的站点ID，如果提供则只返回该站点的数据
        db: 数据库会话
        
    Returns:
        Dict[str, Dict]: 包含每个站点最后一次成功任务的数据
    """
    try:
        logger.info(f"开始获取最后成功任务数据 - 站点: {site_id}")
        
        # 调用服务层方法获取数据
        result_data = await statistics_service.get_last_success_tasks(db, site_id)
        
        logger.info("最后成功任务数据获取成功")
        return result_data
        
    except Exception as e:
        error_msg = f"获取最后成功任务数据失败: {str(e)}"
        logger.error(error_msg)
        logger.debug("错误详情:", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

