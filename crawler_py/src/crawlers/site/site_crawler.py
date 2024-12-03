import re
from typing import Any, Dict, Optional
from urllib.parse import urljoin

from DrissionPage import Chromium
from utils.url import convert_url
from models.crawler import WebElement
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
        self.profile_url, self.uid = await self._get_profile_url(tab)

        # 访问用户资料页面
        tab.get(self.profile_url)
        
        return tab

    async def _get_profile_url(self, tab: Chromium) -> str:
        """获取用户资料页面的URL"""
        # 从配置中获取资料链接选择器
        profile_config = self.task_config.extract_rules
        selector = [rule.selector for rule in profile_config.rules if rule.name == 'username'][0]
        self.logger.debug("查找用户资料链接")
        profile_element = tab.ele(selector)
        if not profile_element:
            raise Exception("未找到用户资料链接")
            
        profile_url = profile_element.attr('href')
        if not profile_url:
            raise Exception("未找到用户资料URL")
        
        # 提取用户ID（如果需要）
        uid = None
        uid_match = re.search(r'id=(\d+)', profile_url)
        if uid_match:
            uid = uid_match.group(1)
            self.logger.debug(f"提取到用户ID: {uid}")
        else:
            self.logger.warning("未能从URL中提取用户ID")
        
        # 确保使用完整URL
        full_profile_url = convert_url(self.task_config, profile_url, uid=uid)
        self.logger.debug(f"访问用户资料页面: {full_profile_url}")
        
        return full_profile_url, uid

    async def _extract_all_data(self, tab: Chromium) -> Dict[str, Any]:
        """提取所有数据"""
        data = {}
        
        # 提取基本数据
        self.logger.info("开始提取用户基本数据")
        basic_data = await self._extract_data_with_rules(tab)
        data.update(basic_data)
        data.update(dict(uid=self.uid))

        # 提取额外统计数据（如果配置了）
        if self.extract_rules and any(rule.name == 'seeding_list' for rule in self.extract_rules.rules):
            try:
                seeding_data = await self._extract_seeding_data(tab)
                data.update(seeding_data)
            except Exception as e:
                self.logger.error(f"获取统计数据失败: {str(e)}")
        
        return data

    async def _extract_seeding_data(self, tab: Chromium) -> Dict[str, Any]:
        """提取做种数据"""
        seeding_data = {}
        
        if not self.extract_rules:
            return seeding_data

        try:
            # 从extract_rules中获取配置
            rules_dict = {rule.name: rule for rule in self.extract_rules.rules}
            
            # 检查是否配置了做种列表按钮
            if 'seeding_list' in rules_dict:
                idx = rules_dict['seeding_list'].index
                
                # 如果不需要预处理，则点击做种统计按钮
                if not rules_dict['seeding_list'].need_pre_action:                    
                    seeding_btn = tab.ele(rules_dict['seeding_list'].selector, index=idx)
                    if not seeding_btn:
                        self.logger.warning("未找到做种统计按钮")
                        return seeding_data
                        
                    self.logger.debug(f"找到做种统计按钮，开始点击")
                    seeding_btn.click()

                # 假设需要预处理，方式为访问做种列表页面，代表站点audiences
                elif rules_dict['seeding_list'].pre_action_type == 'goto':
                    self.logger.debug(f"需要预处理，访问页面: {rules_dict['seeding_list'].page_url}")
                    tab.get(convert_url(self.task_config, rules_dict['seeding_list'].page_url, uid=self.uid))
                    self.logger.debug(f"访问converted页面: {tab.url}")
                    
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
                        if rules_dict['seeding_list_table'].location == 'index':
                            # audiences做种表格中有两个table，第二个table是做种列表
                            table_idx = int(rules_dict['seeding_list_table'].second_selector)
                            table = container.ele(rules_dict['seeding_list_table'].selector, index=table_idx, timeout=3)
                        else:
                            table = container.ele(rules_dict['seeding_list_table'].selector, timeout=3)
                        if not table:
                            self.logger.warning(f"未找到表格: {rules_dict['seeding_list_table'].selector}")
                            break
                        
                        self.logger.debug(f"找到表格: {table}")
                        
                        # 提取当前页面的体积数据
                        
                        if 'seeding_list_row' not in rules_dict:
                            rows = table.eles('tag:tr')
                        elif rules_dict['seeding_list_row'].location == 'grand-child':
                            rows = table.child().children()
                        self.logger.debug(f"找到 {len(rows)-1} 行数据")
                        
                        vidx = rules_dict['seeding_list_table'].index
                        for row in rows[1:]:  # 跳过表头
                            cell = row.ele('tag:td', index=vidx)
                            if cell:
                                volumes.append(cell.text.strip())
                                    
                        # 检查是否有分页
                        if rules_dict['seeding_list_pagination'].location == 'parent':
                            # audiences找到分页的父元素
                            pagination = container.ele(rules_dict['seeding_list_pagination'].selector).parent()
                        else:
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
                
                seeding_data['seeding_count'] = seeding_count
                self.logger.info(f"提取到做种数量: {seeding_data['seeding_count']}")
                seeding_data['seeding_size'] = f"{seeding_size:.2f} GB"
                self.logger.info(f"提取到总做种体积: {seeding_data['seeding_size']}")
                
        except Exception as e:
            self.logger.error(f"解析做种统计数据失败: {str(e)}")
            self.logger.debug(f"错误详情: {type(e).__name__}")
            self.logger.debug(f"错误堆栈: ", exc_info=True)
            
        return seeding_data 

    async def _extract_data_with_rules(self, tab: Chromium) -> Dict[str, Any]:
        """根据规则提取数据"""
        data = {}
        
        if not self.extract_rules:
            self.logger.info("未配置数据提取规则")
            return data
            
        # 按规则分组，先处理不需要预处理的规则
        normal_rules = []
        pre_action_rules = []
        rule: WebElement
        for rule in self.extract_rules.rules:
            if rule.need_pre_action:
                pre_action_rules.append(rule)
            else:
                normal_rules.append(rule)
                
        # 先处理普通规则
        for rule in normal_rules:
            try:
                value = await self._extract_element_value(tab, rule)
                if value is not None:
                    data[rule.name] = value
                elif rule.required:
                    raise ValueError(f"必需的字段 {rule.name} 未能提取到值")
            except Exception as e:
                self.logger.error(f"提取 {rule.name} 时出错: {str(e)}")
                if rule.required:
                    raise
                    
        # 处理需要预处理的规则
        for rule in pre_action_rules:
            try:
                original_url = tab.url
                # 如果规则指定了页面URL，先访问该页面
                if rule.pre_action_type == 'goto' and rule.page_url:
                    full_url = convert_url(self.task_config, rule.page_url, uid=self.uid)
                    self.logger.debug(f"访问页面: {full_url}")
                    tab.get(full_url)
                
                    # 提取数据
                    value = await self._extract_element_value(tab, rule)
                    if value is not None:
                        data[rule.name] = value
                    elif rule.required:
                        raise ValueError(f"必需的字段 {rule.name} 未能提取到值")
                    # 返回原页面
                    tab.get(original_url)

            except Exception as e:
                self.logger.error(f"提取 {rule.name} 时出错: {str(e)}")
                if rule.required:
                    raise
            
        return data
        
    async def _extract_element_value(self, tab: Chromium, rule: WebElement) -> Optional[str]:
        """提取元素值"""
        try:
            # 根据位置关系查找元素
            if rule.location:
                base_element = tab.ele(rule.selector)
                if not base_element:
                    self.logger.warning(f"未找到基础定位元素: {rule.selector}")
                    return None
                    
                if rule.location == 'next':
                    element = base_element.next()
                elif rule.location == 'parent':
                    element = base_element.parent()
                elif rule.location == 'next-child' and rule.second_selector:
                    element = base_element.next().child(rule.second_selector)
                elif rule.location == 'parent-child' and rule.second_selector:
                    element = base_element.parent().child(rule.second_selector)
                elif rule.location == 'east' and rule.second_selector:
                    element = base_element.east(rule.second_selector)
                else:
                    element = base_element
            else:
                element = tab.ele(rule.selector)
                
            if not element:
                self.logger.warning(f"未找到元素: {rule.selector}")
                return None
                
            # 根据类型提取值
            value = None
            if rule.type == "text":
                value = element.text
            elif rule.type == "attribute" and rule.attribute:
                value = element.attr(rule.attribute)
            elif rule.type == "by_day":
                # 用于u2临时提取UCoin值
                self.logger.debug(f"提取 {rule.name} 时，元素文本: {element.texts()[-1]}")
                match = re.search(r'UCoin(\d+\.\d+)', element.texts()[0])
                if match:
                    result = match.group(1)
                    value = str(float(result)/24)
            elif rule.type == "html":
                value = element.html
            elif rule.type == "src":
                value = element.attr('src')
                
            self.logger.debug(f"提取到{rule.name}: {value}")
            return value.strip() if value else None
            
        except Exception as e:
            self.logger.error(f"提取元素值时出错: {str(e)}")
            return None