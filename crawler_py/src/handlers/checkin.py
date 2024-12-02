import os
import time
from typing import Optional, Tuple

from DrissionPage import Chromium
import DrissionPage
import DrissionPage.errors
from models.crawler import CheckInConfig, CrawlerTaskConfig
from utils.CloudflareBypasser import CloudflareBypasser
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

    async def perform_checkin(self, browser: Chromium, checkin_config: CheckInConfig) -> None:
        """执行签到处理"""
        # 检查环境变量中的签到开关
        if not self._check_env_enabled():
            self.logger.info(f"{self.task_config.site_id} 签到功能未在环境变量中启用")
            return
            
        # 检查站点配置中的签到设置，如果未配置(如frds)则不进行签到
        if not checkin_config:
            self.logger.info(f"{self.task_config.site_id} 未配置签到功能")
            return
        
        try:
            self.logger.debug(f"开始签到流程 - checkin_config: {checkin_config}")
            tab = browser.new_tab()
            browser.activate_tab(tab)
            self.logger.debug(f"创建新标签页 - 标签页ID: {id(tab)}")

            # 首先尝试通过访问签到URL的方式
            self.logger.info(f"开始签到流程 - URL:{checkin_config.checkin_url}")
            result = await self._try_checkin_by_url(tab, checkin_config)
            if result:
                return result
                
            # 如果URL方式失败，尝试通过点击按钮的方式
            result = await self._try_checkin_by_button(tab, checkin_config)
            if result:
                return result
            
        except Exception as e:
            self.logger.error(f"{self.task_config.site_id} 签到失败: {str(e)}")
            return
            
    async def _try_checkin_by_url(self, tab, checkin_config: CheckInConfig) -> bool:
        """
        尝试通过直接访问签到URL的方式签到
        
        Returns:
            bool: 是否成功签到
        """
        checkin_url = checkin_config.checkin_url
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
        # 获取签到按钮配置
        button_config = checkin_config.checkin_button
        if not button_config:
            self.logger.warning(f"{self.task_config.site_id} 未配置签到按钮")
            return
            
        # 查找并点击签到按钮
        button = tab.ele(button_config.selector)
        if not button:
            self.logger.warning(f"{self.task_config.site_id} 未找到签到按钮")
            return
        
        already_keywords = ["签到已得", "已签到", "already", "签到成功"]
        if any(keyword in button.text for keyword in already_keywords):
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

    async def _check_checkin_result(self, tab, checkin_config: CheckInConfig) -> Tuple[str, str]:
        """
        检查签到结果
        
        Args:
            page: 要检查的页面

        Returns:
            Tuple[str, str]: (结果类型, 详细信息)
            结果类型: 
                - success: 签到成功
                - already: 已经签到
                - captcha: 需要验证码
                - error: 其他错误
        """
        # 获取结果检查配置
        sign = checkin_config.success_check.sign
        slt = checkin_config.success_check.element.selector
        loc = checkin_config.success_check.element.location
        s_slt = checkin_config.success_check.element.second_selector
        self.logger.debug(f"{self.task_config.site_id} 签到结果检查配置: {slt}, {loc}, {s_slt} => {sign}")

        if loc == "child":
            element = tab.ele(slt).eles(s_slt)
        elif loc == 'index':
            element = tab.ele(slt, index=int(s_slt))
        else:
            element = tab.eles(slt)

        if not element:
            self.logger.warning(f"{self.task_config.site_id} 未配置签到结果检查元素")
            return "error"
        if not sign:
            self.logger.warning(f"{self.task_config.site_id} 未配置签到结果检查标志")
            return "error"
            
        # 检查是否需要验证码
        if tab.ele('@class=cf-turnstile'):
            cf_bypasser = CloudflareBypasser(tab)
            cf_bypasser.click_verification_button()
            self.logger.debug(f"点击了cf-turnstile验证按钮")
            
        # 检查是否签到成功
        for ele in element:
            if ele.text == sign["success"]:
                return "success"
                
            # 检查是否已经签到
            if ele.text == sign["already"]:
                return "already"
                
            # 检查是否有错误信息
            if ele.text == sign["error"]:
                return "error"
                
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

