import re
from typing import Any, Dict
from urllib.parse import urljoin

from config.sites import EXTRACT_RULES
from DrissionPage import Chromium
from utils.logger import get_logger, setup_logger

from ..base.base_crawler import BaseCrawler


class QingWaptCrawler(BaseCrawler):
    def __init__(self, task_config: Dict[str, Any]):
        super().__init__(task_config)
        self.base_url = task_config['site_url'][0]
        setup_logger()
        self.logger = get_logger(name=__name__, site_id="qingwapt")
        self.extract_rules = EXTRACT_RULES.get('qingwapt', [])
        if not self.extract_rules:
            self.logger.warning("未找到qingwapt的数据提取规则")

    def _get_site_id(self) -> str:
        return 'qingwapt'

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
            seeding_btn = tab.ele('@href^javascript: getusertorrentlistajax',index=2)
            if not seeding_btn:
                self.logger.warning("未找到做种统计按钮")
                return stats
            self.logger.debug(f"找到做种统计按钮{seeding_btn}，开始点击")
            seeding_btn.click()
            
            # 使用基类方法提取所有页面的体积数据
            volumes = await self._extract_seeding_volumes(
                tab,
                container_selector="#ka1",
                table_selector="@tag()=table",  # 表格选择器
                pagination_selector='@class=nexus-pagination',
                volume_selector_index= 4  # 体积列选择器（第5列）
            )
            
            # 统计做种数量和总体积
            seeding_count = len(volumes)
            seeding_size = sum(self._convert_size_to_gb(v) for v in volumes)
                        
            stats['seeding_count'] = seeding_count
            self.logger.info(f"提取到做种数量: {stats['seeding_count']}")
            stats['seeding_size'] = f"{seeding_size:.2f} GB"
            self.logger.info(f"提取到总做种体积(GB): {stats['seeding_size']}")
            
        except Exception as e:
            self.logger.error(f"解析做种统计数据失败: {str(e)}")
            self.logger.debug(f"错误详情: {type(e).__name__}")
            self.logger.debug(f"错误堆栈: ", exc_info=True)
            
        return stats