import json
import os
from datetime import datetime
from time import sleep
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import DrissionPage
import DrissionPage.errors
from core.logger import get_logger, setup_logger
from DrissionPage import Chromium
from schemas.siteconfig import (LoginConfig, WebElement)
from services.captcha.captcha_service import CaptchaService
from utils.clouodflare_bypasser import CloudflareBypasser
from utils.url import convert_url

from schemas.sitesetup import SiteSetup
from services.managers.setting_manager import settings

class LoginHandler:
    def __init__(self, site_setup: SiteSetup):
        self.site_setup : SiteSetup = site_setup
        self.login_config : LoginConfig = self.site_setup.site_config.login_config
        self.settings_manager = settings
        # setup_logger()
        self.logger = get_logger(name=__name__, site_id=site_setup.site_id)
        self.logger.debug(f"初始化LoginHandler - 站点ID: {site_setup.site_id}")
        self.captcha_service = CaptchaService()

    async def perform_login(self, browser: Chromium) -> bool:
        """执行登录流程"""
        try:
            # 检查凭证
            if not self.login_config:
                self.logger.error("未配置登录信息")
                return False
            
            if not self.site_setup.crawler_credential:
                self.logger.error("未配置任何可用凭证")
                return False
            
            if not self.site_setup.crawler_config.enabled:
                self.logger.warning("当前站点已禁用")
                return False
            
            # 获取登录配置
            self.logger.info(f"使用凭证 '{self.site_setup.crawler_credential.description or '默认凭证'}' 登录")

            
            self.logger.info(f"开始登录流程 - URL: {self.login_config.login_url}")
            self.logger.debug(f"浏览器实例ID: {id(browser)}")
            
            # 创建新标签页
            tab = browser.new_tab()
            browser.activate_tab(tab)
            self.logger.debug(f"创建新标签页 - 标签页ID: {id(tab)}")
            self.login_url = convert_url(site_url=str(self.site_setup.site_config.site_url), short_url=str(self.login_config.login_url))
            # 导航到登录页面
            self.logger.debug(f"正在导航到登录页面: {self.login_url}")
            tab.get(self.login_url)
            self.logger.debug(f"页面标题: {tab.title}")
            self.logger.debug(f"页面URL: {tab.url}")

            # 执行pre-login操作
            if hasattr(self.login_config, 'pre_login') and self.login_config.pre_login:
                self.logger.info("开始执行pre-login操作")
                if not await self._handle_pre_login(tab, self.login_config.pre_login):
                    self.logger.error("Pre-login操作失败")
                    return False
                self.logger.info("Pre-login操作完成")

            # 等待登录表单
            self.logger.debug(f"等待登录表单出现，选择器: {self.login_config.form_selector}")
            form = tab.ele(self.login_config.form_selector, timeout=5)
            if not form:
                # 如果没有找到登录表单，再次检查是否是Cloudflare页面
                self.logger.debug("未找到登录表单, 开始检查Cloudflare验证")
                if await self._is_cloudflare_present(tab):
                    self.logger.info("检测到Cloudflare验证页面")
                    if not await self._handle_cloudflare(tab):
                        self.logger.error("Cloudflare验证失败")
                        return False
                    # 验证通过后重新检查登录表单
                    form = tab.ele(self.login_config.form_selector, timeout=5)
                    if not form:
                        self.logger.error(f"登录表单未找到 - 选择器: {self.login_config.form_selector}")
                        raise Exception("登录表单未找到")
                else:
                    self.logger.error(f"登录表单未找到 - 选择器: {self.login_config.form_selector}")
                    raise Exception("登录表单未找到")
            self.logger.debug(f"登录表单已找到 - 元素ID: {form.attr('id')}, 类名: {form.attr('class')}")

            # 填充表单字段
            self.logger.info("开始填充表单字段")
            for field_name, field_config in self.login_config.fields.items():
                if field_name == 'username':
                    value = self.site_setup.crawler_credential.username
                elif field_name == 'password':
                    value = self.site_setup.crawler_credential.password
                else:
                    value = getattr(field_config, 'value', None)
                    
                if value is None:
                    self.logger.debug(f"  - 字段 {field_name} 没有值")
                    continue
                    
                # 根据字段类型处理输入
                if field_config.type == "submit":
                    continue
                if field_config.type == "checkbox":
                    input_ele = tab.ele(field_config.selector)
                    if input_ele:
                        input_ele.click()
                    else:
                        self.logger.warning(f"  - 未找到输入元素: {field_config.selector}")
                else:
                    sleep(0.5)
                    input_ele = tab.ele(field_config.selector)
                    if input_ele:
                        self.logger.debug(f"  - 找到输入元素 - ID: {input_ele.attr('id')}")
                        
                        # 根据字段类型处理输入
                        if field_config.type == "password":
                            input_ele.clear()
                            self.logger.debug(f"  - 已清空{field_name}字段")
                            input_ele.input(str(value))
                            self.logger.debug(f"  - 已填充密码字段")
                        else:
                            input_ele.clear()
                            self.logger.debug(f"  - 已清空{field_name}字段")
                            input_ele.input(str(value))
                            self.logger.debug(f"  - 已填充{field_name}: {value}")
                    else:
                        self.logger.warning(f"  - 未找到输入元素: {field_config.selector}")
            self.logger.debug("表单字段填充完成")
            
            # 处理验证码
            # 检查站点的验证码处理方式
            if self.site_setup.crawler_config.captcha_skip:
                self.logger.info(f"站点 {self.site_setup.site_id} 配置为跳过验证码")
            else:
                # 从设置中获取跳过验证码的站点列表
                captcha_skip_sites = await self.settings_manager.get_setting('captcha_skip_sites')
                if captcha_skip_sites and self.site_setup.site_id in captcha_skip_sites:
                    self.logger.info(f"站点 {self.site_setup.site_id} 配置为跳过验证码")
                elif self.login_config.captcha:
                    try:
                        self.logger.debug("开始验证码处理流程")
                        await self._handle_captcha(tab, self.login_config)
                    except json.JSONDecodeError:
                        self.logger.warning("解析站点验证码配置失败")
                        raise Exception("解析站点验证码配置失败")
                    self.logger.info("验证码处理完成")

            # 获取提交按钮
            submit_config = self.login_config.fields.get('submit')
            if not submit_config:
                self.logger.trace(f"使用默认提交按钮: '@type=submit'")
                submit_btn = tab.ele('@type=submit')
            else:
                self.logger.trace(f"使用配置的提交按钮: {submit_config.selector}")
                submit_btn = tab.ele(submit_config.selector)

            if submit_btn:
                self.logger.debug(f"点击登录按钮: {submit_btn.text}")
                submit_btn.click()
                self.logger.trace("已点击登录按钮")
            else:
                self.logger.warning(f"未找到配置的登录按钮: {submit_config.selector}")

            # 验证登录结果
            self.logger.debug("开始验证登录结果")
            success = await self._verify_login(tab, self.login_config.success_check)
            
            if success:
                self.logger.success("登录成功")
            else:
                self.logger.error("登录失败 - 未找到成功登录的标识")
                self.logger.debug(f"当前页面URL: {tab.url}")
                self.logger.debug(f"当前页面标题: {tab.title}")
        
            return success
        
        except DrissionPage.errors.ElementNotFoundError as e:
            self.logger.error("登录过程找不到元素", {e})
            self.logger.debug(f"错误详情: {type(e).__name__}")
            return False
        except Exception as e:
            self.logger.error("登录过程发生错误", {e})
            self.logger.debug(f"错误详情: {type(e).__name__}")
            return False

    async def _handle_captcha(self, tab, login_config: LoginConfig) -> None:
        """处理验证码"""
        if not login_config.captcha:
            return

        try:
            captcha_config = login_config.captcha
            captcha_type = captcha_config.type
            
            # 获取验证码元素选择器
            element_selector = captcha_config.element.selector
            self.logger.debug(f"等待验证码元素 - 选择器: {element_selector}")
            
            captcha_element = tab.ele(element_selector)
            if not captcha_element:
                self.logger.error(f"验证码元素未找到 - 选择器: {element_selector}")
                raise Exception("验证码元素未找到")
                
            # 获取验证码数据
            if captcha_type == 'background':
                # 处理背景图片验证码
                # 获取style属性
                style = captcha_element.attr('style')
                if not style:
                    self.logger.error("验证码元素没有style属性")
                    raise Exception("验证码元素没有style属性")
                
                # 从style中提取图片URL
                url_pattern = captcha_config.element.url_pattern
                import re
                url_match = re.search(url_pattern, style)
                if not url_match:
                    self.logger.error(f"无法从style中提取图片URL: {style}")
                    raise Exception("无法提取验证码图片URL")
                
                image_url = url_match.group(1)
                if not image_url.startswith('http'):
                    # 将相对URL转换为绝对URL
                    image_url = urljoin(tab.url, image_url)
                
                self.logger.debug(f"提取到验证码图片URL: {image_url}")
                captcha_data = image_url
                
            else:
                # 处理普通图片验证码
                captcha_data = captcha_element.src(base64_to_bytes=True)
            
            self.logger.debug(f"验证码元素已找到")
            
            # 验证码处理
            self.logger.info("开始调用验证码识别服务")
            captcha_text = await self.captcha_service.handle_captcha(
                captcha_data,
                self.site_setup.site_id
            )
            
            if not captcha_text:
                self.logger.error("验证码识别失败 - 返回结果为空")
                raise Exception("验证码识别失败")
            self.logger.debug(f"验证码识别成功 - 结果: {captcha_text}")

            # 填充验证码
            input_selector = captcha_config.input.selector
            self.logger.debug(f"查找验证码输入框 - 选择器: {input_selector}")
            
            captcha_input = tab.ele(input_selector)
            if not captcha_input:
                self.logger.error(f"验证码输入框未找到 - 选择器: {input_selector}")
                raise Exception("验证码输入框未找到")
            
            self.logger.debug(f"找到验证码输入框 - ID: {captcha_input.attr('id')}")
            captcha_input.input(captcha_text)
            self.logger.debug("验证码已填充到输入框")

        except Exception as e:
            self.logger.error("验证码处理失败", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            raise
        
    async def check_login(self, browser: Chromium, simple_check: Optional[bool] = False) -> bool:
        """检查是否已登录（公共接口）"""
        try:
            # 检查登录状态
            if self.site_setup:
                if self.site_setup.crawler.is_logged_in:
                    return True
            
            # 获取当前标签页
            tab = browser.latest_tab
            if not tab:
                return False
                
            if not simple_check:
                # 默认检查，使用verify_login的逻辑检查登录状态
                return await self._verify_login(tab, None)
            else:
                # 简单检查，只要存在，即认为已登录
                return True
            
        except Exception as e:
            self.logger.error(f"检查登录状态时发生错误: {str(e)}")
            return False

    async def _verify_login(self, tab, success_check: Optional[WebElement] = None) -> bool:
        """验证登录是否成功（内部接口）"""
        try:
            self.logger.debug(f"开始验证登录状态")
            
            # 0. 检查最明显的登录成功标志
            if tab.ele('@href^logout', timeout=1):
                self.logger.debug("找到登录成功标志")
                return True
            
            # 1. 首先检查是否存在密码输入框（存在则说明未登录）
            if tab.ele('@type=password'):
                self.logger.warning("页面上存在密码输入框，判定为未登录")
                return False
            
            # 2. 如果配置了特定的成功检查元素，优先进行检查
            if success_check:
                self.logger.debug(f"检查站点特有的登录成功的标志: {success_check.selector}")
                element = tab.ele(success_check.selector, timeout=1)
                
                if element:
                    if hasattr(success_check, 'expect_text'):
                        content = element.text
                        if not success_check.expect_text:
                            expect = self.site_setup.crawler_credential.username
                        else:
                            expect = success_check.expect_text
                        self.logger.debug(f"检查登录成功文本:{content}")
                        self.logger.debug(f"  - 期望文本: {expect}")
                        self.logger.debug(f"  - 实际文本: {content}")
                        if not isinstance(content, list):
                            content = content.split(' ')
                        if expect in content:
                            # 更新登录状态为已登录
                            return True
            
            # 3. 检查是否存在登出相关元素
            range = tab.s_ele('@tag()=body')
            logout_selectors = [
                '@href^logout',
                '@href$logout.php',
                '@href:logout',  # 包含logout的链接
                '@href$usercp.php',  # 用户控制面板链接
                '@data-url:logout',  # data-url属性包含logout
                '@onclick:logout',  # onclick事件包含logout
                '@href:mybonus',  # 魔力值页面链接
                '@lay-on:logout',  # layui的登出按钮
                '@action:logout',  # 登出表单
            ]
            
            for selector in logout_selectors:
                if range.ele(selector, timeout=2):
                    self.logger.debug(f"找到登录成功的标志: {selector}")
                    return True
            
            # 4. 记录当前页面状态
            self.logger.debug(f"当前页面URL: {tab.url}")
            self.logger.debug(f"当前页面标题: {tab.title}")
            
            # 5. 检查错误信息
            await self._check_login_error(tab)
            
            return False
            
        except Exception as e:
            self.logger.error(f"验证登录状态时发生错误: {str(e)}")
            self.logger.debug(f"错误详情: ", exc_info=True)
            return False

    async def _check_login_error(self, tab) -> None:
        """检查登录失败的具体原因"""
        try:
            self.logger.debug("开始检查登录错误原因")
            # 检查特定的错误关键词
            page_text = tab.s_eles('@class=text')
            error_keywords = [
                "图片代码无效",
                "密码错误", "密码不正确",
                "验证码错误", "验证码不正确", "验证码已过期",
                "用户名不存在", "账号不存在",
                "账号已被禁用", "账号已封禁",
                "登录失败", "Login Failed",
                "不要返回，图片代码已被清除！",
                "点击这里获取新的图片代码。"
            ]
            for text in page_text:
                for keyword in error_keywords:
                    if keyword in text.text:
                        self.logger.error(f"登录失败: {keyword}")
                        return

            # 检查常见的错误信息
            error_selectors = {
                # 错误提示框
                'error_box': '@class=error',
                # 具体错误文本
                'error_text': '@class=error_text',
                # 表单错误
                'form_error': 'form .error',
                # 验证码错误
                'captcha_error': '@class=captcha-error'
            }
            
            # 检查所有可能的错误信息
            error_messages = []
            range = tab.s_ele('@tag()=body')
            for selector in error_selectors.values():
                elements = range.eles(selector)
                for element in elements:
                    if element and element.text.strip():
                        error_messages.append(element.text.strip())
            
            # 如果找到错误信息
            if error_messages:
                error_text = ' | '.join(error_messages)
                self.logger.error(f"登录失败，错误信息: {error_text}")
                return
                    
        except Exception as e:
            self.logger.error(f"检查登录错误信息时发生错误: {str(e)}")
            self.logger.debug(f"错误详情: ", exc_info=True)

    async def _is_cloudflare_present(self, tab) -> bool:
        """检查是否存在Cloudflare验证页面"""
        try:
            if tab.title == "Just a moment...":
                return True

            # 检查是否存在 Cloudflare 的 JavaScript 或 Turnstile 验证相关的关键元素
            if tab.ele('script[src*="challenge-platform"]') or tab.ele('@div#challenge-error-text'):
                return True

            # 检查页面文本中是否包含 Cloudflare 验证相关提示
            body_text = tab.text
            if "Checking your browser before accessing" in body_text or "Verify you are human" in body_text:
                return True
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

    async def _handle_pre_login(self, tab, pre_login_config: dict) -> bool:
        """处理pre-login操作"""
        try:
            for action in pre_login_config.get('actions', []):
                action_type = action.get('type')
                selector = action.get('selector')
                wait_time = action.get('wait_time', 2)
                
                self.logger.debug(f"执行pre-login动作: {action_type} - 选择器: {selector}")
                
                if action_type == 'click':
                    element = tab.ele(selector, timeout=5)
                    if not element:
                        self.logger.error(f"未找到pre-login元素 - 选择器: {selector}")
                        return False
                        
                    element.click()
                    self.logger.debug(f"点击了元素: {selector}")
                    
                    if wait_time > 0:
                        self.logger.debug(f"等待 {wait_time} 秒")
                        sleep(wait_time)
                        
                elif action_type == 'bypass-cf-turnstile':
                    cft = tab.ele(selector)
                    if not cft:
                        self.logger.error(f"未找到pre-login元素 - 选择器: {selector}")
                        return False
                    
                    cf_bypasser = CloudflareBypasser(tab)
                    cf_bypasser.click_verification_button()
                    self.logger.debug(f"点击了cf-turnstile验证按钮: {selector}")
                    
                    if wait_time > 0:
                        self.logger.debug(f"等待 {wait_time} 秒")
                        sleep(wait_time)
                        
                elif action_type == 'wait':
                    self.logger.debug(f"等待 {wait_time} 秒")
                    sleep(wait_time)
                    
                elif action_type == 'bypass-ddg':
                    sleep(wait_time)
                    if selector and tab.ele(selector, timeout=3):
                        tab.ele(selector).click()
                    sleep(wait_time*0.2)
                    tab.stop_load()
                    tab.get(self.login_url)
                    self.logger.debug(f"再次访问了登录页面: {self.login_url}")
                else:
                    self.logger.warning(f"未知的pre-login动作类型: {action_type}")
                    
            return True
            
        except Exception as e:
            self.logger.error("Pre-login操作失败", exc_info=True)
            return False