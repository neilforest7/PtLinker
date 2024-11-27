import re
from datetime import datetime
from typing import Any, Dict
from urllib.parse import urljoin

from config.sites import EXTRACT_RULES
from DrissionPage import Chromium
from loguru import logger
from models.crawler import LoginConfig

from ..base.base_crawler import BaseCrawler


class HDHomeCrawler(BaseCrawler):
    def __init__(self, task_config: Dict[str, Any]):
        super().__init__(task_config)
        self.base_url = task_config['start_urls'][0]
        self.logger = logger.bind(site="hdhome")
        self.extract_rules = EXTRACT_RULES.get('hdhome', [])
        if not self.extract_rules:
            self.logger.warning("未找到hdhome的数据提取规则")

    def _get_site_id(self) -> str:
        return 'hdhome'

    async def _check_login(self, browser: Chromium) -> bool:
        """检查是否已登录"""
        try:
            tab = browser.latest_tab
            if not tab:
                tab = browser.new_tab()
                browser.activate_tab(tab)
                
            username_element = tab.ele('@class=User_Name')
            if username_element:
                return username_element.eles('tag:a') == self.task_config.username
            return False
        except Exception as e:
            self.logger.error(f"检查登录状态失败: {str(e)}")
            return False

    async def _crawl(self, browser: Chromium):
        """爬取数据的主要逻辑"""
        try:
            # 创建新标签页
            tab = browser.new_tab()
            browser.activate_tab(tab)
            self.logger.debug("创建新标签页")
            
            # 访问用户主页
            self.logger.debug(f"访问用户主页: {self.base_url}")
            tab.get(self.base_url)
            # tab.wait.load_complete()  # DrissionPage会自动等待页面加载完成
            
            # 获取用户资料页面URL
            self.logger.debug("查找用户资料链接")
            profile_element = tab.ele('@class=User_Name')
            if not profile_element:
                raise Exception("未找到用户资料链接")
                
            profile_url = profile_element.attr('href')
            if not profile_url:
                raise Exception("未找到用户资料URL")
                
            # 确保使用完整URL
            full_profile_url = urljoin(self.base_url, profile_url)
            self.logger.debug(f"访问用户资料页面: {full_profile_url}")

            # 访问用户资料页面
            tab.get(full_profile_url)
            # tab.wait.load_complete()  # DrissionPage会自动等待页面加载完成

            # 提取基本数据
            self.logger.debug("开始提取用户基本数据")
            data = await self._extract_user_data(browser)
            seeding_stats = await self._extract_seeding_stats(browser)
            data.update(seeding_stats)

            # 保存数据
            self.logger.debug("保存提取的数据")
            await self._save_data(data)
            
            # 关闭标签页
            self.logger.debug("关闭标签页")
            tab.close()
            
        except Exception as e:
            self.logger.error(f"爬取过程出错: {str(e)}")
            # 保存错误现场
            await self._save_screenshot(browser, 'error')
            await self._save_page_source(browser, 'error')
            raise

    def _clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """清洗爬取的数据"""
        cleaned_data = {}
        
        try:
            # 用户名保持不变
            if 'username' in data:
                cleaned_data['username'] = data['username']
            if 'user_class' in data:
                cleaned_data['user_class'] = data['user_class']
                
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
                size_match = re.search(r'([\d.]+)\s*(TB|GB|MB)', data['upload'])
                if size_match:
                    size_num = float(size_match.group(1))
                    size_unit = size_match.group(2)
                    size_in_gb = size_num
                    if size_unit == 'MB':
                        size_in_gb = size_num / 1024
                    elif size_unit == 'TB':
                        size_in_gb = size_num * 1024
                    cleaned_data['upload'] = f"{size_in_gb:.2f} GB"
            
            if 'download' in data:
                size_match = re.search(r'([\d.]+)\s*(TB|GB|MB)', data['download'])
                if size_match:
                    size_num = float(size_match.group(1))
                    size_unit = size_match.group(2)
                    size_in_gb = size_num
                    if size_unit == 'MB':
                        size_in_gb = size_num / 1024
                    elif size_unit == 'TB':
                        size_in_gb = size_num * 1024
                    cleaned_data['download'] = f"{size_in_gb:.2f} GB"
            
            # 清洗分享率（转换为float）
            if 'ratio' in data:
                ratio_match = re.search(r'([\d.]+)', data['ratio'])
                if ratio_match:
                    cleaned_data['ratio'] = float(ratio_match.group(1))
            
            # 清洗魔力值（转换为float）
            if 'bonus' in data:
                bonus_match = re.search(r'([\d.]+)', data['bonus'])
                if bonus_match:
                    cleaned_data['bonus'] = float(bonus_match.group(1))
            
            # 清洗做种积分（转换为float）
            if 'seeding_score' in data:
                score_match = re.search(r'([\d.]+)', data['seeding_score'])
                if score_match:
                    cleaned_data['seeding_score'] = float(score_match.group(1))
            
            # 清洗HR数量（转换为int）
            if 'hr_count' in data:
                hr_match = re.search(r'(\d+)', data['hr_count'])
                if hr_match:
                    cleaned_data['hr_count'] = int(hr_match.group(1))
            
            # 保留已经清洗过的体积数据
            if 'seeding_size' in data:
                cleaned_data['seeding_size'] = data['seeding_size']
            if 'official_seeding_size' in data:
                cleaned_data['official_seeding_size'] = data['official_seeding_size']
            
            # 转换做种数量为int
            if 'seeding_count' in data:
                cleaned_data['seeding_count'] = int(data['seeding_count'])
            if 'official_seeding_count' in data:
                cleaned_data['official_seeding_count'] = int(data['official_seeding_count'])
            
            return cleaned_data
            
        except Exception as e:
            self.logger.error(f"数据清洗失败: {str(e)}")
            self.logger.debug(f"错误详情: {type(e).__name__}")
            self.logger.debug(f"错误堆栈: ", exc_info=True)
            return data  # 如果清洗失败，返回原始数据

    async def _extract_user_data(self, browser: Chromium) -> Dict[str, Any]:
        """提取用户基本数据"""
        data = {}
        
        try:
            tab = browser.latest_tab
            if not tab:
                raise Exception("未找到活动标签页")

            # 使用EXTRACT_RULES中的规则提取数据
            for rule in self.extract_rules:
                try:
                    name = rule['name']
                    selector = rule['selector']
                    element_type = rule.get('type', 'text')
                    required = rule.get('required', False)
                    transform = rule.get('transform', None)
                    location = rule.get('location', None)
                    second_selector = rule.get('second_selector', None)

                    if location == 'next':
                        element = tab.ele(selector).next(second_selector)
                    elif location == 'parent':
                        element = tab.ele(selector).parent(second_selector)
                    elif location == 'next-child':
                        element = tab.ele(selector).next().child(second_selector)
                    else:
                        element = tab.ele(selector, timeout=1)

                    if not element:
                        if required:
                            self.logger.error(f"未找到必需的元素: {name} (选择器: {selector} 次级选择器: {second_selector})")
                        else:
                            self.logger.warning(f"未找到可选元素: {name} (选择器: {selector} 次级选择器: {second_selector})")
                        continue
                    else:
                        self.logger.debug(f"找到元素: {name} (选择器: {selector} 次级选择器: {second_selector})")

                    # 根据类型提取数据
                    if element_type == 'text':
                        value = element.text
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
            self.logger.error(f"提取用户数据失败: {str(e)}")
            
        # 清洗数据
        return self._clean_data(data)

    async def _extract_seeding_stats(self, browser: Chromium) -> Dict[str, Any]:
        """提取做种统计数据"""
        stats = {}
        tab = browser.latest_tab
        if not tab:
            raise Exception("未找到活动标签页")
        
        # 找到做种统计按钮
        try:
            self.logger.debug("开始获取做种统计")
            # 点击显示做种统计按钮
            seeding_btn = tab.ele('@href^javascript: getusertorrentlistajax',index=2)
            if seeding_btn:
                self.logger.debug(f"找到做种统计按钮{seeding_btn}，开始点击")
                seeding_btn.click()
            else:
                self.logger.warning("未找到做种统计按钮")
                
        except Exception as e:
            self.logger.error(f"获取做种统计失败: {str(e)}")

        # 提取做种数量和体积
        try:
            # 获取做种列表容器
            seeding_container = tab.ele('@id=ka1')
            if not seeding_container:
                self.logger.warning("未找到做种统计容器")
                return stats

            # 提取做种体积和数量
            size_elements = seeding_container.text.split('类型')[0]
            self.logger.debug(f"获取到做种: {size_elements}")
            if size_elements:
                total_num = re.search(r'(\d+)条记录', size_elements)
                offi_num = re.search(r'官种数量\s*(\d+)\s*个', size_elements)
                # 提取总体积时
                total_size_match = re.search(r'Total:\s*([\d.]+)\s*(TB|GB|MB)', size_elements)
                if total_size_match:
                    size_num = float(total_size_match.group(1))
                    size_unit = total_size_match.group(2)
                    # 转换为GB
                    size_in_gb = size_num
                    if size_unit == 'MB':
                        size_in_gb = size_num / 1024  # MB -> GB
                    elif size_unit == 'TB':
                        size_in_gb = size_num * 1024  # TB -> GB
                    stats['seeding_size'] = f"{size_in_gb:.2f} GB"
                    self.logger.debug(f"提取到总做种体积: {stats['seeding_size']}")

                # 提取官种体积时
                official_size_match = re.search(r'官种体积：([\d.]+)\s*(TB|GB|MB)', size_elements)
                if official_size_match:
                    size_num = float(official_size_match.group(1))
                    size_unit = official_size_match.group(2)
                    # 转换为GB
                    size_in_gb = size_num
                    if size_unit == 'MB':
                        size_in_gb = size_num / 1024  # MB -> GB
                    elif size_unit == 'TB':
                        size_in_gb = size_num * 1024  # TB -> GB
                    stats['official_seeding_size'] = f"{size_in_gb:.2f} GB"
                    self.logger.debug(f"提取到官种体积: {stats['official_seeding_size']}")

                stats['seeding_count'] = total_num.group(1)
                stats['official_seeding_count'] = offi_num.group(1)
            else:
                self.logger.warning("未找到做种体积信息")
        except Exception as e:
            self.logger.error(f"提取做种统计失败: {str(e)}")
            self.logger.debug(f"错误详情: {type(e).__name__}")
            self.logger.debug(f"错误堆栈: ", exc_info=True)
            
        return self._clean_data(stats)
        
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