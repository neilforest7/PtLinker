import json
import os
from time import sleep
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple
import re
from urllib.parse import urljoin

from loguru import logger
from DrissionPage import Chromium, ChromiumOptions

from handlers.login import LoginHandler
from models.crawler import CrawlerTaskConfig
from utils.logger import get_logger


class BaseCrawler(ABC):
    def __init__(self, task_config: Dict[str, Any]):
        self.task_config = CrawlerTaskConfig(**task_config)
        self.storage_dir = Path(os.getenv('STORAGE_PATH', 'storage'))
        self.site_id = self._get_site_id()
        
        # 任务数据存储路径
        self.task_storage_path = self.storage_dir / 'tasks' / self.site_id / str(task_config['task_id'])
        self.task_storage_path.mkdir(parents=True, exist_ok=True)
        
        # 初始化登录处理器
        self.login_handler = LoginHandler(self.task_config)
        
        # 根据环境变量设置 headless 模式
        if os.getenv('HEADLESS', 'false').lower() == 'true':
            self.chrome_options = ChromiumOptions().headless().auto_port()
        else:
            self.chrome_options = ChromiumOptions().auto_port()
        
        # 设置User-Agent
        self.chrome_options.set_argument('--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0')
        
        # 添加其他启动参数
        arguments = [
            "--no-first-run",
            "--force-color-profile=srgb",
            "--metrics-recording-only",
            "--password-store=basic",
            "--use-mock-keychain",
            "--export-tagged-pdf",
            "--no-default-browser-check",
            "--disable-background-mode",
            "--enable-features=NetworkService,NetworkServiceInProcess,LoadCryptoTokenExtension,PermuteTLSExtensions",
            "--disable-features=FlashDeprecationWarning,EnablePasswordsAccountStorage",
            "--deny-permission-prompts",
            "--disable-gpu"
            # "--headless=new"
            # "--incognito"
        ]
        
        # 添加所有参数
        for arg in arguments:
            self.chrome_options.set_argument(arg)
        
        self.browser: Optional[Chromium] = None
        self.logger = logger.bind(task_id=task_config['task_id'], site_id=self.site_id)

    @abstractmethod
    def _get_site_id(self) -> str:
        """返回站点ID"""
        pass

    async def start(self):
        """启动爬虫"""
        try:
            # 使用ChromiumOptions初始化浏览器
            self.browser = Chromium(self.chrome_options)
            self.logger.debug(f"创建新的浏览器实例，端口: {self.chrome_options}")
            
            try:
                # 尝试恢复登录状态或执行登录
                if not os.getenv('FRESH_LOGIN', 'false').lower() == 'true':
                    if await self.login_handler.restore_browser_state(self.browser):
                        self.logger.info("成功恢复登录状态")
                    else:
                        self.logger.info("无法恢复登录状态，执行登录流程")
                        await self.login_handler.perform_login(self.browser, self.task_config.login_config)
                else:
                    self.logger.info("FRESH_LOGIN=true，执行从头登录流程")
                    await self.login_handler.perform_login(self.browser, self.task_config.login_config)
                
                # 开始爬取
                await self._crawl(self.browser)

            finally:
                # 清理浏览器资源
                if self.browser:
                    self.logger.debug("关闭浏览器实例")
                    self.browser.quit()

        except Exception as e:
            error_info = {
                'type': 'CRAWLER_ERROR',
                'message': str(e),
                'timestamp': datetime.now().isoformat(),
                'traceback': traceback.format_exc()
            }
            await self._save_error(error_info)
            raise e

    async def _save_data(self, data: Dict[str, Any]):
        """保存爬取的数据到任务目录"""
        data_file = self.task_storage_path / f'data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    async def _save_error(self, error: Dict[str, Any]):
        """保存错误信息到任务目录"""
        error_file = self.task_storage_path / f'error_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        error_file.write_text(json.dumps(error, ensure_ascii=False, indent=2))

    async def _save_screenshot(self, browser: Chromium, name: str):
        """保存页面截图"""
        try:
            tab = browser.latest_tab
            if not tab:
                raise Exception("未找到活动标签页")
                
            screenshot_path = self.task_storage_path / f'{name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            tab.get_screenshot(screenshot_path)
            self.logger.info(f"页面截图已保存: {screenshot_path}")
        except Exception as e:
            self.logger.error(f"保存截图失败: {str(e)}")
            
    async def _save_page_source(self, browser: Chromium, name: str):
        """保存页面源码"""
        try:
            tab = browser.latest_tab
            if not tab:
                raise Exception("未找到活动标签页")
                
            html_path = self.task_storage_path / f'{name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
            html_path.write_text(tab.html, encoding='utf-8')
            self.logger.info(f"页面源码已保存: {html_path}")
        except Exception as e:
            self.logger.error(f"保存页面源码失败: {str(e)}")

    async def _extract_data_with_rules(self, browser: Chromium, rules: list) -> Dict[str, Any]:
        """使用规则提取数据的通用方法"""
        data = {}
        try:
            tab = browser.latest_tab
            if not tab:
                raise Exception("未找到活动标签页")

            for rule in rules:
                try:
                    name = rule['name']
                    selector = rule['selector']
                    element_type = rule.get('type', 'text')
                    required = rule.get('required', False)
                    transform = rule.get('transform', None)
                    location = rule.get('location', None)
                    second_selector = rule.get('second_selector', None)
                    ele_only = rule.get('ele_only', True)

                    if location == 'next':
                        element = tab.ele(selector).next(second_selector)
                    elif location == 'parent':
                        element = tab.ele(selector).parent(second_selector)
                    elif location == 'next-child':
                        element = tab.ele(selector).next().child(second_selector)
                    elif location == 'parent-child':
                        element = tab.ele(selector).parent().child(second_selector, ele_only)
                    elif location == 'east':
                        element = tab.ele(selector).east(second_selector)
                    else:
                        element = tab.ele(selector)
                        
                    if not element:
                        if required:
                            self.logger.error(f"未找到必需的元素: {name} (选择器: {selector})")
                        else:
                            self.logger.warning(f"未找到可选元素: {name} (选择器: {selector})")
                        continue

                    # 根据类型提取数据
                    if element_type == 'text':
                        value = element.text
                        self.logger.info(f"{name}提取到文本: {value}")
                    elif element_type == 'attribute':
                        attribute = rule.get('attribute')
                        if not attribute:
                            self.logger.error(f"属性类型的规则缺少attribute字段: {name}")
                            continue
                        value = element.attr(attribute)
                    else:
                        self.logger.warning(f"未知的元素类型: {element_type}")
                        continue

                    # 应用转换函数
                    if transform and value:
                        if transform == 'extract_class':
                            class_match = re.search(r'class=(.*?)(?:\s|$)', value)
                            value = class_match.group(1) if class_match else value
                        else:
                            self.logger.warning(f"未知的转换函数: {transform}")

                    if value:
                        data[name] = value.strip()
                    else:
                        self.logger.warning(f"元素 {name} 的值为空")

                except Exception as e:
                    self.logger.error(f"提取 {name} 时出错: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"提取数据失败: {str(e)}")

        return data

    def _convert_size_to_gb(self, size_str: str) -> float:
        """将带单位的数据量字符串转换为以GB为单位的float值
        
        Args:
            size_str: 包含数字和单位的字符串，如 "1.5 TB", "500 MB", "2.3GB"
            
        Returns:
            float: 转换后的GB值
            
        Examples:
            >>> _convert_size_to_gb("1.5 TB")  # 返回 1536.0
            >>> _convert_size_to_gb("500 MB")  # 返回 0.48828125
            >>> _convert_size_to_gb("2.3 GB")  # 返回 2.3
        """
        try:
            # 提取数字和单位
            size_match = re.search(r'([\d.]+)\s*(TB|GB|MB|kb|b)', size_str, re.IGNORECASE)
            if not size_match:
                self.logger.warning(f"无法解析的数据量格式: {size_str}")
                return 0.0
                
            size_num = float(size_match.group(1))
            size_unit = size_match.group(2).upper()
            
            # 转换为GB
            if size_unit == 'TB':
                return size_num * 1024
            elif size_unit == 'GB':
                return size_num
            elif size_unit == 'MB':
                return size_num / 1024
            elif size_unit == 'KB':
                return size_num / (1024 * 1024)
            elif size_unit == 'B':
                return size_num / (1024 * 1024 * 1024)
            else:
                self.logger.warning(f"未知的数据量单位: {size_unit}")
                return 0.0
                
        except Exception as e:
            self.logger.error(f"转换数据量失败: {str(e)}, 原始字符串: {size_str}")
            return 0.0

    def _clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """清洗爬取的数据的基础方法"""
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
            
            # 清洗时间格式
            if 'join_time' in data:
                join_time = re.search(r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})', data['join_time'])
                if join_time:
                    cleaned_data['join_time'] = datetime.strptime(join_time.group(1), '%Y-%m-%d %H:%M:%S').isoformat()
            
            if 'last_active' in data:
                last_active = re.search(r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})', data['last_active'])
                if last_active:
                    cleaned_data['last_active'] = datetime.strptime(last_active.group(1), '%Y-%m-%d %H:%M:%S').isoformat()
            
            # 清洗上传下载数据
            if 'upload' in data:
                size_in_gb = self._convert_size_to_gb(data['upload'])
                cleaned_data['upload'] = size_in_gb
            
            if 'download' in data:
                size_in_gb = self._convert_size_to_gb(data['download'])
                cleaned_data['download'] = size_in_gb
            
            # 清洗分享率（转换为float）
            if 'ratio' in data:
                ratio_match = re.search(r'([\d.]+)', data['ratio'])
                if ratio_match:
                    cleaned_data['ratio'] = float(ratio_match.group(1))
            # 清洗魔力值（转换为float，处理带逗号的数值）
            if 'bonus' in data:
                bonus_str = data['bonus'].replace(',', '')
                bonus_match = re.search(r'([\d.]+)', bonus_str)
                if bonus_match:
                    cleaned_data['bonus'] = float(bonus_match.group(1))
            
            # 清洗做种积分（转换为float，处理带逗号的数值）
            if 'seeding_score' in data:
                score_str = data['seeding_score'].replace(',', '')
                score_match = re.search(r'([\d.]+)', score_str)
                if score_match:
                    cleaned_data['seeding_score'] = float(score_match.group(1))
            # 清洗HR数量（转换为int）
            if 'hr_count' in data:
                hr_match = re.search(r'(\d+)', data['hr_count'])
                if hr_match:
                    cleaned_data['hr_count'] = int(hr_match.group(1))
            
            # 清洗做种体积数据
            if 'seeding_size' in data:
                size_in_gb = self._convert_size_to_gb(data['seeding_size'])
                cleaned_data['seeding_size'] = size_in_gb
            if 'official_seeding_size' in data:
                size_in_gb = self._convert_size_to_gb(data['official_seeding_size'])
                cleaned_data['official_seeding_size'] = size_in_gb
            
            # 转换做种数量为int
            if 'seeding_count' in data:
                cleaned_data['seeding_count'] = int(data['seeding_count'])
            if 'official_seeding_count' in data:
                cleaned_data['official_seeding_count'] = int(data['official_seeding_count'])
            
            return cleaned_data
            
        except Exception as e:
            self.logger.error("数据清洗失败", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            return data  # 如果清洗失败，返回原始数据

    @abstractmethod
    async def _check_login(self, browser: Chromium) -> bool:
        """检查是否已登录"""
        pass

    @abstractmethod
    async def _crawl(self, browser: Chromium):
        """爬取数据的主要逻辑"""
        pass

    async def _extract_seeding_volumes(self, tab: Chromium, container_selector: str, table_selector: str, pagination_selector: str, volume_selector_index: int) -> List[str]:
        """
        通用的统计做种容器函数，处理分页并提取每页的种子体积
        
        Args:
            tab: DrissionPage标签页实例
            container_selector: 容器的选择器
            table_selector: 表格的选择器
            volume_selector_index: 体积列的索引（从0开始）
        
        Returns:
            包含所有页面种子体积的列表
        """
        volumes = []
        tab.wait.ele_displayed(container_selector, timeout=10)
        
        # 获取第一页数据
        self.logger.debug("处理第1页数据")
        container = tab.ele(container_selector)
        if not container:
            self.logger.warning(f"未找到容器: {container_selector}")
            return volumes
            
        table = container.ele(table_selector)
        if not table:
            self.logger.warning(f"未找到表格: {table_selector}")
            return volumes

        rows = table.eles('@tag()=tr')[1:]  # 排除表头
        for row in rows:
            volume_cell = row.ele('@tag()=td', index=volume_selector_index)
            if volume_cell:
                volumes.append(volume_cell.text.strip())
        
        # 检查分页
        pagination = container.ele(pagination_selector)
        if not pagination:
            self.logger.debug("没有检测到分页，处理完成")
            return volumes
            
        # 获取所有页码链接
        page_numbers = []
        for link in pagination.eles('@tag()=a'):
            href = link.attr('href')
            if href and 'page=' in href:
                try:
                    # 从链接中提取页码
                    page_num = int(re.search(r'page=(\d+)', href).group(1))
                    if page_num not in page_numbers:
                        page_numbers.append(page_num)
                        self.logger.debug(f"添加页码: {page_num +1}")
                except (AttributeError, ValueError):
                    continue
        
        # 按页码排序
        page_numbers.sort()
        
        # 处理后续页面
        for page_num in page_numbers:
            try:
                # 找到对应页码的链接并点击
                pagination = tab.ele(container_selector).ele(pagination_selector)
                page_link = pagination.ele(f'@href$page={page_num}')
                self.logger.debug(f"找到页码 {page_num + 1} 的链接: {page_link}")
                if not page_link:
                    self.logger.warning(f"未找到页码 {page_num + 1} 的链接")
                    continue
                # 点击链接
                page_link.wait.clickable()
                page_link.click()
                self.logger.debug(f"点击页码 {page_num + 1} 的链接")
                
                # 等待表格重新加载
                tab.wait.ele_displayed(table_selector, timeout=10)
                self.logger.debug(f"等待表格重新加载完成")
                
                table = container.ele(table_selector)
                if not table:
                    self.logger.warning(f"未找到表格: {table_selector}")
                    continue
                
                # 提取数据
                rows = table.eles('@tag()=tr')[1:]  # 排除表头
                for row in rows:
                    volume_cell = row.ele('@tag()=td', index=volume_selector_index)
                    if volume_cell:
                        volumes.append(volume_cell.text.strip())
                        
            except Exception as e:
                self.logger.error(f"处理第{page_num + 1}页时出错: {str(e)}")
                continue
        
        self.logger.info(f"共处理 {len(volumes)} 条做种数据")
        return volumes