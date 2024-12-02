import os
import time
from typing import Optional, Tuple

from DrissionPage import Chromium
import DrissionPage
import DrissionPage.errors
from utils.url import convert_url
from models.crawler import CheckInConfig, CrawlerTaskConfig
from utils.clouodflare_bypasser import CloudflareBypasser
from utils.logger import get_logger, setup_logger


class CheckInHandler:
    def __init__(self, task_config: CrawlerTaskConfig):
        self.task_config = task_config
        setup_logger()
        self.logger = get_logger(name=__name__, site_id=self.task_config.site_id)
        self.logger.debug(f"初始化CheckInHandler - 任务ID: {self.task_config.task_id}, 站点ID: {self.task_config.site_id}")
        # 验证并转换签到配置
        # self.checkin_config = None
        # if "checkin_config" in self.task_config:
        #     try:
        #         self.checkin_config = CheckInConfig(**self.task_config["checkin_config"])
        #     except Exception as e:
        #         self.logger.error(f"签到配置验证失败: {str(e)}")

    async def perform_checkin(self, browser: Chromium, task_config: CrawlerTaskConfig) -> None:
        """执行签到处理"""
        # 检查环境变量中的签到开关
        if not self._check_env_enabled():
            self.logger.info(f"{self.task_config.site_id} 签到功能未在环境变量中启用")
            return
            
        # 检查站点配置中的签到设置，如果未配置(如frds)则不进行签到
        if not task_config.checkin_config:
            self.logger.info(f"{self.task_config.site_id} 未配置签到功能")
            return
        
        checkin_config = task_config.checkin_config
        
        try:
            self.logger.debug(f"开始签到流程 - checkin_config: {checkin_config}")
            tab = browser.new_tab()
            browser.activate_tab(tab)
            self.logger.trace(f"使用标签页 - 标签页ID: {id(tab)}")

            try:
                if await self._is_already_checked_in(tab):
                    self.logger.success(f"{self.task_config.site_id} 今天已经签到")
                    return
                
            except Exception as e:
                self.logger.warning(f"{self.task_config.site_id} 检查签到状态时出错: {str(e)}")
                
            # 首先尝试通过访问签到URL的方式
            self.logger.info(f"开始签到流程 - URL:{checkin_config.checkin_url}")
            result = await self._try_checkin_by_url(tab, checkin_config, task_config)
            if result:
                return result
                
            # 如果URL方式失败，尝试通过点击按钮的方式
            result = await self._try_checkin_by_button(tab, checkin_config)
            if result:
                return result
            
        except Exception as e:
            self.logger.error(f"{self.task_config.site_id} 签到失败: {str(e)}")
            return
            
    async def _try_checkin_by_url(self, tab, checkin_config: CheckInConfig, task_config: CrawlerTaskConfig) -> bool:
        """
        尝试通过直接访问签到URL的方式签到
        
        Returns:
            bool: 是否成功签到
        """
        checkin_url = checkin_config.checkin_url
        checkin_url = convert_url(task_config, checkin_url)
        if not checkin_url:
            self.logger.debug(f"{self.task_config.site_id} 未配置签到URL")
            return False
            
        try:
            # 在新标签页中打开签到URL
            tab.get(checkin_url)
            
            if await self._is_cloudflare_present(tab):
                self.logger.info("检测到Cloudflare验证页面")
                if not await self._handle_cloudflare(tab):
                    self.logger.error("Cloudflare验证失败")
                    return False
                    
            # 检查签到结果
            result = await self._check_checkin_result(tab, checkin_config)
            
            # 处理签到结果
            if result == "success":
                self.logger.success(f"{self.task_config.site_id} [URL方式] 签到成功")
                return result
            elif result == "already":
                self.logger.info(f"{self.task_config.site_id} [URL方式] 今天已经签到")
                return result
            else:
                tab.get(checkin_url)
                self.logger.warning(f"{self.task_config.site_id} [URL方式] 将尝试按钮方式")
                return False
                
        except Exception as e:
            self.logger.warning(f"{self.task_config.site_id} [URL方式] 签到失败: {str(e)}，将尝试按钮方式")
            return False
            
    async def _try_checkin_by_button(self, tab, checkin_config: CheckInConfig) -> None:
        """
        尝试通过点击按钮的方式签到
        """
        try:
            # 首先检查是否已经签到
            if await self._is_already_checked_in(tab):
                self.logger.info(f"{self.task_config.site_id} [按钮方式] 今天已经签到")
                return "already"
                
            # 获取签到按钮配置
            button_config = checkin_config.checkin_button
            if not button_config:
                self.logger.warning(f"{self.task_config.site_id} 未配置签到按钮")
                return
                
            # 查找签到按钮（使用多个选择器）
            button_selectors = [
                button_config.selector,  # 配置的选择器
                '@href$attendance.php',  # 包含attendance的链接
                '@id:signed',  # 通用签到按钮ID
                '@text:签到',  # 文本为"签到"的元素
                '@text:签 到',  # 文本为"签 到"的元素
                '@id:sign_in',  # 签到按钮ID
                '@href:addbonus',  # 魔力值相关链接
                '@class:dt_button@value:打卡',  # 打卡按钮
                '@href:sign_in',  # 包含sign_in的链接
                '@onclick:do_signin',  # 签到点击事件
                '@id:do-attendance',  # 签到按钮ID
                'shark-icon-button@href:attendance.php'  # 特殊签到按钮
            ]
            
            button = None
            for selector in button_selectors:
                button = tab.ele(selector, timeout=3)
                if button:
                    self.logger.debug(f"找到签到按钮: {selector}")
                    break
                    
            if not button:
                self.logger.warning(f"{self.task_config.site_id} 未找到任何签到按钮")
                return
            
            # 检查按钮文本是否表明已签到
            already_keywords = ["已签到", "已经签到", "签到已得", "今日已签"]
            if button.text and any(keyword in button.text for keyword in already_keywords):
                self.logger.info(f"{self.task_config.site_id} [按钮方式] 今天已经签到")
                return "already"

            # 检查按钮是否可见和可点击
            if not button.is_displayed():
                self.logger.warning(f"{self.task_config.site_id} 签到按钮不可见")
                return
            if not button.is_enabled():
                self.logger.warning(f"{self.task_config.site_id} 签到按钮不可点击")
                return
            
            # 点击按钮并等待页面变化
            button.click()
            tab.wait.load_complete()
            
            if await self._is_cloudflare_present(tab):
                self.logger.info("检测到Cloudflare验证页面")
                if not await self._handle_cloudflare(tab):
                    self.logger.error("Cloudflare验证失败")
                    return False
                
            # 检查签到结果
            result = await self._check_checkin_result(tab, checkin_config)
            
            if result == "success":
                self.logger.success(f"{self.task_config.site_id} [按钮方式] 签到成功")
                return result
            elif result == "already":
                self.logger.info(f"{self.task_config.site_id} [按钮方式] 今天已经签到")
                return result
            else:
                self.logger.error(f"{self.task_config.site_id} [按钮方式] 签到失败")
                return False
                
        except Exception as e:
            self.logger.error(f"{self.task_config.site_id} [按钮方式] 签到出错: {str(e)}")
            return False
            
    async def _is_already_checked_in(self, tab) -> bool:
        """
        检查是否已经签到
        
        Returns:
            bool: True已签到 False未签到
        """
        try:
            checked_selectors = [
                '@text:签到已得',
                '@text:今日已签',
                '@text:今天已签到',
                '@class:already-signed',
                '@class:signed-in'
            ]
            for selector in checked_selectors:
                if tab.ele(selector, timeout=2):
                    self.logger.debug(f"找到已签到标识: {selector}")
                    return True
            self.logger.debug(f"{self.task_config.site_id} 未发现已签到标识")
                    
            # 检查各种可能表示未签到的元素
            unchecked_selectors = [
                '@href$attendance.php',  # 包含attendance的链接
                '@id:signed',  # 签到按钮ID
                '@text:签到',  # 文本为"签到"的元素
                '@text:签 到',  # 文本为"签 到"的元素
                '@id:sign_in',  # 签到按钮ID
                '@href:addbonus',  # 魔力值相关链接
                '@class:dt_button@value:打卡',  # 打卡按钮
                '@href:sign_in',  # 包含sign_in的链接
                '@onclick:do_signin',  # 签到点击事件
                '@id:do-attendance',  # 签到按钮ID
                'shark-icon-button@href:attendance.php'  # 特殊签到按钮
            ]
            
            # 如果找到任何一个未签到的元素，说明还没签到
            for selector in unchecked_selectors:
                if tab.ele(selector, timeout=2):
                    self.logger.debug(f"找到未签到标识: {selector}")
                    return False
                
            self.logger.debug(f"{self.task_config.site_id} 未发现未签到标识, 默认已签到")
            return True
            
        except Exception as e:
            self.logger.error(f"检查签到状态时出错: {str(e)}")
            return False

    async def _check_checkin_result(self, tab, checkin_config: CheckInConfig) -> str:
        """
        检查签到结果
        
        Args:
            tab: 要检查的标签页
            checkin_config: 签到配置

        Returns:
            str: 结果类型
                - success: 签到成功
                - already: 已经签到
                - error: 其他错误
        """
        try:
            # 2. 检查常见的签到成功标识
            success_selectors = [
                '@text:签到成功',
                '@text:已签到',
                '@text:今天已经签到',
                '@text:签到已得',
                '@text:已经打卡',
                '@text:打卡成功',
                '@class:signed',
                '@class:checked',
                '@class:success'
            ]
            
            for selector in success_selectors:
                element = tab.ele(selector)
                if element:
                    self.logger.debug(f"找到通用成功标识: {selector}")
                    return "success"
                    
            # 3. 检查常见的已签到标识
            already_selectors = [
                '@text:今日已签',
                '@text:今天已签到',
                '@text:已经签到',
                '@text:请明天再来',
                '@class:already-signed',
                '@class:signed-in'
            ]
            
            for selector in already_selectors:
                element = tab.ele(selector)
                if element:
                    self.logger.debug(f"找到通用已签到标识: {selector}")
                    return "already"
                    
            # 4. 检查常见的错误标识
            error_selectors = [
                '@text:签到失败',
                '@text:出错',
                '@text:错误',
                '@class:error',
                '@class:fail',
                '@class:failed'
            ]
            
            for selector in error_selectors:
                element = tab.ele(selector)
                if element:
                    self.logger.debug(f"找到通用错误标识: {selector}")
                    return "error"
                    
            # 1. 首先检查配置的结果检查规则
            if checkin_config.success_check:
                result_config = checkin_config.success_check
                element_config = result_config.element
                sign_config = result_config.sign
                
                self.logger.debug(f"{self.task_config.site_id} 检查配置的签到结果规则")
                element = tab.ele(element_config.selector)
                if element and element.text:
                    text = element.text
                    if sign_config["success"] in text:
                        self.logger.debug(f"找到成功标识: {sign_config['success']}")
                        return "success"
                    elif sign_config["already"] in text:
                        self.logger.debug(f"找到已签到标识: {sign_config['already']}")
                        return "already"
                    elif sign_config["error"] in text:
                        self.logger.debug(f"找到错误标识: {sign_config['error']}")
                        return "error"
            
            # 5. 检查是否有验证码
            if tab.ele('@class=cf-turnstile'):
                self.logger.debug("检测到验证码，尝试处理")
                cf_bypasser = CloudflareBypasser(tab)
                cf_bypasser.click_verification_button()
                self.logger.debug("点击了验证码按钮")
                tab.wait.load_complete()
                # 递归检查结果
                return await self._check_checkin_result(tab, checkin_config)
                
            # 6. 如果都没找到，记录页面状态
            self.logger.warning(f"未找到任何已知的结果标识")
            self.logger.debug(f"当前页面URL: {tab.url}")
            self.logger.debug(f"当前页面标题: {tab.title}")
            if tab.ele('body'):
                self.logger.debug(f"页面文本: {tab.ele('body').text[:200]}...")  # 只记录前200个字符
                
            return "error"
                
        except Exception as e:
            self.logger.error(f"检查签到结果时出错: {str(e)}")
            self.logger.debug(f"错误详情: ", exc_info=True)
            return "error"
            
    async def _check_env_enabled(self) -> bool:
        """
        检查环境变量中的签到开关
        
        Returns:
            bool: 是否启用签到
        """
        # 检查全局签到开关
        global_enabled = os.getenv("ENABLE_CHECKIN", "false").lower() == "true"
        if not global_enabled:
            return False
            
        # 检查站点特定的签到开关
        sites_str = os.getenv("CHECKIN_SITES", "")
        if not sites_str:
            return False
            
        enabled_sites = [site.strip().lower() for site in sites_str.split(",") if site.strip()]
        return self.task_config.site_id.lower() in enabled_sites
    
    async def _is_cloudflare_present(self, tab) -> bool:
        """检查是否存在Cloudflare验证页面"""
        try:
            if tab.title == "Just a moment...":
                return True

            # 检查是否存在 Cloudflare 的 JavaScript 或 Turnstile 验证相关的关键元素
            if tab.ele('script[src*="challenge-platform"]') or tab.ele('@div#challenge-error-text'):
                return True

            # 检查页面文本中是否包含 Cloudflare 验证相关提示
            body_text = tab.ele('@tag()=body').text
            if "Checking your browser before accessing" in body_text or "Verify you are human" in body_text:
                return True
            return False
        except DrissionPage.errors.ElementNotFoundError:
            self.logger.debug("未找到Cloudflare页面的元素")
            return False
        except Exception as e:
            self.logger.error("检查Cloudflare状态时出错", exc_info=True)
            return False

    async def _handle_cloudflare(self, tab) -> bool:
        """处理Cloudflare验证"""
        try:
            # Where the bypass starts
            self.logger.info('Starting Cloudflare bypass.')
            cf_bypasser = CloudflareBypasser(tab)
            # If you are solving an in-page captcha (like the one here: https://seleniumbase.io/apps/turnstile), use cf_bypasser.click_verification_button() directly instead of cf_bypasser.bypass().
            # It will automatically locate the button and click it. Do your own check if needed.

            cf_bypasser.bypass()

            # 检查是否需要处理Cloudflare验证
            self.logger.info("等待Cloudflare验证完成...")
            # sleep(160)
            tab.wait.load_start()
            if not await self._is_cloudflare_present(tab):
                self.logger.success("Cloudflare验证已完成")
                return True
            else:
                self.logger.error("Cloudflare验证超时")
                return False

        except Exception as e:
            self.logger.error("Cloudflare验证处理出错", exc_info=True)
            return False

