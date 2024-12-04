from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class WebElement(BaseModel):
    """元素选择器配置"""
    name: str
    selector: str
    type: Optional[Literal["text", "attribute", "html", "src", "password", "checkbox", "by_day"]] = "text"
    location: Optional[str] = None
    second_selector: Optional[str] = None
    required: Optional[bool] = False
    attribute: Optional[str] = None
    ele_only: Optional[bool] = True
    need_pre_action: Optional[bool] = False
    index: Optional[int] = None
    url_pattern: Optional[str] = None  # 用于验证码背景图片URL提取
    page_url: Optional[str] = None  # 需要访问的页面URL
    pre_action_type: Optional[str] = None  # 预处理类型
    expect_text: Optional[str] = None  # 预期文本

class CaptchaConfig(BaseModel):
    """验证码配置"""
    type: Optional[str] = 'custom'
    element: WebElement
    input: WebElement
    hash: Optional[WebElement] = None

class LoginConfig(BaseModel):
    """登录配置"""
    login_url: str
    form_selector: str
    pre_login: Optional[Dict[str, Any]] = None
    fields: Dict[str, WebElement]
    captcha: Optional[CaptchaConfig] = None
    success_check: WebElement

class ExtractRuleSet(BaseModel):
    """数据提取规则"""
    rules: List[WebElement]

class CheckInResultConfig(BaseModel):
    """签到结果检查配置"""
    element: Optional[WebElement] = None  # 结果容器选择器
    sign: Optional[Dict[str, str]] = None

class CheckInConfig(BaseModel):
    """签到配置"""
    checkin_url: Optional[str] = None  # 直接访问的签到URL
    checkin_button: Optional[WebElement] = None  # 签到按钮配置
    success_check: Optional[CheckInResultConfig] = None  # 签到结果检查配置（必需）

class SiteCredential(BaseModel):
    """站点凭证配置"""
    username: str
    password: str
    enabled: bool = True
    description: Optional[str] = None

class CrawlerTaskConfig(BaseModel):
    """爬虫任务配置"""
    task_id: str
    site_id: Optional[str] = None
    site_url: List[str]
    credentials: Optional[SiteCredential] = None  # 添加站点特定的凭证
    login_config: Optional[LoginConfig] = None
    extract_rules: Optional[ExtractRuleSet] = None
    checkin_config: Optional[CheckInConfig] = None
    custom_config: Optional[Dict[str, Any]] = None
