import re
from typing import Any, Dict
from urllib.parse import urljoin

from config.sites import EXTRACT_RULES
from DrissionPage import Chromium
from loguru import logger

from ..base.base_crawler import BaseCrawler


class OurBitsCrawler(BaseCrawler):
    def __init__(self, task_config: Dict[str, Any]):
        super().__init__(task_config)
        self.base_url = task_config['start_urls'][0]
        self.logger = logger.bind(site_id="ourbits")
        self.extract_rules = EXTRACT_RULES.get('ourbits', [])
        if not self.extract_rules:
            self.logger.warning("未找到ourbits的数据提取规则")

    def _get_site_id(self) -> str:
        return 'ourbits'

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
            
            # 获取用户资料页面URL
            self.logger.debug("查找用户资料链接")
            profile_element = tab.ele('@class=User_Name')
            if not profile_element:
                raise Exception("未找到用户资料链接")
                
            profile_url = profile_element.attr('href')
            if not profile_url:
                raise Exception("未找到用户资料URL")
            
            # 提取用户ID
            uid_match = re.search(r'id=(\d+)', profile_url)
            if uid_match:
                uid = uid_match.group(1)
                self.logger.debug(f"提取到用户ID: {uid}")
            else:
                self.logger.warning("未能从URL中提取用户ID")
                uid = None
                
            # 确保使用完整URL
            full_profile_url = urljoin(self.base_url, profile_url)
            self.logger.debug(f"访问用户资料页面: {full_profile_url}")

            # 访问用户资料页面
            tab.get(full_profile_url)

            # 提取基本数据
            self.logger.info("开始提取用户基本数据")
            data = await self._extract_data_with_rules(browser, self.extract_rules)
            
            # 添加用户ID到数据中
            if uid:
                data['uid'] = uid
            
            # 获取做种统计数据
            try:
                seeding_stats = await self._extract_seeding_stats(browser)
                data.update(seeding_stats)
            except Exception as e:
                self.logger.error(f"获取做种统计失败: {str(e)}")

            # 清洗数据
            cleaned_data = self._clean_data(data)
            
            # 保存数据
            self.logger.debug("保存提取的数据")
            await self._save_data(cleaned_data)
            
            # 关闭标签页
            self.logger.debug("关闭标签页")
            tab.close()
            
        except Exception as e:
            self.logger.error(f"爬取过程出错: {str(e)}")
            # 保存错误现场
            await self._save_screenshot(browser, 'error')
            await self._save_page_source(browser, 'error')
            raise

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
            seeding_btn = tab.ele('@href^javascript: getusertorrentlistajax',index=3)
            if not seeding_btn:
                self.logger.warning("未找到做种统计按钮")
                return stats
            self.logger.debug(f"找到做种统计按钮{seeding_btn}，开始点击")
            seeding_btn.click()

            # 获取做种列表容器
            seeding_container = tab.ele('#ka1').ele('@tag()=table')
            if not seeding_container:
                self.logger.warning("未找到做种统计容器")
                return stats
                
            seeding_rows = seeding_container.eles('@tag()=tr')
            if not seeding_rows:
                self.logger.warning("未找到做种统计行")
                return stats
                
            seeding_count = len(seeding_rows) - 1
            seeding_size = 0.0
            
            for index, row in enumerate(seeding_rows):
                if index == 0:  # 跳过表头
                    continue
                t_size = row.ele('@tag()=td', index=3)
                if t_size:
                    size_text = t_size.text.strip().replace('\n', '')
                    self.logger.debug(f"提取到做种体积文本: {size_text}")
                    
                    # 使用正则表达式匹配数字和单位
                    size_match = re.search(r'([\d.]+)\s*(TB|GB|MB|KB|B)', size_text, re.IGNORECASE)
                    self.logger.debug(f"匹配结果: {size_match}")
                    if size_match:
                        size_gb = self._convert_size_to_gb(size_text)
                        self.logger.debug(f"转换后的大小(GB): {size_gb}")
                        seeding_size += size_gb
                    else:
                        self.logger.warning(f"无法解析大小文本: {size_text}")
                        
            stats['seeding_count'] = seeding_count
            self.logger.info(f"提取到做种数量: {stats['seeding_count']}")
            stats['seeding_size'] = f"{seeding_size:.2f} GB"
            self.logger.info(f"提取到总做种体积(GB): {stats['seeding_size']}")
            
        except Exception as e:
            self.logger.error(f"解析做种统计数据失败: {str(e)}")
            self.logger.debug(f"错误详情: {type(e).__name__}")
            self.logger.debug(f"错误堆栈: ", exc_info=True)
            
        return stats