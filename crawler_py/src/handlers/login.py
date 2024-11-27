import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
import os
import json

from loguru import logger
from models.crawler import CrawlerTaskConfig, LoginConfig
from playwright.async_api import Page
from services.captcha.captcha_service import CaptchaService
from storage.storage_manager import StorageManager


class LoginHandler:
    def __init__(self, task_config: CrawlerTaskConfig):
        self.task_config = task_config
        self.logger = logger.bind(task_id=task_config.task_id)
        self.captcha_service = CaptchaService()
        
        # 初始化站点状态存储（cookies等）
        state_storage_config = {
            'type': 'file',
            'base_dir': f"storage/state/{task_config.site_id}",
            'compress': False,  # cookies等状态数据不压缩，方便读取
            'backup': True,
            'max_backups': 5  # 保留更多的状态备份
        }
        self.state_storage = StorageManager(state_storage_config)

    async def perform_login(self, page: Page, login_config: LoginConfig) -> bool:
        """执行登录流程"""
        try:
            self.logger.info(f"开始登录流程 - URL: {login_config.login_url}")
            
            # 导航到登录页面
            self.logger.debug(f"正在导航到登录页面: {login_config.login_url}")
            await page.goto(login_config.login_url)
            await page.wait_for_load_state("networkidle")
            self.logger.debug("页面加载完成")

            # 等待登录表单
            self.logger.debug(f"等待登录表单出现，选择器: {login_config.form_selector}")
            await page.wait_for_selector(login_config.form_selector)
            self.logger.debug("登录表单已找到")

            # 填充表单字段
            self.logger.debug("开始填充表单字段")
            for field_name, field_config in login_config.fields.items():
                if field_config.type != "submit":
                    self.logger.debug(f"填充字段 {field_name}: 选择器 {field_config.selector}")
                    await page.fill(field_config.selector, str(field_config.value))
            self.logger.debug("表单字段填充完成")

            # 处理验证码
            if login_config.captcha:
                # 检查站点的验证码处理方式
                site_method = os.getenv('CAPTCHA_SITE_METHODS', '{}')
                try:
                    site_methods = json.loads(site_method)
                    if site_methods.get(self.task_config.site_id) == 'skip':
                        self.logger.info(f"站点 {self.task_config.site_id} 配置为跳过验证码")
                    else:
                        self.logger.debug("检测到验证码，开始处理")
                        await self._handle_captcha(page, login_config)
                except json.JSONDecodeError:
                    self.logger.warning("解析站点验证码配置失败，继续处理验证码")
                    await self._handle_captcha(page, login_config)
                self.logger.debug("验证码处理完成")

            # 提交表单
            submit_field = next(
                (f for f in login_config.fields.values() if f.type == "submit"),
                None
            )
            if submit_field:
                self.logger.debug(f"使用提交按钮选择器: {submit_field.selector}")
                await page.click(submit_field.selector)
            else:
                default_submit = f"{login_config.form_selector} [type=submit]"
                self.logger.debug(f"使用默认提交按钮选择器: {default_submit}")
                await page.click(default_submit)

            # 等待导航完成
            self.logger.debug("等待页面导航完成")
            await page.wait_for_load_state("networkidle")

            # 验证登录结果
            self.logger.debug("开始验证登录结果")
            success = await self._verify_login(page, login_config.success_check)
            
            if success:
                self.logger.info("登录成功，保存cookies和状态")
                await self._save_browser_state(page)
            else:
                self.logger.error("登录失败 - 未找到成功登录的标识")

            return success

        except Exception as e:
            self.logger.error(f"登录过程发生错误: {str(e)}", exc_info=True)
            return False

    async def _handle_captcha(self, page: Page, login_config: LoginConfig) -> None:
        """处理验证码"""
        if not login_config.captcha:
            return

        try:
            # 获取验证码图片
            self.logger.debug(f"等待验证码元素，选择器: {login_config.captcha.element['selector']}")
            captcha_element = await page.wait_for_selector(
                login_config.captcha.element["selector"]
            )
            self.logger.debug("验证码元素已找到，开始截图")
            captcha_image = await captcha_element.screenshot()
            self.logger.debug("验证码截图完成")

            # 解析验证码
            self.logger.debug("开始解析验证码")
            captcha_text = await self.captcha_service.handle_captcha(
                captcha_image,
                self.task_config.site_id
            )
            if not captcha_text:
                raise Exception("验证码识别失败")
            self.logger.debug(f"验证码解析结果: {captcha_text}")

            # 填充验证码
            self.logger.debug(f"填充验证码到输入框: {login_config.captcha.input.selector}")
            await page.fill(
                login_config.captcha.input.selector,
                captcha_text
            )
            self.logger.debug("验证码填充完成")

            # 处理验证码hash（如果有）
            if login_config.captcha.hash:
                hash_selector = login_config.captcha.hash.get('selector')
                if hash_selector:
                    hash_value = await page.get_attribute(hash_selector, 'value')
                    if hash_value:
                        target_field = login_config.captcha.hash.get('targetField', 'imagehash')
                        await page.fill(f'input[name="{target_field}"]', hash_value)
                        self.logger.debug(f"已填充验证码hash: {hash_value}")

        except Exception as e:
            self.logger.error(f"验证码处理失败: {str(e)}", exc_info=True)
            raise

    async def _verify_login(self, page: Page, success_check: Dict[str, str]) -> bool:
        """验证登录是否成功"""
        try:
            self.logger.debug(f"等待登录成功标识元素，选择器: {success_check['selector']}")
            await page.wait_for_selector(
                success_check["selector"],
                timeout=5000
            )
            if "expected_text" in success_check:
                content = await page.text_content(success_check["selector"])
                self.logger.debug(f"检查登录成功文本，期望: {success_check['expected_text']}, 实际: {content}")
                return success_check["expected_text"] in (content or "")
            self.logger.debug("登录验证成功")
            return True
        except Exception as e:
            self.logger.debug(f"登录验证失败: {str(e)}")
            return False

    async def _save_browser_state(self, page: Page) -> bool:
        """保存浏览器状态（cookies等）"""
        try:
            self.logger.info("开始保存浏览器状态")
            
            # 获取cookies
            cookies = await page.context.cookies()
            self.logger.debug(f"获取到 {len(cookies)} 个cookies")
            
            # 获取localStorage
            local_storage = await page.evaluate("() => Object.entries(localStorage)")
            
            # 获取sessionStorage
            session_storage = await page.evaluate("() => Object.entries(sessionStorage)")
            
            # 准备状态数据
            state_data = {
                'cookies': cookies,
                'localStorage': dict(local_storage) if local_storage else {},
                'sessionStorage': dict(session_storage) if session_storage else {},
                'loginState': {
                    'isLoggedIn': True,
                    'lastLoginTime': datetime.now().timestamp() * 1000,
                    'username': self.task_config.username
                },
                'timestamp': datetime.now().isoformat(),
                'siteId': self.task_config.site_id
            }
            
            # 保存状态数据到固定位置
            success = await self.state_storage.save(
                state_data,
                'browser_state.json',
                backup=True
            )
            
            if success:
                self.logger.info("浏览器状态保存成功")
            else:
                self.logger.error("浏览器状态保存失败")
            
            return success
            
        except Exception as e:
            self.logger.error(f"保存浏览器状态失败: {str(e)}", exc_info=True)
            return False

    async def load_browser_state(self) -> Optional[Dict[str, Any]]:
        """加载浏览器状态"""
        try:
            self.logger.info("开始加载浏览器状态")
            
            # 从固定位置加载状态数据
            state_data = await self.state_storage.load('browser_state.json')
            
            if not state_data:
                self.logger.warning("未找到浏览器状态数据")
                return None
            
            # 验证数据完整性
            required_fields = ['cookies', 'loginState', 'timestamp']
            for field in required_fields:
                if field not in state_data:
                    self.logger.warning(f"状态数据缺少必需字段: {field}")
                    return None
            
            # 检查登录状态是否过期
            timestamp = datetime.fromisoformat(state_data['timestamp'])
            if (datetime.now() - timestamp).days > 7:  # 7天过期
                self.logger.warning("浏览器状态已过期")
                return None
            
            self.logger.info("浏览器状态加载成功")
            self.logger.debug(f"状态数据: cookies数量={len(state_data['cookies'])}")
            
            return state_data
            
        except Exception as e:
            self.logger.error(f"加载浏览器状态失败: {str(e)}", exc_info=True)
            return None

    async def restore_browser_state(self, page: Page) -> bool:
        """恢复浏览器状态"""
        try:
            self.logger.info("开始恢复浏览器状态")
            
            # 加载状态数据
            state_data = await self.load_browser_state()
            if not state_data:
                self.logger.warning("无法加载浏览器状态")
                return False
            
            # 恢复cookies
            await page.context.add_cookies(state_data['cookies'])
            self.logger.debug(f"已恢复 {len(state_data['cookies'])} 个cookies")
            
            # 恢复localStorage
            if state_data.get('localStorage'):
                await page.evaluate(
                    """state => {
                        for (const [key, value] of Object.entries(state)) {
                            localStorage.setItem(key, value);
                        }
                    }""",
                    state_data['localStorage']
                )
                self.logger.debug("已恢复localStorage")
            
            # 恢复sessionStorage
            if state_data.get('sessionStorage'):
                await page.evaluate(
                    """state => {
                        for (const [key, value] of Object.entries(state)) {
                            sessionStorage.setItem(key, value);
                        }
                    }""",
                    state_data['sessionStorage']
                )
                self.logger.debug("已恢复sessionStorage")
            
            self.logger.info("浏览器状态恢复成功")
            return True
            
        except Exception as e:
            self.logger.error(f"恢复浏览器状态失败: {str(e)}", exc_info=True)
            return False