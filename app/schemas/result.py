from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator

# Result Schema
class ResultBase(BaseModel):
    """爬虫结果基础模型"""
    username: Optional[str] = Field(None, description="用户名")
    user_class: Optional[str] = Field(None, description="用户等级")
    uid: Optional[str] = Field(None, description="用户ID")
    join_time: Optional[datetime] = Field(None, description="加入时间")
    last_active: Optional[datetime] = Field(None, description="最后活动时间")
    upload: Optional[float] = Field(None, ge=0, description="上传量")
    download: Optional[float] = Field(None, ge=0, description="下载量")
    ratio: Optional[float] = Field(None, ge=0, description="分享率")
    bonus: Optional[float] = Field(None, ge=0, description="魔力值")
    seeding_score: Optional[float] = Field(None, ge=0, description="做种积分")
    hr_count: Optional[int] = Field(None, ge=0, description="HR数量")
    bonus_per_hour: Optional[float] = Field(None, ge=0, description="每小时魔力值")
    seeding_size: Optional[float] = Field(None, ge=0, description="做种体积")
    seeding_count: Optional[int] = Field(None, ge=0, description="做种数量")

    @validator('ratio')
    def validate_ratio(cls, v, values):
        """验证分享率"""
        if v is None and 'upload' in values and 'download' in values:
            upload = values.get('upload')
            download = values.get('download')
            if upload is not None and download is not None:
                if download == 0:
                    return 999999
                return upload / download
        return v


class ResultCreate(ResultBase):
    """创建爬虫结果模型"""
    task_id: str = Field(..., min_length=1, max_length=500, description="任务ID")
    site_id: str = Field(..., min_length=1, max_length=500, description="站点ID")


class ResultResponse(ResultBase):
    """爬虫结果响应模型"""
    task_id: str = Field(..., description="任务ID")
    site_id: str = Field(..., description="站点ID")

    class Config:
        from_attributes = True


class CheckInResultBase(BaseModel):
    """签到结果基础模型"""
    site_id: str = Field(..., min_length=1, max_length=500, description="站点ID")
    result: str = Field(..., min_length=1, max_length=500, description="签到结果")
    checkin_date: datetime = Field(..., description="签到日期")
    last_run_at: datetime = Field(..., description="最后运行时间")


class CheckInResultCreate(CheckInResultBase):
    """创建签到结果模型"""
    pass


class CheckInResultResponse(CheckInResultBase):
    """签到结果响应模型"""
    class Config:
        from_attributes = True
