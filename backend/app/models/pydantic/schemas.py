from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Dict, Any, Optional, List, Union
from enum import Enum

class SelectorType(str, Enum):
    CSS = "css"
    XPATH = "xpath"
    TEXT = "text"
    REGEX = "regex"

class Selector(BaseModel):
    type: SelectorType = Field(default=SelectorType.CSS)
    value: str
    attribute: Optional[str] = None  # 例如 "href", "src" 等
    multiple: bool = False  # 是否提取多个结果
    optional: bool = False  # 是否允许不存在
    regex: Optional[str] = None  # 用于进一步处理提取的文本

class NavigationRule(BaseModel):
    selector: Selector
    max_depth: Optional[int] = None
    follow_same_domain: bool = True
    patterns: Optional[List[str]] = None  # URL 匹配模式

class PageRule(BaseModel):
    url_pattern: str
    selectors: Dict[str, Selector]
    navigation: Optional[NavigationRule] = None
    wait_for: Optional[str] = None  # 等待某个元素出现
    scripts: Optional[List[str]] = None  # 注入的脚本

class LoginConfig(BaseModel):
    url: HttpUrl
    username_selector: str
    password_selector: str
    submit_selector: str
    success_check: str  # 登录成功的检查选择器
    username: str
    password: str

class CrawlerConfig(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    start_urls: List[HttpUrl]
    page_rules: Dict[str, PageRule]
    login: Optional[LoginConfig] = None
    
    # 爬虫行为配置
    max_concurrent_requests: int = Field(default=2, ge=1, le=10)
    request_delay: int = Field(default=1000, ge=0)  # 毫秒
    max_retries: int = Field(default=3, ge=0)
    timeout: int = Field(default=30000, ge=1000)  # 毫秒
    
    # 浏览器配置
    viewport: Dict[str, int] = Field(
        default={"width": 1280, "height": 720}
    )
    user_agent: Optional[str] = None
    
    # 高级配置
    headers: Optional[Dict[str, str]] = None
    cookies: Optional[Dict[str, str]] = None
    proxy: Optional[str] = None
    
    @validator('page_rules')
    def validate_page_rules(cls, v):
        if not v:
            raise ValueError("At least one page rule is required")
        return v

class ConfigTemplate(BaseModel):
    id: str
    name: str
    description: str
    config: CrawlerConfig
    category: str
    tags: List[str] = [] 