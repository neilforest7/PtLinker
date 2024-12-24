import re
from typing import Any, Dict, Literal, Optional
from urllib.parse import urljoin

from DrissionPage import Chromium
from models.models import TaskStatus
from schemas.siteconfig import ExtractRuleSet, WebElement
from schemas.sitesetup import SiteSetup
from utils.url import convert_url

from .base_crawler import BaseCrawler


class SiteCrawler(BaseCrawler):
    """统一的站点爬虫类"""
    
    def __init__(self, site_setup: SiteSetup, task_id: str):
        # 先调用父类的初始化
        super().__init__(site_setup, task_id)

    def _get_site_id(self) -> str:
        """从配置中获取站点ID"""
        return self.site_setup.site_id
    
    async def _crawl(self, browser: Chromium):
        """统一的爬取逻辑"""
        try:
            # 创建并导航标签页
            tab = await self._create_and_navigate_tab(browser)
            
            try:
                # 提取所有数据
                await self._update_progress(3, 6, "正在提取数据")
                data = await self._extract_all_data(tab)
                
                # 清洗数据
                await self._update_progress(4, 6, "正在清洗数据")
                cleaned_data = await self._clean_data(data)
                
                # 保存数据
                self.logger.debug("保存提取的数据")
                await self._save_crawl_data(cleaned_data)

            finally:
                # 确保标签页被关闭
                self.logger.debug("关闭标签页")
                tab.close()
                
        except Exception as e:
            self.logger.error(f"爬取过程出错: {str(e)}")
            # 保存错误现场
            await self._save_screenshot(browser, 'error')
            await self._save_page_source(browser, 'error')
            await self._update_task_status(
                TaskStatus.FAILED,
                msg=f"爬取失败: {str(e)}",
                error_details={"error": str(e)}
            )
            raise

    async def _checkin(self, browser: Chromium):
        """执行签到流程"""
        tab = await self._create_and_navigate_tab(browser)
        try:
            checkin_result = await self.checkin_handler.perform_checkin(tab)
            await self._save_checkin_data(checkin_result)
        finally:
            self.logger.debug("关闭标签页")
            tab.close()
    
    async def _create_and_navigate_tab(self, browser: Chromium) -> Chromium:
        """创建标签页并导航到用户资料页面"""
        # 创建新标签页
        tab = browser.new_tab()
        browser.activate_tab(tab)
        self.logger.debug("创建新标签页")
        
        # 访问站点主页
        if tab.url != self.base_url:
            self.logger.debug(f"访问站点主页: {self.base_url}")
            tab.get(self.base_url)
        
        # 获取用户资料页面URL
        self.profile_url, self.uid = await self._get_profile_url(tab)

        # 访问用户资料页面
        tab.get(self.profile_url)
        self.logger.debug(f"访问用户资料页面: {self.profile_url}")

        return tab

    async def _get_profile_url(self, tab: Chromium) -> tuple[str, Optional[str]]:
        """获取用户资料页面的URL"""
        # 从配置中获取资料链接选择器
        extract_rules : Optional[ExtractRuleSet] = self.site_setup.site_config.extract_rules
        if not extract_rules:
            raise ValueError(f"站点 {self.site_id} 未配置数据提取规则")
            
        username_rule = next((rule for rule in extract_rules.rules if rule.name == 'username'), None)
        if not username_rule:
            raise ValueError(f"站点 {self.site_id} 未配置用户名选择器")
            
        self.logger.debug("查找用户资料链接")
        profile_element = tab.ele(username_rule.selector)
        if not profile_element:
            self.logger.error("未找到用户资料链接")
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
        full_profile_url = convert_url(self.site_setup.site_config.site_url, profile_url, uid=uid)
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
        extract_rules = self.site_setup.site_config.extract_rules
        if extract_rules and any(rule.name == 'seeding_list' for rule in extract_rules.rules):
            try:
                seeding_data = await self._extract_seeding_data(tab)
                data.update(seeding_data)
            except Exception as e:
                self.logger.error(f"获取统计数据失败: {str(e)}")
        
        return data

    async def _extract_data_with_rules(self, tab: Chromium) -> Dict[str, Any]:
        """根据规则提取数据"""
        data = {}
        extract_rules : Optional[ExtractRuleSet] = self.site_setup.site_config.extract_rules
        
        if not extract_rules:
            self.logger.info("未配置数据提取规则")
            return data
            
        # 按规则分组，先处理不需要预处理的规则
        normal_rules = []
        pre_action_rules = []
        rule: WebElement
        for rule in extract_rules.rules:
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
                    full_url = convert_url(self.site_setup.site_config.site_url, rule.page_url, uid=self.uid)
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
                
            # 根据类���提取值
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

    async def _extract_seeding_data(self, tab: Chromium) -> Dict[str, Any]:
        """提取做种数据"""
        seeding_data = {}
        extract_rules : Optional[ExtractRuleSet] = self.site_setup.site_config.extract_rules
        if not extract_rules:
            return seeding_data

        try:
            # 从extract_rules中获取配置
            rules_dict = {rule.name: rule for rule in extract_rules.rules}
            
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
                    tab.get(convert_url(self.site_setup.site_config.site_url, rules_dict['seeding_list'].page_url, uid=self.uid))
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
                
                # 使用asyncio.gather来并行处理所有的体积转换
                import asyncio
                sizes = await asyncio.gather(*[self._convert_size_to_gb(v) for v in volumes])
                seeding_size = sum(sizes)
                
                seeding_data['seeding_count'] = seeding_count
                self.logger.info(f"提取到做种数量: {seeding_data['seeding_count']}")
                seeding_data['seeding_size'] = f"{seeding_size:.2f} GB"
                self.logger.info(f"提取到总做种体积: {seeding_data['seeding_size']}")
                
        except Exception as e:
            self.logger.error(f"解析做种统计数据失败: {str(e)}")
            self.logger.debug(f"错误详情: {type(e).__name__}")
            
        return seeding_data