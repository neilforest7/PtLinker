import json
import os
import re
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from core.logger import get_logger, setup_logger
from DrissionPage import Chromium, ChromiumOptions
from handlers.checkin import CheckInHandler
from handlers.login import LoginHandler
from schemas.browserstate import BrowserState
from schemas.result import ResultCreate
from schemas.sitesetup import SiteSetup
from services.managers.browserstate_manager import BrowserStateManager
from services.managers.result_manager import ResultManager
from services.managers.setting_manager import SettingManager
from services.managers.task_status_manager import task_status_manager
from sqlalchemy.ext.asyncio import AsyncSession
from models.models import TaskStatus

CheckInResult = Literal["not_set", "already", "success", "failed"]

class BaseCrawler(ABC):
    def __init__(self, site_setup: SiteSetup, task_id: str):
        # 1. 基础配置初始化
        self.site_setup = site_setup
        self.site_id = site_setup.site_id
        self.task_id = task_id
        self.db: Optional[AsyncSession] = None
        
        # 2. 设置日志
        # setup_logger()
        self.logger = get_logger(name=__name__, site_id=self.site_id)
        
        # 3. 其他组件初始化
        if not site_setup.site_config or not site_setup.site_config.site_url:
            raise ValueError(f"站点 {self.site_id} 缺少基础配置或URL配置")
        self.base_url = site_setup.site_config.site_url
        self.storage_dir = Path(os.getenv('STORAGE_PATH', 'storage'))
        
        # 4. 存储路径初始化
        self.task_storage_path = self.storage_dir / 'tasks' / self.site_id
        self.task_storage_path.mkdir(parents=True, exist_ok=True)
        
        # 5. 处理器初始化
        self.login_handler = LoginHandler(self.site_setup)
        self.checkin_handler = CheckInHandler(self.site_setup)
        
        # 6. 结果管理器
        self.result_manager = ResultManager()
        
        # 7. 浏览器初始化
        self.browser: Optional[Chromium] = None
            
    async def set_db(self, db: AsyncSession):
        """设置数据库会话"""
        self.db = db

    async def _update_task_status(
        self,
        status: TaskStatus,
        msg: Optional[str] = None,
        error_details: Optional[Dict] = None,
        completed_at: Optional[datetime] = None
    ) -> None:
        """更新任务状态"""
        if not self.db:
            self.logger.error("数据库会话未初始化，无法更新任务状态")
            return
            
        await task_status_manager.update_task_status(
            db=self.db,
            task_id=self.task_id,
            status=status,
            msg=msg,
            completed_at=completed_at,
            error_details=error_details,
            site_id=self.site_id
        )

    async def start(self):
        """启动爬虫"""
        try:
            # 初始化浏览器
            init_result = await self._init_browser()
            
            # 执行具体的爬取任务
            if init_result:
                await self._crawl(self.browser)
                await self._checkin(self.browser)
            else:
                await self._update_task_status(TaskStatus.FAILED, "初始化浏览器失败，跳过爬取")
                self.logger.warning(f"{self.site_id} 初始化浏览器失败，跳过爬取")
        except Exception as e:
            self.logger.error(f"爬虫运行失败: {str(e)}")
            self.logger.debug("错误详情:", exc_info=True)
            await self._update_task_status(TaskStatus.FAILED, "爬虫运行失败", error_details=e)
            raise
        finally:
            # 清理资源
            await self._cleanup()

    async def _init_browser(self) -> None:
        """初始化浏览器"""
        try:
            # 创建浏览器实例
            browser = await self._create_browser()
            tab = browser.latest_tab
            # 获取登录重试配置
            _MAX_RETRY = await SettingManager.get_instance().get_setting('login_max_retry')
            self.logger.info(f"全局登录最大重试次数: {_MAX_RETRY}")
            MAX_RETRY = self.site_setup.get_crawler_config('login_max_retry', _MAX_RETRY)
            self.logger.info(f"站点登录最大重试次数: {MAX_RETRY}")
            RETRY_COUNT = 0
            
            while RETRY_COUNT < MAX_RETRY:
                if RETRY_COUNT > 0:
                    self.logger.info(f"第 {RETRY_COUNT} 次尝试恢复登录状态")
                
                # 检查是否需要强制重新登录
                if not self.site_setup.crawler_config.fresh_login:
                    if self.site_setup.browser_state:
                        if self.site_setup.browser_state.cookies:
                            self.logger.info("找到站点cookies")
                            if await self._restore_browser_state(browser):
                                tab.get(self.site_setup.site_config.site_url)
                                if await self.login_handler.check_login(browser):
                                    self.logger.info("恢复登录状态成功")
                                    await self._save_browser_state(browser)
                                    # 更新登录状态
                                    # self.site_setup.crawler = self.site_setup.crawler.model_copy(
                                    #     update={
                                    #         'is_logged_in': True,
                                    #         'last_login_time': datetime.now()
                                    #     }
                                    # )
                                    self.browser = browser
                                    return True
                    else:
                        self.logger.info("未找到站点浏览器状态，将使用新会话")
                
                # 执行登录
                self.logger.info("开始执行登录")
                login_success = await self.login_handler.perform_login(browser)
                
                if login_success:
                    self.logger.info("登录成功")
                    # 更新登录状态
                    # self.site_setup.crawler = self.site_setup.crawler.model_copy(
                    #     update={
                    #         'is_logged_in': True,
                    #         'last_login_time': datetime.now()
                    #     }
                    # )
                    self.browser = browser
                    await self._save_browser_state(browser)
                    return True
                else:
                    self.logger.error(f"第 {RETRY_COUNT+1} 次登录失败")
                    # await self._clear_browser_state()
                    RETRY_COUNT += 1
                    
            return False
        except Exception as e:
            self.logger.error(f"浏览器初始化失败: {str(e)}")
            await self._cleanup()
            return False
            
        
    async def _create_browser(self) -> Chromium:
        """创建浏览器实例"""
        try:
            # 创建浏览器选项
            options = ChromiumOptions()
            
            # 设置无头模式
            if self.site_setup.crawler_config.headless:
                options.headless().auto_port()
            else:
                options.auto_port()
            
            # 设置代理
            if self.site_setup.crawler_config.use_proxy:
                if proxy_url := self.site_setup.crawler_config.proxy_url:
                    options.set_proxy(proxy_url)
                    self.logger.info(f"{self.site_id} 已设置代理: {proxy_url}")
                else:
                    self.logger.warning(f"{self.site_id} 开启了代理但未设置代理URL")
                
            # 设置User-Agent
            options.set_argument('--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0')

            # 阻止"自动保存密码"的提示气泡
            options.set_pref('credentials_enable_service', False)

            # 阻止"Chrome未正确关闭"的提示气泡
            options.set_argument('--hide-crash-restore-bubble')

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
                # 流程结束后site_setup中没有crawler.is_logged_in, 跳过
                # if await self.login_handler.check_login(self.browser):
                #     await self._save_browser_state(self.browser)
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

            # 使用 browserstate_manager 保存浏览器状态
            browserstate_manager = BrowserStateManager.get_instance()
            state = BrowserState(
                site_id=self.site_id,
                cookies=cookies,
                local_storage=local_storage,
                session_storage=session_storage
            )
            await browserstate_manager.save_state(self.site_id, state)
            self.logger.info("浏览器状态保存完成")
            
        except Exception as e:
            self.logger.error(f"保存浏览器状态失败: {str(e)}")
            self.logger.debug("错误详情:", exc_info=True)

    async def _restore_browser_state(self, browser: Chromium) -> bool:
        """恢复浏览器状态"""
        try:
            # 使用 browserstate_manager 获取浏览器状态
            browserstate_manager = BrowserStateManager.get_instance()
            browser_state : BrowserState = await browserstate_manager.get_state(self.site_id)
            
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
                cookies = browser_state.cookies
                self.logger.debug(f"正在恢复 {len(cookies)} 个cookies")
                for name, cookie_data in cookies.items():
                    try:
                        if isinstance(cookie_data, dict):
                            browser.set.cookies(cookie_data)
                    except Exception as e:
                        self.logger.error(f"设置cookie {name} 失败: {str(e)}")
                        continue
            
            # 恢复local storage
            if browser_state.local_storage:
                local_storage = browser_state.local_storage
                self.logger.debug(f"正在恢复 {len(local_storage)} 个localStorage项")
                for key, value in local_storage.items():
                    try:
                        tab.set.local_storage(item=key, value=value)
                    except Exception as e:
                        self.logger.error(f"设置localStorage {key} 失败: {str(e)}")
                        continue

            # 恢复session storage
            if browser_state.session_storage:
                session_storage = browser_state.session_storage
                self.logger.debug(f"正在恢复 {len(session_storage)} 个sessionStorage项")
                for key, value in session_storage.items():
                    try:
                        tab.set.session_storage(item=key, value=value)
                    except Exception as e:
                        self.logger.error(f"设置sessionStorage {key} 失败: {str(e)}")
                        continue
            
            self.logger.info("浏览器状态恢复完成")
            return True
            
        except Exception as e:
            self.logger.error(f"恢复浏览器状态失败: {str(e)}")
            self.logger.debug("错误详情:", exc_info=True)
            return False

    async def _clear_browser_state(self) -> None:
        """清除浏览器状态"""
        try:
            browserstate_manager = BrowserStateManager.get_instance()
            await browserstate_manager.delete_browser_state(self.site_id)
            self.logger.info("浏览器状态已清除")
        except Exception as e:
            self.logger.error(f"清除浏览器状态失败: {str(e)}")
            self.logger.debug("错误详情:", exc_info=True)

    async def get_result(self) -> Dict[str, Any]:
        """获取爬虫结果"""
        return getattr(self, '_result_data', {})

    async def _save_error(self, error: Dict[str, Any]):
        """保存错误信息到任务目录"""
        error_file = self.task_storage_path / f'error_{datetime.now().strftime("%y%m%d_%H%M%S")}.json'
        error_file.write_text(json.dumps(error, ensure_ascii=False, indent=2))

    async def _save_screenshot(self, browser: Chromium, name: str):
        """保存页面截图"""
        try:
            tab = browser.latest_tab
            if not tab:
                raise Exception("未找到活动标签页")
                
            screenshot_path = self.task_storage_path / f'{name}_{datetime.now().strftime("%y%m%d_%H%M%S")}.png'
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
                
            html_path = self.task_storage_path / f'{name}_{datetime.now().strftime("%y%m%d_%H%M%S")}.html'
            html_path.write_text(tab.html, encoding='utf-8')
            self.logger.info(f"页面源码已保存: {html_path}")
        except Exception as e:
            self.logger.error(f"保存页面源码失败: {str(e)}")

    async def _convert_size_to_gb(self, size_str: str) -> float:
        """将字符串形式的大小转换为GB为单位的浮点数"""
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

    async def _clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
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
                size_in_gb = await self._convert_size_to_gb(data['upload'])
                cleaned_data['upload'] = size_in_gb
            
            if 'download' in data:
                size_in_gb = await self._convert_size_to_gb(data['download'])
                cleaned_data['download'] = size_in_gb
            
            # 清洗分享率
            if 'ratio' in data:
                ratio_match = re.search(r'([\d.]+)', data['ratio'])
                if ratio_match:
                    cleaned_data['ratio'] = float(ratio_match.group(1))
            elif cleaned_data.get('upload', None) and cleaned_data.get('download', None):
                cleaned_data['ratio'] = cleaned_data.get('upload', None)/cleaned_data.get('download', None)
            
            # 清洗魔力值
            if 'bonus' in data:
                bonus_str = data['bonus'].replace(',', '')
                bonus_match = re.search(r'([\d.]+)', bonus_str)
                if bonus_match:
                    cleaned_data['bonus'] = float(bonus_match.group(1))
            
            # 清洗做种积分
            if 'seeding_score' in data:
                score_str = data['seeding_score'].replace(',', '')
                score_match = re.search(r'([\d.]+)', score_str)
                if score_match:
                    cleaned_data['seeding_score'] = float(score_match.group(1))
            
            # 清洗HR数据
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
                size_in_gb = await self._convert_size_to_gb(data['seeding_size'])
                cleaned_data['seeding_size'] = size_in_gb
            if 'official_seeding_size' in data:
                size_in_gb = await self._convert_size_to_gb(data['official_seeding_size'])
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

    async def _save_crawl_data(self, data: Dict[str, Any]) -> None:
        """保存提取的数据"""
        try:
            # 1. 保存到文件系统（用于调试）
            timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
            result_file = self.task_storage_path / f'result_{timestamp}.json'
            
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"数据已保存到 {result_file}")
            
            # 2. 保存到数据库
            result_data = ResultCreate(
                task_id=self.task_id,
                site_id=self.site_id,
                username=data.get('username'),
                user_class=data.get('user_class'),
                uid=data.get('uid'),
                join_time=data.get('join_time'),
                last_active=data.get('last_active'),
                upload=data.get('upload'),
                download=data.get('download'),
                ratio=data.get('ratio'),
                bonus=data.get('bonus'),
                seeding_score=data.get('seeding_score'),
                hr_count=data.get('hr_count'),
                bonus_per_hour=data.get('bonus_per_hour'),
                seeding_size=data.get('seeding_size'),
                seeding_count=data.get('seeding_count')
            )
            
            result = await self.result_manager.save_result(result_data)
            if result:
                self.logger.info("数据已保存到数据库")
            else:
                self.logger.error("保存数据到数据库失败")
            
            # 保存结果到内存中
            self._result_data = data
            
        except Exception as e:
            self.logger.error(f"保存数据失败: {str(e)}")
            raise

    async def _save_checkin_data(self, checkin_result: CheckInResult) -> None:
        """保存签到结果"""
        try:
            res = await self.result_manager.save_checkin_result(
                site_id=self.site_id,
                task_id=self.task_id,  # 添加task_id
                result=checkin_result
            )
            if res:
                self.logger.info("签到结果已保存到数据库")
            else:
                self.logger.error("保存签到结果到数据库失败")
                
        except Exception as e:
            self.logger.error(f"保存签到结果失败: {str(e)}")
            raise
