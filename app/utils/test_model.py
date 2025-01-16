from typing import Optional, List, Dict, Union, Any
from pydantic import BaseModel, Field

class SelectorConfig(BaseModel):
    """选择器配置模型"""
    selector: Union[str, List[str]] = Field(
        description="选择器字符串或选择器列表，支持多个备选选择器"
    )
    location: Optional[str] = Field(
        default=None,
        description="父元素的选择器"
    )
    index: Optional[int] = Field(
        default=None,
        description="获取第n个元素"
    )
    relative_location: Optional[str] = Field(
        default=None,
        description="相对位置，支持 next, prev, parent, child, before, after"
    )
    filters: List[tuple] = Field(
        default_factory=list,
        description="过滤器列表，如[('filter_one', (2,)), ('filter', ('visible',))]"
    )
    attribute: Optional[str] = Field(
        default=None,
        description="要获取的属性名"
    )
    pattern: Optional[str] = Field(
        default=None,
        description="正则匹配模式"
    )
    value_type: Optional[str] = Field(
        default=None,
        description="值类型：text, html, inner_html, outer_html, bool"
    )
    actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="元素操作动作列表"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "selector": ["@class$User_Name", "@href$userdetails.php"],
                "attribute": "href",
                "pattern": r"(\d+)"
            }
        }
        
class PageConfig(BaseModel):
    """页面配置模型"""
    page: str = Field(description="页面路径")
    fields: Dict[str, SelectorConfig] = Field(
        description="字段选择器配置"
    )
    params: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="页面请求参数"
    )
    response_type: Optional[str] = Field(
        default="html",
        description="响应类型：html 或 json"
    )
    data_path: Optional[str] = Field(
        default=None,
        description="JSON响应数据路径"
    )
    table_selector: Optional[str] = Field(
        default=None,
        description="表格选择器"
    )
    row_selector: Optional[str] = Field(
        default=None,
        description="行选择器"
    )
    enable_pagination: Optional[bool] = Field(
        default=True,
        description="是否启用分页"
    )
    
class SiteParserConfig(BaseModel):
    """站点解析配置模型"""
    site_url: str = Field(description="站点URL")
    user_base_info: PageConfig = Field(
        description="用户基础信息配置"
    )
    user_extend_info: PageConfig = Field(
        description="用户扩展信息配置"
    )
    user_bonus_extend_info: Optional[PageConfig] = Field(
        default=None,
        description="用户魔力值信息配置"
    )
    seeding_info: PageConfig = Field(
        description="做种信息配置"
    )
    checkin_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="签到配置"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "site_url": "https://example.org",
                "user_base_info": {
                    "page": "/index.php",
                    "fields": {
                        "id": {
                            "selector": ["@href$userdetails.php", "@class$User_Name"],
                            "attribute": "href",
                            "pattern": r"(\d+)"
                        }
                    }
                }
            }
        }