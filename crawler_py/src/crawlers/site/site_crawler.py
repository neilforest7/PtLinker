import re
from typing import Any, Dict, Optional
from urllib.parse import urljoin

from DrissionPage import Chromium
from utils.logger import get_logger

from ..base.base_crawler import BaseCrawler


class SiteCrawler(BaseCrawler):
    """统一的站点爬虫类"""
    
    def __init__(self, task_config: Dict[str, Any]):
        super().__init__(task_config)
        self.logger = get_logger(name=__name__, site_id=self._get_site_id())
        self.base_url = task_config['site_url'][0]

    def _get_site_id(self) -> str:
        """从配置中获取站点ID"""
        return self.task_config.site_id
    
    async def _checkin(self, browser: Chromium):
        """执行签到流程"""
        pass
    
    async def _crawl(self, browser: Chromium):
        """统一的爬取逻辑"""
        try:
            # 创建并导航标签页
            tab = await self._create_and_navigate_tab(browser)
            
            try:
                # 提取所有数据
                data = await self._extract_all_data(tab)
                
                # 清洗数据
                cleaned_data = self._clean_data(data)
                
                # 保存数据
                self.logger.debug("保存提取的数据")
                await self._save_data(cleaned_data)
                
            finally:
                # 确保标签页被关闭
                self.logger.debug("关闭标签页")
                tab.close()
                
        except Exception as e:
            self.logger.error(f"爬取过程出错: {str(e)}")
            # 保存错误现场
            await self._save_screenshot(browser, 'error')
            await self._save_page_source(browser, 'error')
            raise

    async def _create_and_navigate_tab(self, browser: Chromium) -> Chromium:
        """创建标签页并导航到用户资料页面"""
        # 创建新标签页
        tab = browser.new_tab()
        browser.activate_tab(tab)
        self.logger.debug("创建新标签页")
        
        # 访问用户主页
        self.logger.debug(f"访问用户主页: {self.base_url}")
        tab.get(self.base_url)
        
        # 获取用户资料页面URL
        profile_url = await self._get_profile_url(tab)
        
        # 访问用户资料页面
        tab.get(profile_url)
        
        return tab

    async def _get_profile_url(self, tab: Chromium) -> str:
        """获取用户资料页面的URL"""
        # 从配置中获取资料链接选择器
        profile_config = self.task_config.custom_config.get('profile_link', {})
        selector = profile_config.get('selector', '@class=User_Name')  # 默认选择器
        
        self.logger.debug("查找用户资料链接")
        profile_element = tab.ele(selector)
        if not profile_element:
            raise Exception("未找到用户资料链接")
            
        profile_url = profile_element.attr('href')
        if not profile_url:
            raise Exception("未找到用户资料URL")
        
        # 提取用户ID（如果需要）
        uid = None
        if profile_config.get('extract_uid', True):
            uid_match = re.search(r'id=(\d+)', profile_url)
            if uid_match:
                uid = uid_match.group(1)
                self.logger.debug(f"提取到用户ID: {uid}")
            else:
                self.logger.warning("未能从URL中提取用户ID")
        
        # 确保使用完整URL
        full_profile_url = urljoin(self.base_url, profile_url)
        self.logger.debug(f"访问用户资料页面: {full_profile_url}")
        
        return full_profile_url

    async def _extract_all_data(self, tab: Chromium) -> Dict[str, Any]:
        """提取所有数据"""
        data = {}
        
        # 提取基本数据
        self.logger.info("开始提取用户基本数据")
        basic_data = await self._extract_data_with_rules(tab)
        data.update(basic_data)
        
        # 提取额外统计数据（如果配置了）
        if self.extract_rules and any(rule.name == 'seeding_list' for rule in self.extract_rules.rules):
            try:
                stats_data = await self._extract_stats_data(tab)
                data.update(stats_data)
            except Exception as e:
                self.logger.error(f"获取统计数据失败: {str(e)}")
        
        return data

    async def _extract_stats_data(self, tab: Chromium) -> Dict[str, Any]:
        """提取统计数据"""
        stats = {}
        
        if not self.extract_rules:
            return stats
            
        try:
            # 从extract_rules中获取配置
            rules_dict = {rule.name: rule for rule in self.extract_rules.rules}
            
            # 检查是否配置了做种列表按钮
            if 'seeding_list' in rules_dict:
                idx = rules_dict['seeding_list'].index
                seeding_btn = tab.ele(rules_dict['seeding_list'].selector, index=idx)
                if not seeding_btn:
                    self.logger.warning("未找到做种统计按钮")
                    return stats
                    
                self.logger.debug(f"找到做种统计按钮，开始点击")
                seeding_btn.click()
                
                # 提取做种数据
                volumes = []
                page = 0
                
                while True:
                    try:
                        # 等待容器加载并确保可见
                        container = tab.ele(rules_dict['seeding_list_container'].selector)
                        if not container:
                            self.logger.warning(f"未找到做种列表容器: {rules_dict['seeding_list_container'].selector}")
                            break
                        
                        self.logger.debug(f"找到容器: {container}")
                        
                        # 等待表格加载
                        self.logger.debug(f"开始查找表格: {rules_dict['seeding_list_table'].selector}")
                        table = container.ele(rules_dict['seeding_list_table'].selector, timeout=10)
                        if not table:
                            self.logger.warning(f"未找到表格: {rules_dict['seeding_list_table'].selector}")
                            break
                        
                        self.logger.debug(f"找到表格: {table}")
                        
                        # 提取当前页面的体积数据
                        rows = table.eles('tag:tr')
                        self.logger.debug(f"找到 {len(rows)-1} 行数据")
                        
                        vidx = rules_dict['seeding_list_table'].index
                        for row in rows[1:]:  # 跳过表头
                            cell = row.ele('tag:td', index=vidx)
                            if cell:
                                volumes.append(cell.text.strip())
                                    
                        pagination = container.ele(rules_dict['seeding_list_pagination'].selector)
                        # 检查是否有下一页
                        if not pagination:
                            self.logger.debug("没有分页，提取完成")
                            break
                            
                        page_link = pagination.ele(f'@href$page={page + 1}')
                        if not page_link:
                            self.logger.debug("没有下一页，提取完成")
                            break
                            
                        # 点击下一页
                        self.logger.debug(f"找到页码 {page + 1} 的链接: {page_link}")
                        # 点击链接
                        page_link.wait.clickable()
                        page_link.click()
                        self.logger.debug(f"点击页码 {page + 1} 的链接")
                        page += 1
                        
                    except Exception as e:
                        self.logger.error(f"处理第 {page} 页时出错: {str(e)}")
                        break
                        
                self.logger.info(f"共提取到 {len(volumes)} 条做种数据")
                
                # 统计做种数量和总体积
                seeding_count = len(volumes)
                seeding_size = sum(self._convert_size_to_gb(v) for v in volumes)
                
                stats['seeding_count'] = seeding_count
                self.logger.info(f"提取到做种数量: {stats['seeding_count']}")
                stats['seeding_size'] = f"{seeding_size:.2f} GB"
                self.logger.info(f"提取到总做种体积: {stats['seeding_size']}")
                
        except Exception as e:
            self.logger.error(f"解析做种统计数据失败: {str(e)}")
            self.logger.debug(f"错误详情: {type(e).__name__}")
            self.logger.debug(f"错误堆栈: ", exc_info=True)
            
        return stats 