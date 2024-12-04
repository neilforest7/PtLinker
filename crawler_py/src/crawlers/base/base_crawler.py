import json
import os
import re
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from DrissionPage import Chromium, ChromiumOptions
from handlers.checkin import CheckInHandler
from handlers.login import LoginHandler
from models.crawler import CrawlerTaskConfig, ExtractRuleSet
from models.storage import LoginState
from storage.browser_state_manager import BrowserStateManager
from utils.logger import get_logger, setup_logger
from utils.url import get_site_domain


class BaseCrawler(ABC):
    def __init__(self, task_config: Dict[str, Any], browser_manager: Optional[BrowserStateManager] = None):
        # 1. 基础配置初始化
        self.task_config = CrawlerTaskConfig(**task_config)
        self.storage_dir = Path(os.getenv('STORAGE_PATH', 'storage'))
        
        # 2. 获取site_id（这必须在logger初始化之前）
        self.site_id = self._get_site_id()
        
        # 3. 设置日志
        setup_logger()
        self.logger = get_logger(name=__name__, site_id=self.site_id)
        
        # 4. 其他组件初始化
        self.base_url = self.task_config.site_url[0]
        self.browser_manager = browser_manager
        self.site_domain = get_site_domain(self.task_config, self.logger)
        
        # 5. 存储路径初始化
        self.task_storage_path = self.storage_dir / 'tasks' / self.site_id / str(task_config['task_id'])
        self.task_storage_path.mkdir(parents=True, exist_ok=True)
        
        # 6. 处理器初始化
        self.login_handler = LoginHandler(self.task_config, self.browser_manager)
        self.checkin_handler = CheckInHandler(self.task_config)
        
        # 7. 配置转换
        self.extract_rules = self.task_config.extract_rules
        if not self.extract_rules:
            self.logger.warning(f"{self.site_id} 未配置数据提取规则")
        
        # 8. 浏览器初始化
        self.browser: Optional[Chromium] = None
        
    async def start(self):
        """启动爬虫"""
        try:
            # 初始化浏览器
            await self._init_browser()
            
            # 执行具体的爬取任务
            await self._crawl(self.browser)
            await self._checkin(self.browser)
            
        except Exception as e:
            self.logger.error(f"爬虫运行失败: {str(e)}")
            self.logger.debug("错误详情:", exc_info=True)
            raise
        finally:
            # 清理资源
            await self._cleanup()

    async def _init_browser(self) -> None:
        """初始化浏览器"""
        try:
            # 创建浏览器实例
            browser = await self._create_browser()
            self.logger.debug("浏览器实例创建成功")
            
            MAX_RETRY = 3
            RETRY_COUNT = 0
            while RETRY_COUNT < MAX_RETRY:
                if RETRY_COUNT > 0:
                    self.logger.info(f"第 {RETRY_COUNT} 次尝试恢复登录状态")
                
                # 检查登录状态
                if not (os.getenv('FRESH_LOGIN', 'false').lower() == 'true'):
                    if await self._restore_browser_state(browser) and RETRY_COUNT < 2:
                        tab = browser.new_tab()
                        tab.set.load_mode.eager()
                        tab.get(self.base_url)
                        # 检查登录状态
                        is_logged_in = await self.login_handler.check_login(browser)
                        if not is_logged_in:
                            login_success = await self.login_handler.perform_login(browser, self.task_config.login_config)
                            if not login_success:
                                self.logger.error(f"第 {RETRY_COUNT+1} 次登录失败，清除登录状态并重新登录...")
                                await self.browser_manager.clear_state(self.site_id)
                                RETRY_COUNT += 1
                                continue
                            else:
                                self.logger.info("登录成功")
                                break
                        else:
                            self.logger.info("恢复登录状态成功")
                            break
                    else:
                        self.logger.info("未加载到登录状态，开始登录流程")
                        # 执行登录
                        login_success = await self.login_handler.perform_login(browser, self.task_config.login_config)
                        if not login_success:
                            self.logger.error(f"第 {RETRY_COUNT+1} 次登录失败，清除登录状态并重新登录...")
                            await self.browser_manager.clear_state(self.site_id)
                            RETRY_COUNT += 1
                            continue
                        else:
                            self.logger.info("登录成功")
                            break
                else:
                    self.logger.info("环境变量强制重新登录")
                    login_success = await self.login_handler.perform_login(browser, self.task_config.login_config)
                    if not login_success:
                        self.logger.error(f"第 {RETRY_COUNT+1} 次登录失败，清除登录状态并重新登录...")
                        await self.browser_manager.clear_state(self.site_id)
                        RETRY_COUNT += 1
                        continue
                    else:
                        self.logger.info("登录成功")
                        break
                
            # 保存浏览器实例
            self.browser = browser
            
        except Exception as e:
            self.logger.error(f"浏览器初始化失败: {str(e)}")
            await self._cleanup()
            raise
        
    async def _create_browser(self) -> Chromium:
        """创建浏览器实例"""
        try:
            # 创建浏览器选项
            if os.getenv('HEADLESS', 'false').lower() == 'true':
                options = ChromiumOptions().headless().auto_port()
            else:
                options = ChromiumOptions().auto_port()
            
            # 设置User-Agent
            options.set_argument('--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0')
            
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
            ]
            
            # 添加所有参数
            for arg in arguments:
                options.set_argument(arg)
            
            # 创建浏览器实例
            browser = Chromium(options)
            self.logger.debug(f"浏览器实例创建成功")
            return browser
            
        except Exception as e:
            self.logger.error(f"创建浏览器实例失败: {str(e)}")
            self.logger.debug("错误详情:", exc_info=True)
            raise
                
    async def _cleanup(self) -> None:
        """清理资源"""
        try:
            if hasattr(self, 'browser') and self.browser:
                # 只有在登录成功的情况下才保存浏览器状态
                if await self.login_handler.check_login(self.browser):
                    await self._save_browser_state(self.browser)
                # 关闭浏览器
                try:
                    await self.browser.quit()
                    self.logger.info("浏览器已关闭")
                except:
                    pass
        except Exception as e:
            self.logger.error(f"清理资源时发生错误: {str(e)}")
            self.logger.debug("错误详情:", exc_info=True)
            # 确保浏览器被关闭
            if hasattr(self, 'browser') and self.browser:
                try:
                    await self.browser.quit()
                except:
                    pass
            raise
        
    async def _save_browser_state(self, browser: Chromium) -> None:
        """保存浏览器状态"""
        try:
            # 获取当前标签页
            tab = browser.latest_tab
            if not tab:
                self.logger.warning("未找到活动标签页")
                return
            
            # 获取cookies
            try:
                raw_cookies = tab.cookies(all_domains=False, all_info=True)
                cookies = {}
                self.logger.info(f"获取到 {len(raw_cookies)} 个cookies")
                for cookie in raw_cookies:
                    cookies[cookie['name']] = cookie
                self.logger.debug(f"处理后的cookies数量: {len(cookies)}")
            except Exception as e:
                self.logger.error(f"获取cookies失败: {str(e)}")
                cookies = {}
            
            # 获取local storage
            try:
                local_storage: dict = tab.local_storage()
                if not local_storage:
                    self.logger.debug(f"没有获取到localStorage项")
                else:
                    self.logger.debug(f"获取到 {len(local_storage)} 个localStorage项")
                    
            except Exception as e:
                self.logger.error(f"获取localStorage失败: {str(e)}")
                local_storage = {}
                
            # 获取session storage
            try:
                session_storage: dict = tab.session_storage()
                if not session_storage:
                    self.logger.debug(f"没有获取到sessionStorage项")
                else:
                    session_storage = dict(session_storage)
                    self.logger.debug(f"获取到 {len(session_storage)} 个sessionStorage项")

            except Exception as e:
                self.logger.error(f"获取sessionStorage失败: {str(e)}")
                session_storage = {}
            
            # 一次性更新所有状态
            success = await self.browser_manager._batch_update_state(
                self.site_id,
                cookies=cookies,
                local_storage=local_storage,
                session_storage=session_storage
            )
            
            if success:
                self.logger.info("浏览器状态保存完成")
            else:
                self.logger.error("浏览器状态保存失败")
            
        except Exception as e:
            self.logger.error(f"保存浏览器状态失败: {str(e)}")
            self.logger.debug("错误详情:", exc_info=True)

    async def _restore_browser_state(self, browser: Chromium) -> bool:
        """恢复浏览器状态
        
        Args:
            browser: 浏览器实例
            
        Returns:
            bool: 状态恢复是否成功
        """
        try:
            # 获取浏览器状态
            browser_state = await self.browser_manager.restore_state(self.site_id)
            if not browser_state:
                self.logger.info("未找到浏览器状态，将使用新会话")
                return False
                
            # 获取当前标签页
            tab = browser.latest_tab
            if not tab:
                self.logger.warning("未找到活动标签页")
                return False
                
            # 恢复cookies
            if browser_state.cookies:
                self.logger.debug(f"正在恢复 {len(browser_state.cookies)} 个cookies")
                for name, cookie_data in browser_state.cookies.items():
                    try:
                        if isinstance(cookie_data, dict):
                            browser.set.cookies(cookie_data)
                    except Exception as e:
                        self.logger.error(f"设置cookie {name} 失败: {str(e)}")
                        continue
            
            # 恢复local storage
            if browser_state.local_storage:
                self.logger.debug(f"正在恢复 {len(browser_state.local_storage)} 个localStorage项")
                for key, value in browser_state.local_storage.items():
                    try:
                        js_code = f'localStorage.setItem("{key}", "{value}")'
                        tab.run_js(js_code)
                    except Exception as e:
                        self.logger.error(f"设置localStorage {key} 失败: {str(e)}")
                        continue
            
            # 恢复session storage
            if browser_state.session_storage:
                self.logger.debug(f"正在恢复 {len(browser_state.session_storage)} 个sessionStorage项")
                for key, value in browser_state.session_storage.items():
                    try:
                        js_code = f'sessionStorage.setItem("{key}", "{value}")'
                        tab.run_js(js_code)
                    except Exception as e:
                        self.logger.error(f"设置sessionStorage {key} 失败: {str(e)}")
                        continue
            
            self.logger.info("浏览器状态恢复完成")
            return True
            
        except Exception as e:
            self.logger.error(f"恢复浏览器状态失败: {str(e)}")
            self.logger.debug("错误详情:", exc_info=True)
            return False

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

    def _convert_size_to_gb(self, size_str: str) -> float:
        """
        将字符串形式的大小转换为GB为单位的浮点数
        
        Args:
            size_str: 大小字符串，如 "1.5 TB", "800 MB", "2.3 GB", "1.5"
            
        Returns:
            float: 转换后的GB值
            
        Examples:
            >>> _convert_size_to_gb("1.5 TB")  # 返回 1536.0
            >>> _convert_size_to_gb("500 MB")  # 返回 0.48828125
            >>> _convert_size_to_gb("2.3 GB")  # 返回 2.3
        """
        try:
            # 移除多余空格并转换为大写以统一处理
            size_str = size_str.strip().upper()
            
            # 使用正则表达式匹配数字和单位
            size_match = re.search(r'([\d.]+)\s*([TGMK]B|B)?', size_str, re.IGNORECASE)
            if not size_match:
                self.logger.warning(f"无法解析的数据量格式: {size_str}")
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
            self.logger.error(f"转换数据量失败: {size_str}, 错误: {str(e)}")
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
            # 如果没有分享率数据，则根据上传下载计算分享率
            elif cleaned_data.get('upload', None) and cleaned_data.get('download', None):
                cleaned_data['ratio'] = cleaned_data.get('upload', None)/cleaned_data.get('download', None)
            
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
            
            # 清洗HR数据（转换为int）
            if 'hr_count' in data:
                hr_match = re.search(r'(\d+)', data['hr_count'])
                if hr_match:
                    cleaned_data['hr_count'] = int(hr_match.group(1))
            
            if 'bonus_per_hour' in data:
                bph_match = re.search(r'([\d.]+)', data['bonus_per_hour'])
                if bph_match:
                    cleaned_data['bonus_per_hour'] = float(bph_match.group(1))
            
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
    async def _crawl(self, browser: Chromium):
        """爬取数据的主要逻辑"""
        pass
    
    @abstractmethod
    async def _checkin(self, browser: Chromium):
        """执行签到"""
        pass
            
    @abstractmethod
    def _get_site_id(self) -> str:
        """返回站点ID"""
        pass
