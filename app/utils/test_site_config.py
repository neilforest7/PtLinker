import asyncio
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv
from pydantic import BaseModel

# 添加项目根目录到系统路径
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
env_path = project_root / '.env'
load_dotenv(env_path)

from utils.clouodflare_bypasser import CloudflareBypasser
from core.logger import get_logger
from DrissionPage import Chromium, ChromiumOptions, SessionPage
from handlers.checkin import CheckInHandler
from handlers.login import LoginHandler
from schemas.crawlerconfig import CrawlerConfigBase
from schemas.crawlercredential import CrawlerCredentialBase
from schemas.settings import SettingsBase
from schemas.siteconfig import ExtractRuleSet, WebElement
from schemas.sitesetup import SiteSetup
from services.managers.setting_manager import SettingManager

logger = get_logger(__name__)
class SiteConfigTestBase(BaseModel):
    site_id: str
    site_url: str
    login_config: Optional[dict] = None
    
class SiteSetupTest(BaseModel):
    site_id: str
    site_config: SiteConfigTestBase
    crawler_config: CrawlerConfigBase
    crawler_credential: CrawlerCredentialBase
    settings: SettingsBase
    
# 选择器配置
class SelectorConfig:
    """选择器配置，支持DrissionPage的高级特性"""
    def __init__(self, 
                selector: Union[str, List[str]],  # 支持多个选择器
                location: Optional[str] = None,    # 父元素的selector
                index: Optional[int] = None,       # 获取第n个元素
                relative_location: Optional[str] = None, # 相对位置，如next, prev, parent, child, before, after
                filters: Optional[List[tuple]] = None,  # 过滤器列表，如[('filter_one', (2,)), ('filter', ('visible',))]
                attribute: Optional[str] = None,   # 要获取的属性
                pattern: Optional[str] = None,     # 正则匹配模式
                value_type: Optional[str] = None,  # text, html, inner_html, outer_html
                actions: Optional[List[Dict]] = None,  # 元素操作动作列表
                ):
        self.selector = selector
        self.location = location
        self.index = index
        self.relative_location = relative_location
        self.filters = filters or []
        self.attribute = attribute
        self.pattern = pattern
        self.value_type = value_type
        self.actions = actions or []

    @classmethod
    def from_dict(cls, data: dict) -> 'SelectorConfig':
        """从字典创建选择器配置"""
        return cls(**data)

# 页面配置
class PageConfig:
    """页面配置"""
    def __init__(self, url: str, selectors: Dict[str, SelectorConfig],
                pre_actions: Optional[List[Dict]] = None):
        self.url = url
        self.selectors = selectors
        self.pre_actions = pre_actions or []  # 页面预处理动作

