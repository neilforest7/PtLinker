import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv

# 添加项目根目录到系统路径
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
env_path = project_root / '.env'
load_dotenv(env_path)

from core.logger import get_logger
from DrissionPage import Chromium, ChromiumOptions
from handlers.checkin import CheckInHandler
from handlers.login import LoginHandler
from schemas.crawlerconfig import CrawlerConfigBase
from schemas.crawlercredential import CrawlerCredentialBase
from schemas.settings import SettingsBase
from schemas.siteconfig import ExtractRuleSet, SiteConfigBase, WebElement
from schemas.sitesetup import SiteSetup
from services.managers.setting_manager import SettingManager

logger = get_logger(__name__)

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
        # 移除多余空格并转换为大写以统一处理
        size_str = size_str.strip().upper()
        
        # 使用正则表达式匹配数字和单位
        size_match = re.search(r'([\d.]+)\s*([TGMK]B|B)?', size_str, re.IGNORECASE)
        if not size_match:
            logger.warning(f"无法解析的数据量格式: {size_str}")
            return 0.0
        
        size_num = float(size_match.group(1))
        # 如果没有匹配到单位，默认为GB
        size_unit = size_match.group(2) if size_match.group(2) else 'GB'
        
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
        
        # 清洗时间格式
        for field in ['join_time', 'last_active']:
            if field in data:
                time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})', data[field])
                if time_match:
                    cleaned_data[field] = time_match.group(1)
        
        # 清洗数据量
        for field in ['upload', 'download', 'seeding_size', 'official_seeding_size']:
            if field in data:
                cleaned_data[field] = await _convert_size_to_gb(data[field])
        
        # 清洗分享率
        if 'ratio' in data:
            ratio_match = re.search(r'([\d.]+)', data['ratio'])
            if ratio_match:
                cleaned_data['ratio'] = float(ratio_match.group(1))
        
        # 清洗数值型数据
        for field in ['bonus', 'seeding_score', 'bonus_per_hour']:
            if field in data:
                value_str = data[field].replace(',', '')
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

async def _extract_seeding_data(tab: Chromium, site_config: SiteConfigBase) -> Dict[str, Any]:
    """提取做种数据"""
    seeding_data = {}
    try:
        # 构建种子列表API URL
        api_url = urljoin(site_config.site_url, "/getusertorrentlistajax.php")
        params = {
            "type": "seeding",
            "ajax": 1
        }
        
        # 获取第一页数据
        logger.info("获取第一页数据...")
        response = await tab.get_async(api_url, params=params)
        
        # 根据响应类型处理数据
        if response.content_type == 'application/json':
            # JSON格式处理
            data = response.json()
            total_size = 0
            seeding_count = 0
            
            if isinstance(data, dict) and 'data' in data:
                for item in data['data']:
                    if 'size' in item:
                        total_size += await _convert_size_to_gb(item['size'])
                    seeding_count += 1
                
                seeding_data['seeding_size'] = total_size
                seeding_data['seeding_count'] = seeding_count
                
        else:
            # HTML格式处理
            rules_dict = {rule.name: rule for rule in site_config.extract_rules.rules}
            if 'seeding_list_table' in rules_dict:
                table = tab.ele(rules_dict['seeding_list_table'].selector)
                if table:
                    rows = table.eles('tag:tr')[1:]  # 跳过表头
                    total_size = 0
                    for row in rows:
                        size_cell = row.ele(f'tag:td', index=rules_dict['seeding_list_table'].index)
                        if size_cell:
                            total_size += await _convert_size_to_gb(size_cell.text)
                    
                    seeding_data['seeding_size'] = total_size
                    seeding_data['seeding_count'] = len(rows)
        
        return seeding_data
        
    except Exception as e:
        logger.error(f"提取做种数据失败: {str(e)}", exc_info=True)
        return seeding_data

