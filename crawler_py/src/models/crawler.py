from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class FormField(BaseModel):
    """表单字段配置"""
    name: str
    type: Literal["text", "password", "checkbox", "radio", "hidden", "submit"]
    selector: str
    value: Optional[str | bool] = None
    required: bool = True
    validation: Optional[Dict[str, str]] = None

class CaptchaConfig(BaseModel):
    """验证码配置"""
    type: Optional[str] = 'custom'
    element: Dict[str, str]
    input: FormField
    hash: Optional[Dict[str, str]] = None
    solver: Optional[Dict[str, Any]] = None

class LoginConfig(BaseModel):
    """登录配置"""
    login_url: str
    form_selector: str
    pre_login: Optional[Dict[str, Any]] = None
    fields: Dict[str, FormField]
    captcha: Optional[CaptchaConfig] = None
    success_check: Dict[str, str]

class ExtractRule(BaseModel):
    """数据提取规则"""
    name: str
    selector: str
    type: Literal["text", "attribute", "html"]
    attribute: Optional[str] = None
    required: bool = False
    transform: Optional[str] = None

class CrawlerTaskConfig(BaseModel):
    """爬虫任务配置"""
    task_id: str
    site_id: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    site_url: List[str]
    login_config: Optional[LoginConfig] = None
    extract_rules: List[ExtractRule] = Field(default_factory=list)
    custom_config: Optional[Dict[str, Any]] = None