# 站点配置
class SiteParserConfig:
    """站点解析配置，参考MoviePilot结构"""
    def __init__(self, site_url: str, site_id: str):
        self.site_url = site_url
        self.site_id = site_id
        self._init_default_configs()
        
    def _init_default_configs(self):
        """初始化默认配置"""
        # 1. 用户基础信息配置
        self.user_base_info = {
            "page": "/index.php",
            "fields": {
                "id": SelectorConfig(
                    selector=["@@href:userdetails.php@@class$User_Name",
                            "@href:userdetials.php",
                            "a[href*='userdetails.php'][class*='Name']:first", 
                            "a[href*='userdetails.php']:first"],
                    attribute="href",
                    pattern=r"(\d+)"
                ),
                "name": SelectorConfig(
                    selector=[
                        "@class$User_Name",
                        "@href$userdetails.php",
                        "a[href*='userdetails.php'][class*='Name']:first", 
                        "a[href*='userdetails.php']:first"],
                    value_type="text"
                ),
                "is_logged": SelectorConfig(
                    selector=["@href$usercp.php",
                            "@text:控制面板"],
                    value_type="bool"
                )
            }
        }
        
        # 2. 用户详细信息配置
        self.user_extend_info = {
            "page": "/userdetails.php",
            "fields": {
                "uploaded": SelectorConfig(
                    selector=["tag:table@@text():上传量",
                            "tag:table@@text():上傳量",
                            "tag:table@@text():uploaded",
                            "tag:table@@text():Uploaded"],
                    pattern=r"(上[传傳]量|uploaded|Uploaded)[：:]?\s*(\d+(\.\d+)?\s*[ZEPTGMKk]?i?B)"
                ),
                "downloaded": SelectorConfig(
                    selector="tag:table@@text():下载量",
                    pattern=r"(下[载載]量|downloaded|Downloaded)[：:]?.+?([\d.]+ ?[ZEPTGMK]?i?B)"
                ),
                "ratio": SelectorConfig(
                    selector="tag:table@@text():分享率",
                    pattern=r"(分享率|Ratio)[：:]?\s*([\d.]+)"
                ),
                "bonus": SelectorConfig(
                    selector=["tag:table@@text():魔力值",
                                "tag:table@@text():爆米花",
                                "tag:table@@text():憨豆"],
                    pattern=r"(?:魔力值|Bonus Points|爆米花|憨豆)[：:]?.*?[：:]?\s*([\d,]+\.\d+)"
                ),
                "seeding_score": SelectorConfig(
                    selector="tag:table@@text():做种积分",
                    pattern=r"(?:做种积分|做種積分|Seeding Points)[：:]?.*?[：:]?\s*([\d,.]+)"
                ),
                "join_time": SelectorConfig(
                    selector="@text():加入日期",
                    relative_location="next",
                    pattern=r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})"
                ),
                "last_active": SelectorConfig(
                    selector="@text():最近动向",
                    relative_location="next",
                    pattern=r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})"
                ),
                "user_class": SelectorConfig(
                    selector="@@tag()=img@@alt$User",
                    attribute="alt",
                )
            }
        }
        
        # 3. 魔力值信息配置
        self.user_bonus_extend_info = {
            "page": "/mybonus.php",
            "fields": {
                "bonus_per_hour": SelectorConfig(
                    selector="@text():你当前每小时能获取",
                    pattern=r"([\d.]+)"
                )
            }
        }
        
        # 4. 做种信息配置
        self.seeding_info = {
            "page": "/getusertorrentlistajax.php",
            "params": {
                "type": "seeding",
                "userid": "{userid}",
                "page": 0
            },
            "response_type": "html",
            "table_selector": "tag:table",
            "row_selector": "tag:tr",
            "pagination_selector": "@class=nexus-pagination",
            "fields": {
                "size": SelectorConfig(
                    selector="tag:td",
                    index=4,
                    pattern=r"([\d.]+[\s\n]*[KMGTPE]?i?B)",
                    value_type="text"
                ),
                "name": SelectorConfig(
                    selector="t:td:nth-child(2) > a",
                    attribute="title"
                ),
                "uploaded": SelectorConfig(
                    selector="t:td:nth-child(7)",
                    pattern=r"([\d.]+ ?[ZEPTGMK]?i?B)"
                ),
                "downloaded": SelectorConfig(
                    selector="t:td:nth-child(8)",
                    pattern=r"([\d.]+ ?[ZEPTGMK]?i?B)"
                ),
                "ratio": SelectorConfig(
                    selector="t:td:nth-child(9)",
                    pattern=r"([\d.]+|---)"
                ),
                "seeding_time": SelectorConfig(
                    selector="t:td:nth-child(10)",
                    pattern=r"(\d+天\d+:\d+:\d+)"
                )
            }
        }
        
        # 5. 签到配置
        self.checkin_config = {
            "page": "/attendance.php",
            "button": SelectorConfig(
                selector=[
                    "@href$attendance.php",
                    "input[type='submit']"
                ]
            ),
            "success_pattern": r"已签到|签到成功|success"
        }

    def merge_config(self, config_path: str):
        """从文件合并配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                site_config = json.load(f)
                
            # 递归合并配置
            self._merge_dict_config(site_config)
            logger.info(f"成功合并配置文件: {config_path}")
            
        except Exception as e:
            logger.error(f"合并配置失败: {str(e)}")
            
    def _merge_dict_config(self, new_config: dict):
        """递归合并字典配置"""
        for key, value in new_config.items():
            if not hasattr(self, key):
                logger.warning(f"未知的配置项: {key}")
                continue
                
            current_value = getattr(self, key)
            
            if isinstance(value, dict) and isinstance(current_value, dict):
                # 递归合并字典
                self._merge_dict_values(current_value, value)
            else:
                # 直接覆盖非字典值
                setattr(self, key, value)
                logger.debug(f"更新配置项: {key} = {value}")
                
    def _merge_dict_values(self, current_dict: dict, new_dict: dict):
        """递归合并字典值"""
        for key, value in new_dict.items():
            if key in current_dict:
                if isinstance(value, dict) and isinstance(current_dict[key], dict):
                    # 递归合并嵌套字典
                    self._merge_dict_values(current_dict[key], value)
                    logger.debug(f"合并嵌套配置: {key}")
                elif isinstance(value, dict) and isinstance(current_dict[key], SelectorConfig):
                    # 处理SelectorConfig的情况
                    current_dict[key] = SelectorConfig(**{
                        **current_dict[key].__dict__,
                        **value
                    })
                    logger.debug(f"更新选择器配置: {key}")
                else:
                    # 直接覆盖非字典值（包括URL）
                    current_dict[key] = value
                    logger.debug(f"覆盖配置值: {key} = {value}")
            else:
                # 添加新键值对
                if isinstance(value, dict) and 'selector' in value:
                    # 如果是选择器配置，创建SelectorConfig实例
                    current_dict[key] = SelectorConfig(**value)
                    logger.debug(f"添加新选择器配置: {key}")
                else:
                    current_dict[key] = value
                    logger.debug(f"添加新配置项: {key} = {value}")

    def get_page_url(self, page_type: str) -> str:
        """获取完整页面URL，优先使用站点特定配置"""
        config = getattr(self, f"{page_type}_info", None)
        if not config:
            raise ValueError(f"未知的页面类型: {page_type}")
            
        # 获取页面路径，优先使用配置中的值
        page_path = config.get('page')
        if not page_path:
            raise ValueError(f"未找到页面路径配置: {page_type}")
            
        # 如果是完整URL，直接返回
        if page_path.startswith(('http://', 'https://')):
            return page_path
            
        # 否则拼接站点URL
        return urljoin(self.site_url, page_path)

    def get_field_selectors(self, page_type: str) -> Dict[str, SelectorConfig]:
        """获取指定页面的字段选择器"""
        config = getattr(self, f"{page_type}_info", None)
        if not config:
            raise ValueError(f"未知的页面类型: {page_type}")
        return config.get('fields', {})

class DrissionPageParser:
    """DrissionPage页面解析器"""
    def __init__(self, tab: Chromium):
        self.tab = tab
        self.logger = get_logger(__name__)

    def get_element_value(self, selector_config: SelectorConfig) -> Any:
        """获取元素值"""
        # 处理多选择器情况
        self.logger.trace(f"开始获取元素值: {selector_config.selector}")
        if isinstance(selector_config.selector, list):
            self.logger.trace(f"多选择器: {selector_config.selector}")
            for selector in selector_config.selector:
                self.logger.trace(f"尝试选择器: {selector}")
                value = self._try_selector(selector, selector_config)
                if value is not None:
                    self.logger.success(f"获取到元素值: {value}")
                    return value
            self.logger.error(f"未获取到元素值")
            return None
        else:
            self.logger.trace(f"单选择器: {selector_config.selector}")
            value = self._try_selector(selector_config.selector, selector_config)
            if value is not None:
                self.logger.success(f"获取到元素值: {value}")
                return value
            self.logger.error(f"未获取到元素值")
            return None

    def _try_selector(self, selector: str, config: SelectorConfig) -> Any:
        """尝试单个选择器"""
        try:
            self.logger.trace(f"开始尝试选择器:{config.__dict__} 中的 {selector}")
            
            # 1. 处理基本选择器和父元素
            base_element = None
            if config.location:
                self.logger.trace(f"尝试获取父元素，选择器: {config.location}")
                if isinstance(config.location, str):
                    base_element = self.tab.ele(config.location)
                else:
                    base_element = config.location
                if not base_element:
                    self.logger.error(f"未找到父元素: {config.location}")
                    return None
                # self.logger.trace(f"成功获取父元素: {base_element}")
            else:
                self.logger.trace("使用tab作为基础元素")
                base_element = self.tab
            
            # 2. 处理索引及获取元素
            self.logger.trace(f"开始在基础元素下查找: {selector}")
            if hasattr(config, 'index') and config.index is not None:
                self.logger.trace(f"使用索引 {config.index} 查找元素")
                element = base_element.ele(selector, index=config.index)
            else:
                self.logger.trace("查找第一个匹配元素")
                element = base_element.ele(selector)
            
            if not element:
                self.logger.error(f"未找到匹配元素: {selector}")
                return None
            # self.logger.trace(f"成功找到元素: {element}")
            
            # 3. 处理过滤器
            if hasattr(config, 'filters') and config.filters:
                self.logger.trace(f"开始应用过滤器: {config.filters}")
                for filter_rule in config.filters:
                    if isinstance(filter_rule, tuple):
                        method, args = filter_rule
                        self.logger.trace(f"应用过滤器: {method}, 参数: {args}")
                        if method == 'filter_one':
                            element = element.filter_one.text(*args)
                        elif method == 'filter':
                            element = element.filter.attr(*args)
                        if not element:
                            self.logger.error(f"过滤后未找到元素")
                            return None
                        self.logger.trace(f"过滤后的元素: {element}")
                        
            # 4. 处理元素相对位置
            if config.relative_location:
                self.logger.trace(f"开始处理相对位置: {config.relative_location}")
                original_element = element
                if config.relative_location == 'next':
                    element = element.next()
                    self.logger.trace(f"获取下一个元素: {element}")
                elif config.relative_location == 'prev':
                    element = element.prev()
                    self.logger.trace(f"获取上一个元素: {element}")
                elif config.relative_location == 'parent':
                    element = element.parent()
                    self.logger.trace(f"获取父元素: {element}")
                elif config.relative_location == 'child':
                    element = element.child()
                    self.logger.trace(f"获取子元素: {element}")
                elif config.relative_location == 'before':
                    element = element.before()
                    self.logger.trace(f"获取前一个元素: {element}")
                elif config.relative_location == 'after':
                    element = element.after()
                    self.logger.trace(f"获取后一个元素: {element}")
                    
                if not element:
                    self.logger.error(f"未找到相对位置元素: {config.relative_location}, 原始元素: {original_element}")
                    return None
                # self.logger.trace(f"成功获取相对位置元素: {element}")
                    
            # 5. 获取元素值
            self.logger.trace(f"开始获取元素值: {element}")
            value = self._get_value(element, config)
            if not value:
                self.logger.error("获取元素值失败")
                return None
            # self.logger.trace(f"获取到原始值: {value}")

            # 6. 应用正则模式
            if config.pattern:
                # self.logger.trace(f"应用正则模式: {config.pattern}")
                match = re.search(config.pattern, value)
                if match:
                    value = match.group(0)
                    self.logger.trace(f"正则匹配结果: {value}")
                else:
                    self.logger.error(f"正则匹配失败: {value} 不匹配 {config.pattern}")
                    return None

            self.logger.success(f"选择器 {selector} 提取到最终值: {value}")
            return value

        except Exception as e:
            self.logger.error(f"选择器 {selector} 提取失败: {str(e)}", exc_info=True)
            return None
        
    def _get_value(self, element, config: SelectorConfig) -> str:
        """获取元素值"""
        try:
            if hasattr(config, 'attribute') and config.attribute:
                return element.attr(config.attribute) or ""
            elif hasattr(config, 'value_type'):
                if config.value_type == 'text':
                    return element.text.strip()
                elif config.value_type == 'html':
                    return element.html
                elif config.value_type == 'inner_html':
                    return element.inner_html
                elif config.value_type == 'outer_html':
                    return element.outer_html
                elif config.value_type == 'bool':
                    return element.text != ""
            return element.text.strip()
        except Exception as e:
            self.logger.debug(f"获取元素值失败: {str(e)}")
            return ""

class DataExtractor:
    """数据提取器"""
    def __init__(self, site_config: SiteParserConfig):
        self.config = site_config
        self.logger = get_logger(__name__)
        # 新增请求控制相关属性
        self._request_times = []  # 记录最近的请求时间
        self._retry_count = 0     # 当前重试次数
        
        # 根据站点ID设置不同的延迟策略
        if site_config.site_id in ['audi']:  # 需要更保守延迟的站点
            self._base_delay = (5500, 6000)  # 基础延迟范围改为1.5-2秒
            self._max_requests = 25          # 降低窗口内最大请求数
        else:
            self._base_delay = (350, 450)    # 保持原有的延迟范围
            self._max_requests = 30          # 保持原有的最大请求数
            
        self._max_delay = 30000   # 最大延迟时间(ms)
        self._window_size = 10    # 时间窗口大小(s)
        self._ban_time = 10000    # 封禁时间(ms)
        
        # 添加限流和验证页面的识别特征
        self._rate_limit_patterns = [
            "请求过于频繁",  # 常见中文提示
            "Rate limit exceeded",  # 常见英文提示
            "访问频率超限",
            "请稍后再试",
            "Too Many Requests",  # HTTP 429 相关提示
            "Please slow down",
        ]
        
        self._cloudflare_patterns = [
            "Turnstile",
            "Security check required",  # Cloudflare 安全检查页面特征
            "cf-turnstile",  # Turnstile 元素特征
            "Just a moment",  # Cloudflare 常见提示
            "Checking your browser",  # Cloudflare 检查提示
        ]
        
        # 添加请求超时阈值（毫秒）
        self._request_timeout = 3000  # 5秒

    async def extract_all(self, tab: Chromium, user_id: str) -> Dict[str, Any]:
        """提取所有数据"""
        data = {}
        
        # 1. 提取基础信息
        self.logger.info("开始提取用户基础信息...")
        base_info = await self.extract_page_info(tab, 'user_base', user_id)
        data.update(base_info)
        
        # 2. 提取扩展信息
        self.logger.info("开始提取用户扩展信息...")
        extend_info = await self.extract_page_info(tab, 'user_extend', user_id)
        data.update(extend_info)
        
        # 3. 提取魔力值信息
        self.logger.info("开始提取魔力值信息...")
        bonus_info = await self.extract_page_info(tab, 'user_bonus_extend', user_id)
        data.update(bonus_info)
        
        # 4. 提取做种信息
        self.logger.info("开始提取做种信息...")
        seeding_info = await self.extract_seeding_info(tab, user_id)
        data.update(seeding_info)
        
        return data

    async def extract_page_info(self, tab: Chromium, page_type: str, user_id: str) -> Dict[str, Any]:
        """提取指定页面的信息"""
        data = {}
        try:
            # 获取页面URL
            page_url = self.config.get_page_url(page_type)
            if user_id:
                page_url = f"{page_url}?id={user_id}"
            
            # 访问页面
            self.logger.info(f"访问页面: {page_url}")
            tab.get(page_url)
            
            # 获取选择器并提取数据
            parser = DrissionPageParser(tab)
            selectors = self.config.get_field_selectors(page_type)
            
            for field, selector_config in selectors.items():
                value = parser.get_element_value(selector_config)
                if value:
                    data[field] = value
                    self.logger.info(f"提取到 {field}: {value}")
                    
        except Exception as e:
            self.logger.error(f"提取{page_type}页面信息失败: {str(e)}")
            
        return data

    async def extract_seeding_info(self, tab: Chromium, user_id: str) -> Dict[str, Any]:
        """提取做种信息"""
        try:
            # 切换到s模式
            # tab.change_mode('s')
            
            # 构建请求
            page_url = self.config.get_page_url('seeding')
            self.logger.warning(f"page_url: {page_url}")
            base_params = {**self.config.seeding_info['params'], 'userid': user_id}
            self.logger.warning(f"base_params: {base_params}")
            
            total_result = {
                'seeding_count': 0,
                'seeding_size': 0
            }
            
            # 检查是否启用翻页
            enable_pagination = self.config.seeding_info.get('enable_pagination', True)
            if not enable_pagination:
                # 如果禁用翻页，只请求第一页
                page_result = await self._request_page(tab, page_url, base_params)
                if page_result:
                    total_result.update(page_result)
            else:
                # 启用翻页的情况
                page = 0
                last_page_size = None  # 记录上一页的总大小
                
                while True:
                    # 添加页码参数
                    params = {**base_params, 'page': page}
                    page_result = await self._request_page(tab, page_url, params)
                    
                    if not page_result:
                        break
                        
                    current_page_size = page_result.get('seeding_size', 0)
                    
                    # 如果当前页的总大小与上一页相同，说明可能是重复数据
                    if last_page_size is not None and abs(current_page_size - last_page_size) < 0.01:  # 允许0.01GB的误差
                        self.logger.warning(f"检测到重复数据，当前页: {page}, 数据大小: {current_page_size:.2f} GB")
                        break
                        
                    total_result['seeding_count'] += page_result.get('seeding_count', 0)
                    total_result['seeding_size'] += current_page_size
                    
                    last_page_size = current_page_size
                    page += 1
            
            self.logger.info(f"总计: {total_result['seeding_count']} 个种子，{total_result['seeding_size']:.2f} GB")
            return total_result
                
        except Exception as e:
            self.logger.error(f"提取做种信息失败: {str(e)}")
            return {
                'seeding_count': 0,
                'seeding_size': 0
            }

    async def _request_page(self, tab: Chromium, page_url: str, params: dict) -> Optional[Dict[str, Any]]:
        """请求单页数据"""
        try:
            self.logger.info(f"请求做种数据: {page_url}, params: {params}")
            
            # 等待请求控制
            await self._wait_for_request()
            
            # 记录本次请求时间
            request_start_time = time.time()
            self._request_times.append(request_start_time)
            
            params_str = "&".join([f"{k}={v}" for k, v in params.items()])
            page_url = f"{page_url}?{params_str}"
            
            # 发送请求
            response = tab.get(page_url)
            request_duration = (time.time() - request_start_time) * 1000  # 转换为毫秒
            self.logger.debug(f"响应状态: {response}, URL: {tab.url}, 耗时: {request_duration:.2f}ms")
            
            # 只有当请求时间超过阈值时才进行检查
            if request_duration > self._request_timeout:
                self.logger.warning(f"请求耗时 {request_duration:.2f}ms 超过阈值 {self._request_timeout}ms，进行安全检查")
                
                # 检查是否遇到限流
                if await self._is_rate_limited(tab):
                    self._retry_count += 1
                    self.logger.warning("检测到限流响应")
                    return None
                    
                # 检查是否遇到Cloudflare验证
                if await self._is_cloudflare_present(tab):
                    self.logger.warning("检测到Cloudflare验证页面")
                    if not await self._handle_cloudflare(tab):
                        self.logger.error("Cloudflare验证失败")
                        return None
            
            if not response:
                self._retry_count += 1
                self.logger.error(f"请求失败: {response}")
                self.logger.error(f"请求失败: {tab.url}")
                return None
                
            # 请求成功，重置重试计数
            self._retry_count = 0
            
            # 处理响应
            response_type = self.config.seeding_info.get('response_type', 'html')
            if response_type == 'json':
                try:
                    return await self._process_json_response(tab)
                except json.JSONDecodeError:
                    self.logger.warning("JSON解析失败，尝试作为HTML处理")
                    return await self._process_html_response(tab)
            else:
                return await self._process_html_response(tab)
                
        except Exception as e:
            self._retry_count += 1
            self.logger.error(f"请求页面失败: {str(e)}")
            return None

    async def _process_json_response(self, tab) -> Dict[str, Any]:
        """处理JSON响应"""
        try:
            data = tab.json
            result = {}
            
            # 获取数据路径
            data_path = self.config.seeding_info.get('data_path')
            if data_path:
                data = data.get(data_path, [])
            
            if isinstance(data, list):
                total_size = 0
                for item in data:
                    # 使用配置的字段映射获取数据
                    field_mappings = self.config.seeding_info['fields']
                    for our_field, their_field in field_mappings.items():
                        if their_field in item:
                            if our_field == 'size':
                                total_size += await _convert_size_to_gb(item[their_field])
                
                result.update({
                    'seeding_count': len(data),
                    'seeding_size': total_size
                })
                
            return result
            
        except Exception as e:
            self.logger.error(f"处理JSON响应失败: {str(e)}")
            return {}

    async def _process_html_response(self, tab) -> Dict[str, Any]:
        """处理HTML响应"""
        try:
            result = {
                'seeding_count': 0,
                'seeding_size': 0
            }
            
            parser = DrissionPageParser(tab)

            # 1. 获取表格元素
            table_element = tab.ele(self.config.seeding_info['table_selector'])
            if not table_element:
                self.logger.error("未找到种子列表表格")
                return result
            
            # 2. 获取所有行
            rows = table_element.eles(self.config.seeding_info['row_selector'])
            if not rows or len(rows) <= 1:  # 如果只有表头或没有行
                self.logger.info("未找到种子数据行")
                return result
            
            # 3. 处理每一行数据（跳过第一行表头）
            total_size = 0
            for row in rows[1:]:  # 从第二行开始
                try:
                    # 提取大小信息
                    size_config = self.config.seeding_info['fields']['size']
                    size_config.location = row  # 在当前行内查找
                    self.logger.trace(f"种子数据行: {row}")
                    size_text = parser.get_element_value(size_config)
                    self.logger.trace(f"提取到大小: {size_text}")
                    if size_text:
                        total_size += await _convert_size_to_gb(size_text)
                        
                    self.logger.info(f"转换到大小: {size_text}")
                except Exception as e:
                    self.logger.debug(f"处理行数据失败: {str(e)}")
                    continue
            
            # 4. 更新结果（减去表头行）
            result['seeding_count'] = len(rows) - 1  # 总行数减去表头
            result['seeding_size'] = total_size
            
            # 5. 检查分页信息
            # pagination_text = parser.get_element_value(self.config.seeding_info['fields']['pagination'])
            # if pagination_text:
            #     self.logger.info(f"当前页面显示: {pagination_text}")
            #     pass
            
            return result
            
        except Exception as e:
            self.logger.error(f"处理HTML响应失败: {str(e)}")
            return {
                'seeding_count': 0,
                'seeding_size': 0
            }

    async def _wait_for_request(self) -> None:
        """控制请求频率"""
        try:
            # 清理过期的请求记录
            current_time = time.time()
            self._request_times = [t for t in self._request_times 
                                    if current_time - t < self._window_size]
            
            # 检查是否接近限制
            if len(self._request_times) >= self._max_requests - 5:  # 预留安全边界
                self.logger.warning("接近请求限制，增加延迟")
                await asyncio.sleep(self._window_size / 2)  # 等待半个窗口时间
                return
            
            # 计算基础延迟
            delay = random.uniform(self._base_delay[0], self._base_delay[1]) / 1000
            
            # 如果有重试记录，使用指数退避
            if self._retry_count > 0:
                delay = min(self._ban_time * (2 ** (self._retry_count - 1)) / 1000, 
                            self._max_delay / 1000)
                self.logger.warning(f"第 {self._retry_count} 次重试，等待 {delay:.2f} 秒")
            
            await asyncio.sleep(delay)
            
        except Exception as e:
            self.logger.error(f"请求控制出错: {str(e)}")
            await asyncio.sleep(1)  # 发生错误时使用保守延迟
            
    async def _is_cloudflare_present(self, tab) -> bool:
        """检查是否存在Cloudflare验证页面"""
        try:
            if tab.title == "Just a moment...":
                return True

            # 检查是否存在 Cloudflare 的 JavaScript 或 Turnstile 验证相关的关键元素
            if tab.ele('script[src*="challenge-platform"]') or tab.ele('@div#challenge-error-text'):
                return True

            # 检查页面文本中是否包含 Cloudflare 验证相关提示
            body_text = tab.text
            if "Checking your browser before accessing" in body_text or "Verify you are human" in body_text:
                return True
            return False

        except Exception as e:
            self.logger.error("检查Cloudflare状态时出错", exc_info=True)
            return False

    async def _handle_cloudflare(self, tab) -> bool:
        """处理Cloudflare验证"""
        try:
            # Where the bypass starts
            self.logger.info('Starting Cloudflare bypass.')
            cf_bypasser = CloudflareBypasser(tab)
            # If you are solving an in-page captcha (like the one here: https://seleniumbase.io/apps/turnstile), use cf_bypasser.click_verification_button() directly instead of cf_bypasser.bypass().
            # It will automatically locate the button and click it. Do your own check if needed.

            cf_bypasser.bypass()

            # 检查是否需要处理Cloudflare验证
            self.logger.info("等待Cloudflare验证完成...")
            # sleep(160)
            tab.wait.load_start()
            if not await self._is_cloudflare_present(tab):
                self.logger.success("Cloudflare验证已完成")
                return True
            else:
                self.logger.error("Cloudflare验证超时")
                return False

        except Exception as e:
            self.logger.error("Cloudflare验证处理出错", exc_info=True)
            return False


    async def _is_rate_limited(self, tab: Chromium) -> bool:
        """检查是否遇到限流"""
        try:
            # 检查HTTP状态码
            # if tab.status_code == 429:
            #     return True
                
            # 检查页面内容是否包含限流特征
            page_text = tab.html
            for pattern in self._rate_limit_patterns:
                if pattern.lower() in page_text.lower():
                    return True
                    
            return False
        except Exception as e:
            self.logger.error(f"检查限流状态失败: {str(e)}")
            return False
        
def parse_cookies(cookies_str: str, domain: str) -> list:
    """解析cookies字符串为列表格式"""
    try:
        # 如果是JSON格式
        if cookies_str.strip().startswith('[') or cookies_str.strip().startswith('{'):
            cookies_data = json.loads(cookies_str)
            if isinstance(cookies_data, dict):
                cookies_data = [cookies_data]
        else:
            # 如果是Netscape格式或简单的name=value格式
            cookies_data = []
            for line in cookies_str.split(';'):
                if '=' in line:
                    name, value = line.strip().split('=', 1)
                    cookies_data.append({'name': name.strip(), 'value': value.strip()})
        
        # 确保每个cookie都有domain字段
        for cookie in cookies_data:
            if 'domain' not in cookie:
                cookie['domain'] = domain
        
        return cookies_data
    except Exception as e:
        logger.error(f"解析cookies失败: {str(e)}")
        return []

async def _convert_size_to_gb(size_str: str) -> float:
    """将字符串形式的大小转换为GB为单位的浮点数"""
    try:
        # 如果输入已经是数字，直接返回
        logger.info(f"输入大小: {size_str}")
        if isinstance(size_str, (int, float)):
            return float(size_str)
            
        # 移除多余空格并转换为大写以统一处理
        size_str = str(size_str).strip().upper()
        
        # 使用正则表达式匹配数字和单位
        size_match = re.search(r'([\d.]+)\s*([TGMK]B|B)?', size_str, re.IGNORECASE)
        if not size_match:
            logger.warning(f"无法解析的数据量格式: {size_str}")
            return 0.0
        
        size_num = float(size_match.group(1))
        # 如果没有匹配到单位，默认为GB
        size_unit = size_match.group(2) if size_match.group(2) else 'GB'
        
        # 统一单位格式
        size_unit = size_unit.upper()
        
        # 转换为GB
        if 'TB' in size_unit or 'TIB' in size_unit:
            return size_num * 1024
        elif 'GB' in size_unit or 'GIB' in size_unit:
            return size_num
        elif 'MB' in size_unit or 'MIB' in size_unit:
            return size_num / 1024
        elif 'KB' in size_unit or 'KIB' in size_unit:
            return size_num / (1024 * 1024)
        elif size_unit == 'B':  # 只处理单独的B
            return size_num / (1024 * 1024 * 1024)
        else:
            return size_num  # 未知单位默认为GB
        
    except Exception as e:
        logger.error(f"转换数据量失败: {size_str}, 错误: {str(e)}")
        return 0.0

async def _clean_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """清洗爬取的数据"""
    cleaned_data = {}
    
    try:
        # 用户名保持不变
        if 'username' in data:
            cleaned_data['username'] = data.get('username')
        if 'user_id' in data:
            cleaned_data['user_id'] = data.get('user_id')
        if 'user_class' in data:
            cleaned_data['user_class'] = data.get('user_class')
        if 'uid' in data:
            cleaned_data['uid'] = data.get('uid')
        if 'id' in data:
            cleaned_data['user_id'] = data.get('id')
        if 'name' in data:
            cleaned_data['username'] = data.get('name')
        
        # 清洗时间格式
        for field in ['join_time', 'last_active']:
            if field in data:
                time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})', str(data[field]))
                if time_match:
                    cleaned_data[field] = time_match.group(1)
        
        # 清洗数据量
        for field in ['upload', 'download', 'uploaded', 'downloaded', 'seeding_size', 'official_seeding_size']:
            if field in data:
                cleaned_data[field.replace('upload', 'uploaded').replace('download', 'downloaded')] = await _convert_size_to_gb(data[field])
        
        # 清洗分享率
        if 'ratio' in data:
            ratio_match = re.search(r'([\d.]+)', str(data['ratio']))
            if ratio_match:
                cleaned_data['ratio'] = float(ratio_match.group(1))
        
        # 清洗数值型数据
        for field in ['bonus', 'seeding_score', 'bonus_per_hour']:
            if field in data:
                value_str = str(data[field]).replace(',', '')
                value_match = re.search(r'([\d.]+)', value_str)
                if value_match:
                    cleaned_data[field] = float(value_match.group(1))
        
        # 清洗整数型数据
        for field in ['hr_count', 'seeding_count', 'official_seeding_count']:
            if field in data:
                value_match = re.search(r'(\d+)', str(data[field]))
                if value_match:
                    cleaned_data[field] = int(value_match.group(1))
        
        return cleaned_data
    except Exception as e:
        logger.error("数据清洗失败", {'error': str(e)})
        return data

async def quick_test(site_id: str) -> None:
    """快速测试入口"""
    browser = None
    try:
        # 1. 创建站点设置
        site_setup = await create_site_setup(site_id)
        
        # 2. 创建站点配置解析器
        site_config = SiteParserConfig(site_setup.site_config.site_url, site_setup.site_config.site_id)
        
        # 2.1 合并站点特定配置
        site_config_path = Path(project_root) /  "services" / "sites" / "implementations" / f"_test_{site_id}.json"
        if site_config_path.exists():
            site_config.merge_config(str(site_config_path))
        
        # 3. 创建数据提取器
        extractor = DataExtractor(site_config)
        
        # 4. 初始化浏览器
        browser = setup_browser()
        
        # 5. 设置cookies
        if site_setup.crawler_credential.enable_manual_cookies:
            cookies = site_setup.crawler_credential.manual_cookies
            if cookies:
                domain = urlparse(site_setup.site_config.site_url).netloc
                cookies_list = parse_cookies(cookies, domain)
                browser.set.cookies(cookies_list)
                browser.latest_tab.get(site_setup.site_config.site_url)
                logger.info("从cookies恢复成功")
            else:
                raise Exception("cookies格式错误或为空")
        
        # 6. 数据提取
        tab = browser.latest_tab
        
        # 提取用户ID
        user_id = None
        try:
            user_link = tab.ele("@href:userdetails.php")
            if user_link:
                href = user_link.attr('href')
                user_id = href.split('id=')[1] if 'id=' in href else None
        except Exception as e:
                logger.error(f"提取用户ID失败: {str(e)}")
                raise Exception("无法获取用户ID")
        
        if not user_id:
            raise Exception("未找到用户ID")
            
        # 提取所有数据
        data = await extractor.extract_all(tab, user_id)
        
        # 清洗数据
        cleaned_data = await _clean_data(data)
        
        # 输出结果
        logger.info("提取结果:")
        logger.info(json.dumps(cleaned_data, ensure_ascii=False, indent=2))
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        raise
    finally:
        if browser:
            browser.quit()
            logger.info("浏览器已关闭")

def setup_browser() -> Chromium:
    """初始化浏览器"""
    options = ChromiumOptions()
    options.headless(True)  # 使用有头模式便于调试
    options.set_argument('--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    options.set_pref('credentials_enable_service', False)
    options.set_argument('--hide-crash-restore-bubble')
    
    browser = Chromium(options)
    logger.info("浏览器实例创建成功")
    return browser

async def handle_login(browser: Chromium, site_setup: SiteSetup, login_handler: LoginHandler) -> bool:
    """处理登录"""
    try:
        if site_setup.crawler_credential.enable_manual_cookies:
            cookies = site_setup.crawler_credential.manual_cookies
            if cookies:
                domain = urlparse(site_setup.site_config.site_url).netloc
                cookies_list = parse_cookies(cookies, domain)
                browser.set.cookies(cookies_list)
                browser.latest_tab.get(site_setup.site_config.site_url)
                logger.info("从cookies恢复成功")
                return True
            else:
                raise Exception("cookies格式错误或为空")
        else:
                login_success = await login_handler.perform_login(browser)
                if not login_success:
                    raise Exception("登录失败")
                logger.info("登录成功")
                return True
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        return False

async def create_site_setup(site_id: str, config_path: Optional[str] = None) -> SiteSetup:
    """创建站点设置"""
    try:
        # 直接从文件读取配置
        config_file = Path(project_root) /  "services" / "sites" / "implementations" / f"_test_{site_id}.json"
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
            
        with open(config_file, 'r', encoding='utf-8') as f:
            site_config_data = json.load(f)
            
        # 创建基础配置对象
        site_config = SiteConfigTestBase(
            site_id=site_config_data['site_id'],
            site_url=site_config_data['site_url'],
        )
        
        # 创建默认的爬虫配置
        crawler_config = CrawlerConfigBase(
            site_id=site_id,  # 添加必需的site_id字段
            browser_type='chromium',
            headless=True,
            auto_reload=True
        )
        
        # 创建默认的爬虫凭证
        crawler_credential = CrawlerCredentialBase(
            site_id=site_id,
            enable_manual_cookies=True,
            manual_cookies=os.getenv(f"{site_id.upper()}_COOKIES"))
        
        # 创建默认的基础设置
        settings = SettingsBase()
        
        # 创建站点设置
        site_setup = SiteSetupTest(
            site_id=site_id,
            site_config=site_config,
            crawler_config=crawler_config,
            crawler_credential=crawler_credential,
            settings=settings
        )
        
        logger.info(f"成功加载站点配置: {site_id}")
        return site_setup
        
    except Exception as e:
        logger.error(f"创建站点设置失败: {str(e)}")
        raise

if __name__ == "__main__":
    site_id = "hdfans"  # 替换为要测试的站点ID
    asyncio.run(quick_test(site_id))