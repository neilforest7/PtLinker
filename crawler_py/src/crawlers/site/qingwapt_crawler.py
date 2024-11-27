import os
from typing import Dict, Any
from ..base.base_crawler import BaseCrawler
from playwright.sync_api import Page
import re
from datetime import datetime

class QingWaptCrawler(BaseCrawler):
    def __init__(self, task_config: Dict[str, Any]):
        super().__init__(task_config)

    def _get_site_id(self) -> str:
        return 'qingwapt'

    async def _check_login(self) -> bool:
        """检查是否已登录"""
        try:
            username_element = await self.page.query_selector('a.User_Name')
            if username_element:
                username = await username_element.text_content()
                return username == os.getenv('LOGIN_USERNAME')
            return False
        except Exception:
            return False

    async def _handle_login(self):
        """处理登录流程"""
        await self.page.goto('https://www.qingwapt.com/login.php')
        
        # 填写登录表单
        await self.page.fill('input.textbox[name="username"][type="text"]', os.getenv('LOGIN_USERNAME', ''))
        await self.page.fill('input.textbox[name="password"][type="password"]', os.getenv('LOGIN_PASSWORD', ''))
        
        # 提交表单
        await self.page.click('input[type="submit"]')
        await self.page.wait_for_load_state('networkidle')

        # 检查登录结果
        if await self._check_login():
            await self._save_cookies()
        else:
            raise Exception("登录失败")

    async def _crawl(self):
        """爬取数据的主要逻辑"""
        # 访问用户主页
        await self.page.goto('https://www.qingwapt.com')
        
        # 获取用户资料页面URL
        profile_element = await self.page.query_selector('a.User_Name')
        if not profile_element:
            raise Exception("未找到用户资料链接")
            
        profile_url = await profile_element.get_attribute('href')
        if not profile_url:
            raise Exception("未找到用户资料URL")

        # 访问用户资料页面
        await self.page.goto(profile_url)
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
            print(f"获取做种统计失败: {str(e)}")

        await self._save_data(data)

    async def _extract_user_data(self) -> Dict[str, Any]:
        """提取用户数据"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'url': self.page.url
        }

        # 提取UID
        uid_element = await self.page.query_selector('td.rowhead:has-text("用户ID/UID") + td.rowfollow')
        if uid_element:
            uid_text = await uid_element.text_content()
            uid_match = re.search(r'(\d+)', uid_text or '')
            if uid_match:
                data['uid'] = int(uid_match[1])

        # 提取分享率
        ratio_element = await self.page.query_selector('td.rowfollow')
        if ratio_element:
            ratio_text = await ratio_element.text_content()
            ratio_match = re.search(r'分享率.*?(\d+\.?\d*)', ratio_text or '')
            if ratio_match:
                data['ratio'] = float(ratio_match[1])

        # 提取上传下载量
        upload_element = await self.page.query_selector('td.rowfollow')
        if upload_element:
            upload_text = await upload_element.text_content()
            data['uploaded'] = self._parse_size(upload_text or '')

        download_element = await self.page.query_selector('td.rowfollow')
        if download_element:
            download_text = await download_element.text_content()
            data['downloaded'] = self._parse_size(download_text or '')

        # 提取当前做种和下载数
        seeding_element = await self.page.query_selector('td.rowfollow')
        if seeding_element:
            seeding_text = await seeding_element.text_content()
            seeding_match = re.search(r'当前做种.*?(\d+)', seeding_text or '')
            if seeding_match:
                data['seeding'] = int(seeding_match[1])

        leeching_element = await self.page.query_selector('td.rowfollow')
        if leeching_element:
            leeching_text = await leeching_element.text_content()
            leeching_match = re.search(r'当前下载.*?(\d+)', leeching_text or '')
            if leeching_match:
                data['leeching'] = int(leeching_match[1])

        return data

    async def _extract_seeding_stats(self) -> Dict[str, Any]:
        """提取做种统计数据"""
        stats = {}
        
        seeding_element = await self.page.query_selector('#ka1[data-type="seeding"]')
        if seeding_element:
            text = await seeding_element.text_content()
            
            # 提取做种数量
            count_match = re.search(r'(\d+)\s*条记录', text or '')
            if count_match:
                stats['seeding_count'] = int(count_match[1])
            
            # 提取做种总大小
            size_match = re.search(r'总大小：([\d.]+)\s*(TB|GB|MB)', text or '')
            if size_match:
                size = float(size_match[1])
                unit = size_match[2]
                stats['seeding_size'] = self._convert_to_gb(size, unit)

        return stats

    def _parse_size(self, text: str) -> float:
        """解析大小字符串为GB为单位的浮点数"""
        match = re.search(r'(\d+\.?\d*)\s*(TB|GB|MB|KB)', text)
        if not match:
            return 0.0
        
        size, unit = float(match.group(1)), match.group(2)
        return self._convert_to_gb(size, unit)

    def _convert_to_gb(self, size: float, unit: str) -> float:
        """将不同单位的大小转换为GB"""
        if unit == 'TB':
            return size * 1024
        elif unit == 'GB':
            return size
        elif unit == 'MB':
            return size / 1024
        elif unit == 'KB':
            return size / (1024 * 1024)
        return size 