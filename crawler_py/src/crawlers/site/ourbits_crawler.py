import os
from typing import Dict, Any
from urllib.parse import urljoin
from ..base.base_crawler import BaseCrawler
from playwright.async_api import Page
import re
from datetime import datetime
from models.crawler import LoginConfig

class OurBitsCrawler(BaseCrawler):
    def __init__(self, task_config: Dict[str, Any]):
        super().__init__(task_config)
        self.base_url = task_config['start_urls'][0]

    def _get_site_id(self) -> str:
        return 'ourbits'

    async def _check_login(self) -> bool:
        """检查是否已登录"""
        try:
            username_element = await self.page.query_selector('a.User_Name')
            if username_element:
                username = await username_element.text_content()
                return username == self.task_config.username
            return False
        except Exception:
            return False

    async def _crawl(self):
        """爬取数据的主要逻辑"""
        try:
            # 访问用户主页
            await self.page.goto(self.base_url)
            
            # 获取用户资料页面URL
            profile_element = await self.page.query_selector('a.User_Name')
            if not profile_element:
                raise Exception("未找到用户资料链接")
                
            profile_url = await profile_element.get_attribute('href')
            if not profile_url:
                raise Exception("未找到用户资料URL")
                
            # 确保使用完整URL
            full_profile_url = urljoin(self.base_url, profile_url)
            self.logger.debug(f"访问用户资料页面: {full_profile_url}")

            # 访问用户资料页面
            await self.page.goto(full_profile_url)
            await self.page.wait_for_load_state('networkidle')

            # 提取基本数据
            data = await self._extract_user_data()
            
            # 获取做种统计数据
            try:
                # 点击显示做种统计按钮
                await self.page.click('a[href*="getusertorrentlistajax"][href*="seeding"]')
                
                # 等待数据加载
                await self.page.wait_for_selector('#ka1[data-type="seeding"]', timeout=10000)
                
                # 提取做种统计
                seeding_stats = await self._extract_seeding_stats()
                data.update(seeding_stats)
            except Exception as e:
                self.logger.error(f"获取做种统计失败: {str(e)}")

            await self._save_data(data)
            
        except Exception as e:
            self.logger.error(f"爬取过程出错: {str(e)}")
            raise

    async def _extract_user_data(self) -> Dict[str, Any]:
        """提取用户基本数据"""
        data = {}
        
        # 提取用户名
        username_element = await self.page.query_selector('a.User_Name')
        if username_element:
            data['username'] = await username_element.text_content()
            
        # 提取用户等级
        class_element = await self.page.query_selector('img[alt*="class="]')
        if class_element:
            alt_text = await class_element.get_attribute('alt')
            if alt_text:
                class_match = re.search(r'class=(.*?)(?:\s|$)', alt_text)
                if class_match:
                    data['user_class'] = class_match.group(1)
                    
        # 提取加入时间
        join_time_element = await self.page.query_selector('td:has-text("加入时间") + td')
        if join_time_element:
            data['join_time'] = await join_time_element.text_content()
            
        # 提取上传下载量
        upload_element = await self.page.query_selector('td:has-text("上传量") + td')
        if upload_element:
            data['upload'] = await upload_element.text_content()
            
        download_element = await self.page.query_selector('td:has-text("下载量") + td')
        if download_element:
            data['download'] = await download_element.text_content()
            
        return data

    async def _extract_seeding_stats(self) -> Dict[str, Any]:
        """提取做种统计数据"""
        stats = {}
        
        # 提取做种数量
        seeding_count_element = await self.page.query_selector('#ka1[data-type="seeding"] .td_title span')
        if seeding_count_element:
            count_text = await seeding_count_element.text_content()
            count_match = re.search(r'\d+', count_text)
            if count_match:
                stats['seeding_count'] = int(count_match.group())
                
        # 提取做种体积
        seeding_size_element = await self.page.query_selector('#ka1[data-type="seeding"] .td_size')
        if seeding_size_element:
            stats['seeding_size'] = await seeding_size_element.text_content()
            
        return stats