async def quick_test(site_id: str, config_path: Optional[str] = None) -> None:
    """快速测试站点配置"""
    try:
        # 1. 读取配置文件
        if not config_path:
            config_path = f"app/services/sites/implementations/{site_id}.json"
        
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            
        # 2. 创建站点配置对象
        # 处理 extract_rules
        if 'extract_rules' in config_data:
            rules = [WebElement(**rule) for rule in config_data['extract_rules']]
            config_data['extract_rules'] = ExtractRuleSet(rules=rules)
            
        site_config = SiteConfigBase(**config_data)
        crawler_config = CrawlerConfigBase(
            site_id=site_id,
            headless=False,
            fresh_login=True,
            use_proxy=False,
            proxy_url=None,
            enabled=True,
            captcha_skip=False  # 不跳过验证码
        )
        
        # 从环境变量获取登录凭证
        username = os.getenv("LOGIN_USERNAME")
        password = os.getenv("LOGIN_PASSWORD")
        if not username or not password:
            raise Exception("请在.env文件中设置 LOGIN_USERNAME 和 LOGIN_PASSWORD")
            
        crawler_credential = CrawlerCredentialBase(
            site_id=site_id,
            enable_manual_cookies=True,
            manual_cookies="c_secure_uid=MjE3NDA%3D; c_secure_pass=dd7d6af525da30b2a7d54bd6bd6c4aa2; c_secure_ssl=eWVhaA%3D%3D; c_secure_tracker_ssl=eWVhaA%3D%3D; c_secure_login=bm9wZQ%3D%3D; cf_clearance=CRo8E190C19ISjUT0mKtH.R.qYUOI5AGqR9dAVTzBRQ-1736714330-1.2.1.1-7d4X0RRyO9gHCHv.BHW4Hvs9kueXY8ua7m8y1b.4vs.ZkYVUaXHsrYX6ErDtcoDhangQH_FIs9s4tqcLlRL5BYvPkmGNUCHZccMecJA7S2DLFutTnPblUomeZfRzf2Xue_01PfFtbgZ5NsDAWsIzqXX3fNqy0Ez75y3eAHyR0pysYz287qMRnBok9QWpLJ7idStLAr3xSP6C6OmtC1bjZVWWyrj31BEHId4JmmWzsczLq45EvloTlDbkW5LOTpJCbLi_Epg7hj0sdaS7PZ6hdH_4q_a9drYdWSE2DQGjQuSdpEL.4GNmz2NeEfSMHHYM9ggfysbg.5wSgo9iGN22uQ",
            username=username,
            password=password,
            authorization=None,
            apikey=None,
            description="测试凭证"
        )
        
        # 初始化设置管理器
        setting_manager = SettingManager.get_instance()
        setting_manager._settings = SettingsBase(
            captcha_api_key=os.getenv('CAPTCHA_API_KEY'),
            captcha_default_method='api',
            captcha_skip_sites='',
            checkin_sites='',
            chrome_path='',
            crawler_max_concurrency=1,
            enable_checkin=True,
            fresh_login=True,
            headless=False,
            log_level='DEBUG',
            storage_path='storage'
        )
        
        site_setup = SiteSetup(
            site_id=site_id,
            site_config=site_config,
            crawler_config=crawler_config,
            crawler_credential=crawler_credential
        )
        
        # 4. 初始化浏览器
        options = ChromiumOptions()
        options.headless(False)  # 使用有头模式便于调试
        options.set_argument('--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        options.set_pref('credentials_enable_service', False)
        options.set_argument('--hide-crash-restore-bubble')
        
        # 4. 创建浏览器实例
        browser = Chromium(options)
        logger.info("浏览器实例创建成功")
        
        # 5. 创建处理器
        login_handler = LoginHandler(site_setup)
        checkin_handler = CheckInHandler(site_setup)
        
        # 6a. 从cookies恢复
        if site_setup.crawler_credential.enable_manual_cookies:
            cookies = site_setup.crawler_credential.manual_cookies
            if cookies:
                # 获取域名
                domain = urlparse(site_config.site_url).netloc
                # 解析并设置cookies
                cookies_list = parse_cookies(cookies, domain)
                browser.set.cookies(cookies_list)
                browser.latest_tab.get(site_config.site_url)
                logger.info("从cookies恢复成功")
            else:
                raise Exception("cookies格式错误或为空")
        
        # 6b. 执行登录
        else:
            logger.info("开始执行登录")
            try:
                login_success = await login_handler.perform_login(browser)
                if not login_success:
                    raise Exception("登录失败")
                logger.info("登录成功")
            except Exception as e:
                logger.error(f"登录失败: {str(e)}")
                raise
        
        # 7. 提取数据
        data = {}
        try:
            # 获取用户资料页面URL
            tab = browser.latest_tab
            username_element = tab.ele(site_config.extract_rules.rules[0].selector)
            if not username_element:
                raise Exception("未找到用户名元素")
            
            profile_url = username_element.attr('href')
            if not profile_url:
                raise Exception("未找到用户资料URL")
                
            # 访问用户资料页面
            if not profile_url.startswith('http'):
                profile_url = site_config.site_url + profile_url
            tab.get(profile_url)
            logger.info(f"访问用户资料页面: {profile_url}")
            
            # 提取数据
            for rule in site_config.extract_rules.rules:
                try:
                    if rule.need_pre_action:
                        if rule.pre_action_type == 'goto' and rule.page_url:
                            full_url = urljoin(site_config.site_url, rule.page_url)
                            logger.debug(f"访问页面: {full_url}")
                            tab.get(full_url)
                        # elif rule.pre_action_type == 'click':
                        #     element = tab.ele(rule.selector)
                        #     if element:
                        #         element.click()
                        #         logger.debug(f"点击元素: {rule.selector}")
                                
                    element = tab.ele(rule.selector)
                    if element:
                        if rule.location == 'next':
                            value = element.next().text
                        elif rule.location == 'next-child' and rule.second_selector:
                            value = element.next().child(rule.second_selector).text
                        elif rule.location == 'parent':
                            value = element.parent().text
                        elif rule.location == 'parent-child' and rule.second_selector:
                            value = element.parent().child(rule.second_selector).text
                        elif rule.location == 'east' and rule.second_selector:
                            value = element.east(rule.second_selector).text
                        else:
                            value = element.text
                        
                        if value:
                            data[rule.name] = value.strip()
                            logger.info(f"通过 {rule.location}+{rule.selector} 提取到 {rule.name}: {value.strip()}")
                except Exception as e:
                    logger.error(f"提取 {rule.name} 时出错: {str(e)}")
            
            # 提取做种数据
            seeding_data = await _extract_seeding_data(tab, site_config)
            data.update(seeding_data)
            
            # 清洗数据
            data = await _clean_data(data)
                    
            # 8. 执行签到
            if site_config.checkin_config:
                logger.info("开始执行签到")
                checkin_result = await checkin_handler.perform_checkin(browser)
                logger.info(f"签到结果: {checkin_result}")
                
        except Exception as e:
            logger.error(f"数据提取失败: {str(e)}")
            raise
            
        # 9. 输出结果
        logger.info("测试完成，输出结果:")
        logger.info(json.dumps(data, ensure_ascii=False, indent=2))
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        if browser:
            # 保存错误截图
            try:
                os.makedirs("storage", exist_ok=True)  # 确保目录存在
                screenshot_path = f"storage/error_{site_id}.png"
                browser.latest_tab.get_screenshot(screenshot_path)
                logger.info(f"错误截图已保存: {screenshot_path}")
            except Exception as se:
                logger.error(f"保存截图失败: {str(se)}")
        raise
        
    finally:
        if browser:
            try:
                browser.quit()
                logger.info("浏览器已关闭")
            except:
                pass

if __name__ == "__main__":
    site_id = "hhan"  # 替换为要测试的站点ID
    asyncio.run(quick_test(site_id)) 