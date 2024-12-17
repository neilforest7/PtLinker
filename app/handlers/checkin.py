import os
from enum import Enum
from typing import Literal

import DrissionPage
import DrissionPage.errors
from core.logger import get_logger, setup_logger
from DrissionPage import Chromium
from schemas.siteconfig import CheckInConfig
from schemas.sitesetup import SiteSetup
from utils.clouodflare_bypasser import CloudflareBypasser
from utils.url import convert_url
from services.managers.setting_manager import SettingManager

CheckInResult = Literal["not_set", "already", "success", "failed"]


class CheckInHandler:
    def __init__(self, site_setup: SiteSetup):
        self.site_setup = site_setup
        self.settings_manager = SettingManager.get_instance()
        # setup_logger()
        self.logger = get_logger(name=__name__, site_id=self.site_setup.site_id)
        self.logger.debug(f"初始化CheckInHandler - 站点ID: {self.site_setup.site_id}")

    async def perform_checkin(self, tab: Chromium) -> CheckInResult:
        """执行签到处理"""
        checkin_config = self.site_setup.site_config.checkin_config

        # 检查站点配置中的签到设置
        if not checkin_config.checkin_url and not checkin_config.checkin_button:
            self.logger.info(f"{self.site_setup.site_id} 未配置签到功能 (checkin_config未配置)")
            return "not_set"
            
        # 检查站点是否启用签到
        if not checkin_config.enabled:
            self.logger.info(f"{self.site_setup.site_id} 未启用签到功能 (签到开关已禁用)")
            return "not_set"
        
        if not self.settings_manager.get_setting('captcha_skip_sites') and self.site_setup.site_id not in self.settings_manager.get_setting('captcha_skip_sites'):
            self.logger.info(f"{self.site_setup.site_id} 未启用签到功能 (全局站点列表跳过)")
            return "not_set"
        
        try:
            self.logger.debug(f"开始签到流程 - checkin_config: {checkin_config}")
            self.logger.trace(f"使用标签页 - 标签页ID: {id(tab)}")
            
            # 首先尝试通过访问签到URL的方式
            self.logger.info(f"开始签到流程 - URL:{checkin_config.checkin_url}")
            result = await self._try_checkin_by_url(tab, checkin_config)
            if result in ["success", "already"]:
                return result

            # 中途检查是否已经签到
            try:
                if await self._is_already_checked_in(tab):
                    self.logger.success(f"{self.site_setup.site_id} 今天已经签到")
                    return "already"
            except Exception as e:
                self.logger.warning(f"{self.site_setup.site_id} 检查签到状态时出错: {str(e)}")
                
            # 如果URL方式失败，尝试通过点击按钮的方式
            result = await self._try_checkin_by_button(tab, checkin_config)
            return result
            
        except Exception as e:
            self.logger.error(f"{self.site_setup.site_id} 签到失败: {str(e)}")
            return "failed"
            
    async def _try_checkin_by_url(self, tab, checkin_config: CheckInConfig) -> CheckInResult:
        """
        尝试通过直接访问签到URL的方式签到
        """
        checkin_url = checkin_config.checkin_url
        checkin_url = convert_url(self.site_setup.site_config.site_url, checkin_url)
        if not checkin_url:
            self.logger.debug(f"{self.site_setup.site_id} 未配置签到URL")
            return "failed"
            
        try:
            # 在新标签页中打开签到URL
            tab.get(checkin_url)

            if await self._is_cloudflare_present(tab):
                self.logger.info("检测到Cloudflare验证页面")
                if not await self._handle_cloudflare(tab):
                    self.logger.error("Cloudflare验证失败")
                    return "failed"
                    
            # 检查签到结果
            result = await self._check_checkin_result(tab, checkin_config)
            
            # 处理签到结果
            if result == "success":
                self.logger.success(f"{self.site_setup.site_id} [URL方式] 签到成功")
                return "success"
            elif result == "already":
                self.logger.info(f"{self.site_setup.site_id} [URL方式] 今天已经签到")
                return "already"
            else:
                self.logger.warning(f"{self.site_setup.site_id} [URL方式] 将尝试按钮方式")
                return "failed"
                
        except Exception as e:
            self.logger.warning(f"{self.site_setup.site_id} [URL方式] 签到失败: {str(e)}，将尝试按钮方式")
            return "failed"
            
    async def _try_checkin_by_button(self, tab, checkin_config: CheckInConfig) -> CheckInResult:
        """
        尝试通过点击按钮的方式签到
        """
        try:
            # 首先检查是否已经签到
            if await self._is_already_checked_in(tab):
                self.logger.info(f"{self.site_setup.site_id} [按钮方式] 今天已经签到")
                return "already"
                
            # 获取签到按钮配置
            button_config = checkin_config.checkin_button
            if not button_config:
                self.logger.warning(f"{self.site_setup.site_id} 未配置签到按钮")
                return "failed"
                
            # 查找签到按钮（使用多个选择器）
            button_selectors = [
                button_config.selector,  # 配置的选择器
                '@href$attendance.php',  # 包含attendance的链接
                '@id:signed',  # 通用签到按钮ID
                '@text():签到',  # 文本为"签到"的元素
                '@text():签 到',  # 文本为"签 到"的元素
                '@id:sign_in',  # 签到按钮ID
                '@href$action=addbonus',  # 魔力值相关链接
                '@@class=dt_button@@value:打卡',  # 打卡按钮
            ]
            
            button = None
            for selector in button_selectors:
                button = tab.ele(selector, timeout=3)
                if button:
                    self.logger.debug(f"找到签到按钮: {selector}")
                    break
                    
            if not button:
                self.logger.warning(f"{self.site_setup.site_id} 未找到任何签到按钮")
                return "failed"
            
            # 检查按钮文本是否表明已签到
            already_keywords = ["已签到", "已经签到", "签到已得", "今日已签"]
            if button.text and any(keyword in button.text for keyword in already_keywords):
                self.logger.info(f"{self.site_setup.site_id} [按钮方式] 今天已经签到")
                return "already"
            
            # 点击按钮并等待页面变化
            button.click()
            
            if await self._is_cloudflare_present(tab):
                self.logger.info("检测到Cloudflare验证页面")
                if not await self._handle_cloudflare(tab):
                    self.logger.error("Cloudflare验证失败")
                    return "failed"
                
            # 检查签到结果
            result = await self._check_checkin_result(tab, checkin_config)
            
            if result == "success":
                self.logger.success(f"{self.site_setup.site_id} [按钮方式] 签到成功")
                return "success"
            elif result == "already":
                self.logger.info(f"{self.site_setup.site_id} [按钮方式] 今天已经签到")
                return "already"
            else:
                self.logger.error(f"{self.site_setup.site_id} [按钮方式] 签到失败")
                return "failed"
                
        except Exception as e:
            self.logger.error(f"{self.site_setup.site_id} [按钮方式] 签到出错: {str(e)}")
            return "failed"
            
    async def _is_already_checked_in(self, tab) -> bool:
        """
        检查是否已经签到
        
        Returns:
            bool: True已签到 False未签到
        """
        try:
            checked_selectors = [
                '@text():签到已得',
                '@text():今日已签',
                '@text():今天已签到',
                '@value=已经打卡',
                '@text():簽到成功',
                '@text():已簽到',
                '@class:already-signed',
                '@class:signed-in'
            ]
            for selector in checked_selectors:
                if tab.ele(selector, timeout=2):
                    self.logger.debug(f"找到已签到标识: {selector}")
                    return True
            self.logger.debug(f"{self.site_setup.site_id} 未发现已签到标识")
                    
            # 检查各种可能表示未签到的元素
            unchecked_selectors = [
                '@href$attendance.php',
                '@value=每日打卡',  # 包含attendance的链接
                '@id:signed',  # 签到按钮ID
                '@text:签到',  # 文本为"签到"的元素
                '@text:签 到',  # 文本为"签 到"的元素
                '@id:sign_in',  # 签到按钮ID
                '@href$addbonus',
                '@text():回答按钮点击时即提交',  # 打卡按钮
                # 魔力值相关链接
            ]
            
            # 如果找到任何一个未签到的元素，说明还没签到
            for selector in unchecked_selectors:
                if tab.ele(selector, timeout=2):
                    self.logger.debug(f"找到未签到标识: {selector}")
                    return False
                
            self.logger.debug(f"{self.site_setup.site_id} 未发现未签到标识")
            return False
            
        except Exception as e:
            self.logger.error(f"检查签到状态时出错: {str(e)}")
            return False

    async def _check_checkin_result(self, tab, checkin_config: CheckInConfig) -> CheckInResult:
        """
        检查签到结果
        
        Args:
            tab: 要检查的标签页
            checkin_config: 签到配置

        Returns:
            CheckInResult: 签到结果
        """
        try:
            # 2. 检查常见的签到成功标识
            success_selectors = [
                '@text():签到成功',
                '@text():已签到',
                '@text():今天已经签到',
                '@text():签到已得',
                '@text():已经打卡',
                '@value=已经打卡',
                '@text():打卡成功',
                '@class:signed',
                '@class:checked',
                '@class:success'
            ]
            
            for selector in success_selectors:
                element = tab.ele(selector, timeout=2)
                if element:
                    self.logger.debug(f"找到通用成功标识: {selector}")
                    return "success"
                    
            # 3. 检查常见的已签到标识
            already_selectors = [
                '@text():今日已签',
                '@text():今天已签到',
                '@text():已经签到',
                '@text():请明天再来',
                '@value=已经打卡',
                '@class:already-signed',
                '@class:signed-in'
            ]
            
            for selector in already_selectors:
                element = tab.ele(selector, timeout=2)
                if element:
                    self.logger.debug(f"找到通用已签到标识: {selector}")
                    return "already"
                    
            # 4. 检查常见的错误标识
            error_selectors = [
                '@text:签到失败',
                '@text:出错',
                '@text():错误',
                '@text():回答按钮点击时即提交',
                '@class:error',
                '@class:fail',
                '@class:failed'
            ]
            
            for selector in error_selectors:
                element = tab.ele(selector, timeout=2)
                if element:
                    self.logger.debug(f"找到通用错误标识: {selector}")
                    return "failed"
                    
            # 1. 首先检查配置的结果检查规则
            if checkin_config.success_check:
                result_config = checkin_config.success_check
                element_config = result_config.element
                sign_config = result_config.sign
                
                self.logger.debug(f"{self.site_setup.site_id} 检查配置的签到结果规则")
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
                        return "failed"
            
            # 5. 检查是否有验证码
            if tab.ele('@class=cf-turnstile'):
                self.logger.debug("检测到验证码，尝试处理")
                cf_bypasser = CloudflareBypasser(tab)
                cf_bypasser.click_verification_button()
                self.logger.debug("点击了验证码按钮")
                # 递归检查结果
                return await self._check_checkin_result(tab, checkin_config)
                
            # 6. 如果都没找到，记录页面状态
            self.logger.debug(f"未找到任何已知的结果标识")
            self.logger.debug(f"当前页面URL: {tab.url}")
            self.logger.debug(f"当前页面标题: {tab.title}")
                
            return "failed"
                
        except Exception as e:
            self.logger.error(f"检查签到结果时出错: {str(e)}")
            self.logger.debug(f"错误详情: ", exc_info=True)
            return "failed"
            
    async def _is_cloudflare_present(self, tab) -> bool:
        """检查是否存在Cloudflare验证页面"""
        try:
            if tab.title == "Just a moment...":
                return True

            # 检查是否存在 Cloudflare 的 JavaScript 或 Turnstile 验证相关的关键元素
            if tab.ele('script[src*="challenge-platform"]') or tab.ele('@div#challenge-error-text'):
                return True

            if CloudflareBypasser(tab).is_bypassed():
                return False
            
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
            tab.wait.title_change("Just a moment...", exclude = True)
            return cf_bypasser.is_bypassed()

        except Exception as e:
            self.logger.error("Cloudflare验证处理出错", exc_info=True)
            return False

