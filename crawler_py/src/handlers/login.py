import json
import os
from datetime import datetime
from time import sleep
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import DrissionPage
from utils.CloudflareBypasser import CloudflareBypasser
from DrissionPage import Chromium
from loguru import logger
from models.crawler import CrawlerTaskConfig, LoginConfig
from services.captcha.captcha_service import CaptchaService
from storage.storage_manager import StorageManager


class LoginHandler:
    def __init__(self, task_config: CrawlerTaskConfig):
        self.task_config = task_config
        self.logger = logger.bind(task_id=task_config.task_id, site_id=task_config.site_id)
        self.logger.debug(f"初始化LoginHandler - 任务ID: {task_config.task_id}, 站点ID: {task_config.site_id}")
        self.captcha_service = CaptchaService()
        
        # 初始化站点状态存储（cookies等）
        state_storage_config = {
            'type': 'file',
            'base_dir': f"storage/state/{task_config.site_id}",
            'compress': False,  # cookies等状态数据不压缩，方便读取
            'backup': True,
            'max_backups': 5  # 保留更多的状态备份
        }
        self.logger.debug(f"初始化状态存储 - 配置: {state_storage_config}")
        self.state_storage = StorageManager(state_storage_config)

    async def perform_login(self, browser: Chromium, login_config: LoginConfig) -> bool:
        """执行登录流程"""
        try:
            self.logger.info(f"开始登录流程 - URL: {login_config.login_url}")
            self.logger.debug(f"浏览器实例ID: {id(browser)}")
            
            # 创建新标签页
            tab = browser.new_tab()
            browser.activate_tab(tab)
            self.logger.debug(f"创建新标签页 - 标签页ID: {id(tab)}")
            
            # 导航到登录页面
            self.logger.debug(f"正在导航到登录页面: {login_config.login_url}")
            tab.get(login_config.login_url)
            self.logger.debug(f"页面标题: {tab.title}")
            self.logger.debug(f"页面URL: {tab.url}")

            # 执行pre-login操作
            if hasattr(login_config, 'pre_login') and login_config.pre_login:
                self.logger.info("开始执行pre-login操作")
                if not await self._handle_pre_login(tab, login_config.pre_login):
                    self.logger.error("Pre-login操作失败")
                    return False
                self.logger.info("Pre-login操作完成")

            # 等待登录表单
            self.logger.debug(f"等待登录表单出现，选择器: {login_config.form_selector}")
            form = tab.ele(login_config.form_selector, timeout=5)
            if not form:
                # 如果没有找到登录表单，再次检查是否是Cloudflare页面
                self.logger.debug("未找到登录表单，开始检查Cloudflare验证")
                if await self._is_cloudflare_present(tab):
                    self.logger.info("检测到Cloudflare验证页面")
                    if not await self._handle_cloudflare(tab):
                        self.logger.error("Cloudflare验证失败")
                        return False
                    # 验证通过后重新检查登录表单
                    form = tab.ele(login_config.form_selector, timeout=10)
                    if not form:
                        self.logger.error(f"登录表单未找到 - 选择器: {login_config.form_selector}")
                        raise Exception("登录表单未找到")
                else:
                    self.logger.error(f"登录表单未找到 - 选择器: {login_config.form_selector}")
                    raise Exception("登录表单未找到")
            self.logger.debug(f"登录表单已找到 - 元素ID: {form.attr('id')}, 类名: {form.attr('class')}")

            # 填充表单字段
            self.logger.info("开始填充表单字段")
            for field_name, field_config in login_config.fields.items():
                if field_config.type != "submit":
                    self.logger.debug(f"处理字段 {field_name}:")
                    self.logger.debug(f"  - 选择器: {field_config.selector}")
                    self.logger.debug(f"  - 类型: {field_config.type}")
                    input_ele = tab.ele(field_config.selector)
                    if input_ele:
                        self.logger.debug(f"  - 找到输入元素 - ID: {input_ele.attr('id')}")
                        # 对密码字段做特殊处理，不记录实际密码
                        if field_config.type == "password":
                            self.logger.debug(f"  - 正在填充密码字段: {field_config.value}")
                            sleep(0.5)
                            input_ele.clear()
                            self.logger.debug(f"  - 已清空密码字段")
                            input_ele.input(str(field_config.value))
                        else:
                            self.logger.debug(f"  - 正在填充{field_name}: {field_config.value}")
                            sleep(0.5)
                            input_ele.clear()
                            self.logger.debug(f"  - 已清空{field_name}字段")
                            input_ele.input(str(field_config.value))
                    else:
                        self.logger.warning(f"  - 未找到输入元素: {field_config.selector}")
            self.logger.debug("表单字段填充完成")
            
            # 处理验证码
            # 检查站点的验证码处理方式
            skipped_sites = os.getenv('CAPTCHA_SKIP_SITES', '')
            if skipped_sites and self.task_config.site_id in skipped_sites:
                self.logger.info(f"站点 {self.task_config.site_id} 配置为跳过验证码")
            elif login_config.captcha:
                self.logger.debug("开始处理验证码")
                try:
                    self.logger.debug("开始验证码处理流程")
                    await self._handle_captcha(tab, login_config)
                except json.JSONDecodeError:
                    self.logger.warning("解析站点验证码配置失败")
                    raise Exception("解析站点验证码配置失败")
                self.logger.info("验证码处理完成")

            # 获取提交按钮
            submit_config = login_config.fields.get('submit')
            self.logger.debug(f"------ 选择器: {submit_config.selector}")
            if not submit_config:
                submit_config = f"{login_config.form_selector} [type=submit]"
                self.logger.debug(f"使用默认提交按钮 - 选择器: {submit_config}")
            if not submit_config:
                self.logger.warning("未找到任何提交按钮")
                return False
            submit_btn = tab.ele(submit_config.selector)
            self.logger.debug(f"使用配置的提交按钮 - 选择器: {submit_config.selector}")
            if submit_btn:
                self.logger.debug(f"找到提交按钮 - ID: {submit_btn.attr('id')}, 文本: {submit_btn.text}")
                submit_btn.click()
                self.logger.debug("已点击提交按钮")
            else:
                self.logger.warning(f"未找到配置的提交按钮: {submit_btn.selector}")

            # 验证登录结果
            self.logger.debug("开始验证登录结果")
            success = await self._verify_login(tab, login_config.success_check)
            
            if success:
                self.logger.info("登录成功，准备保存浏览器状态")
                await self._save_browser_state(browser)
            else:
                self.logger.error("登录失败 - 未找到成功登录的标识")
                self.logger.debug(f"当前页面URL: {tab.url}")
                self.logger.debug(f"当前页面标题: {tab.title}")

            # 关闭标签页
            self.logger.debug("正在关闭登录标签页")
            tab.close()
            return success
        
        except DrissionPage.errors.ElementNotFoundError as e:
            self.logger.error("登录过程找不到元素", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            return False
        except Exception as e:
            self.logger.error("登录过程发生错误", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            return False

    async def _handle_captcha(self, tab, login_config: LoginConfig) -> None:
        """处理验证码"""
        if not login_config.captcha:
            return

        try:
            captcha_config = login_config.captcha
            captcha_type = captcha_config.type
            
            self.logger.debug(f"等待验证码元素 - 选择器: {captcha_config.element['selector']}")
            captcha_element = tab.ele(captcha_config.element["selector"], timeout=3)
            if not captcha_element:
                self.logger.error(f"验证码元素未找到 - 选择器: {captcha_config.element['selector']}")
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
                url_pattern = captcha_config.element.get('url_pattern', r'url\("([^"]+)"\)')
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
                self.task_config.site_id
            )
            
            if not captcha_text:
                self.logger.error("验证码识别失败 - 返回结果为空")
                raise Exception("验证码识别失败")
            self.logger.debug(f"验证码识别成功 - 结果: {captcha_text}")

            # 填充验证码
            self.logger.debug(f"查找验证码输入框 - 选择器: {captcha_config.input.selector}")
            captcha_input = tab.ele(captcha_config.input.selector)
            if not captcha_input:
                self.logger.error(f"验证码输入框未找到 - 选择器: {captcha_config.input.selector}")
                raise Exception("验证码输入框未找到")
            
            self.logger.debug(f"找到验证码输入框 - ID: {captcha_input.attr('id')}")
            captcha_input.input(captcha_text)
            self.logger.debug("验证码已填充到输入框")

            # # 处理验证码hash
            # if hasattr(captcha_config, 'hash') and captcha_config.hash:
            #     self.logger.debug("检测到验证码hash配置")
            #     hash_selector = captcha_config.hash.get('selector')
            #     if hash_selector:
            #         self.logger.debug(f"查找hash元素 - 选择器: {hash_selector}")
            #         hash_element = tab.ele(hash_selector)
            #         if hash_element:
            #             hash_value = hash_element.attr('value')
            #             if hash_value:
            #                 target_field = captcha_config.hash.get('targetField', 'imagehash')
            #                 self.logger.debug(f"查找hash输入框 - 名称: {target_field}")
            #                 hash_input = tab.ele(f'input[name="{target_field}"]')
            #                 if hash_input:
            #                     hash_input.input(hash_value)
            #                     self.logger.debug(f"已填充验证码hash: {hash_value}")
            #                 else:
            #                     self.logger.warning(f"未找到hash输入框: {target_field}")
            #         else:
            #             self.logger.warning(f"未找到hash元素: {hash_selector}")

        except Exception as e:
            self.logger.error("验证码处理失败", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            raise

    async def _verify_login(self, tab, success_check: Dict[str, str]) -> bool:
        """验证登录是否成功"""
        try:
            self.logger.debug(f"开始验证登录状态")
            self.logger.debug(f"检查成功标识 - 选择器: {success_check['selector']}")
            element = tab.ele(success_check["selector"], timeout=5)
            
            if not element:
                self.logger.warning(f"未找到成功标识元素: {success_check['selector']}")
                self.logger.debug(f"当前页面URL: {tab.url}")
                self.logger.debug(f"当前页面标题: {tab.title}")
                return False
                
            if "expected_text" in success_check:
                content = element.child().text
                self.logger.debug(f"检查登录成功文本:")
                self.logger.debug(f"  - 期望文本: {success_check['expected_text']}")
                self.logger.debug(f"  - 实际文本: {content}")
                return success_check["expected_text"] in (content or "")
            
            self.logger.debug("登录验证成功")
            return True
            
        except Exception as e:
            self.logger.error("登录验证失败", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            return False

    async def _save_browser_state(self, browser: Chromium) -> bool:
        """保存浏览器状态（cookies等）"""
        try:
            self.logger.info("开始保存浏览器状态")
            
            # 获取当前标签页
            tab = browser.latest_tab
            self.logger.debug(f"当前签页 - URL: {tab.url}")
            
            # 获取cookies（使用DrissionPage的cookies方法）
            cookies = tab.cookies(all_domains=False, all_info=True)
            self.logger.debug(f"获取到cookies - 数量: {len(cookies)}")
            
            # 记录cookies的详细信息
            for cookie in cookies:
                self.logger.debug(f"Cookie: {cookie.get('name')} = {cookie.get('value')} "
                                f"[domain: {cookie.get('domain')}, "
                                f"path: {cookie.get('path')}, "
                                f"expires: {cookie.get('expires')}]")
            
            # 获取localStorage
            local_storage = tab.run_js("return Object.entries(localStorage)")
            self.logger.debug(f"获取到localStorage项 - 数量: {len(local_storage) if local_storage else 0}")
            
            # 获取sessionStorage
            session_storage = tab.run_js("return Object.entries(sessionStorage)")
            self.logger.debug(f"获取到sessionStorage项 - 数量: {len(session_storage) if session_storage else 0}")
            
            # 准备状态数据
            state_data = {
                'cookies': cookies.as_dict(),  # 使用as_dict()方法转换为字典格式
                'cookies_full': cookies,  # 保存完整的cookies信息
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
            
            self.logger.debug(f"准备保存状态数据:")
            self.logger.debug(f"  - 时间戳: {state_data['timestamp']}")
            self.logger.debug(f"  - 用户名: {state_data['loginState']['username']}")
            self.logger.debug(f"  - Cookies数量: {len(state_data['cookies'])}")
            
            # 保存状态数据到固定位置
            success = await self.state_storage.save(
                state_data,
                'browser_state.json',
                backup=True
            )
            
            if success:
                self.logger.info("浏览器状态保存成功")
                self.logger.debug(f"保存位置: storage/state/{self.task_config.site_id}/browser_state.json")
            else:
                self.logger.error("浏览器状态保存失败")
            
            return success
            
        except Exception as e:
            self.logger.error("保存浏览器状态失败", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            return False

    async def load_browser_state(self) -> Optional[Dict[str, Any]]:
        """加载浏览器状态"""
        try:
            self.logger.info("开始加载浏览器状态")
            self.logger.debug(f"状态文件路径: storage/state/{self.task_config.site_id}/browser_state.json")
            
            # 从固定位置加载状态数据
            state_data = await self.state_storage.load('browser_state.json')
            
            if not state_data:
                self.logger.warning("未找到浏览器状态数据")
                return None
            
            # 验证数据完整性
            required_fields = ['cookies', 'loginState', 'timestamp']
            self.logger.debug("验证状态数据完整性")
            for field in required_fields:
                if field not in state_data:
                    self.logger.warning(f"状态数据缺少必需字段: {field}")
                    return None
            
            # 检查登录状态是否过期
            timestamp = datetime.fromisoformat(state_data['timestamp'])
            days_old = (datetime.now() - timestamp).days
            self.logger.debug(f"状态数据年龄: {days_old}天")
            
            if days_old > 7:  # 7天过期
                self.logger.warning(f"浏览器状态已过期 ({days_old}天)")
                return None
            
            self.logger.info("浏览器状态加载成功")
            self.logger.debug(f"状态数据概览:")
            self.logger.debug(f"  - Cookies数量: {len(state_data['cookies'])}")
            self.logger.debug(f"  - localStorage项数: {len(state_data.get('localStorage', {}))}")
            self.logger.debug(f"  - sessionStorage项数: {len(state_data.get('sessionStorage', {}))}")
            self.logger.debug(f"  - 最后登录时间: {datetime.fromtimestamp(state_data['loginState']['lastLoginTime']/1000)}")
            
            return state_data
            
        except Exception as e:
            self.logger.error("加载浏览器状态失败", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            return None

    async def restore_browser_state(self, browser: Chromium) -> bool:
        """恢复浏览器状态"""
        try:
            self.logger.info("开始恢复浏览器状态")
            self.logger.debug(f"浏览器实例ID: {id(browser)}")
            
            # 加载状态数据
            state_data = await self.load_browser_state()
            if not state_data:
                self.logger.warning("无法加载浏览器状态")
                return False
            
            # 获取当前标签页
            tab = browser.latest_tab
            self.logger.debug(f"当前标签页 - URL: {tab.url}")
            
            # 恢复cookies
            if 'cookies_full' in state_data:
                cookies_list = state_data['cookies_full']
                self.logger.debug(f"开始恢复完整cookies - 数量: {len(cookies_list)}")
                
                # 将cookies按域名分组
                cookies_by_domain = {}
                for cookie in cookies_list:
                    domain = cookie.get('domain', '')
                    if domain not in cookies_by_domain:
                        cookies_by_domain[domain] = []
                    cookies_by_domain[domain].append(cookie)
                
                # 按域名设置cookies
                for domain, domain_cookies in cookies_by_domain.items():
                    self.logger.debug(f"设置域名 {domain} 的cookies - 数量: {len(domain_cookies)}")
                    try:
                        # 使用dict格式设置cookies
                        cookies_dict = {
                            cookie['name']: cookie['value']
                            for cookie in domain_cookies
                        }
                        cookies_dict['domain'] = domain
                        tab.set.cookies(cookies_dict)
                        
                        # 设置每个cookie的其他属性（如过期时间、路径等）
                        for cookie in domain_cookies:
                            cookie_str = f"{cookie['name']}={cookie['value']}; "
                            if 'domain' in cookie:
                                cookie_str += f"domain={cookie['domain']}; "
                            if 'path' in cookie:
                                cookie_str += f"path={cookie['path']}; "
                            if 'expires' in cookie:
                                cookie_str += f"expires={cookie['expires']}; "
                            if 'secure' in cookie and cookie['secure']:
                                cookie_str += "secure; "
                            if 'httpOnly' in cookie and cookie['httpOnly']:
                                cookie_str += "httpOnly; "
                            tab.set.cookies(cookie_str)
                            
                    except Exception as e:
                        self.logger.warning(f"设置域名 {domain} 的cookies时出错: {str(e)}")
                        continue
                
                self.logger.info("完整Cookies恢复完成")
            else:
                # 使用基本cookie信息（向后兼容）
                cookies_dict = state_data['cookies']
                self.logger.debug(f"开始恢复基本cookies - 数量: {len(cookies_dict)}")
                try:
                    tab.set.cookies(cookies_dict)
                    self.logger.debug("基本Cookies恢复完成")
                except Exception as e:
                    self.logger.error(f"恢复基本cookies时出错: {str(e)}")
            
            # 恢复localStorage
            if state_data.get('localStorage'):
                self.logger.debug(f"开始恢复localStorage - 项数: {len(state_data['localStorage'])}")
                js_code = """
                (state) => {
                    for (const [key, value] of Object.entries(state)) {
                        localStorage.setItem(key, value);
                    }
                }
                """
                tab.run_js(js_code, state_data['localStorage'])
                self.logger.debug("localStorage恢复完成")
            
            # 恢复sessionStorage
            if state_data.get('sessionStorage'):
                self.logger.debug(f"开始恢复sessionStorage - 项数: {len(state_data['sessionStorage'])}")
                js_code = """
                (state) => {
                    for (const [key, value] of Object.entries(state)) {
                        sessionStorage.setItem(key, value);
                    }
                }
                """
                tab.run_js(js_code, state_data['sessionStorage'])
                self.logger.debug("sessionStorage恢复完成")
            
            self.logger.info("浏览器状态恢复成功")
            return True
            
        except Exception as e:
            self.logger.error("恢复浏览器状态失败", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            return False

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
                self.logger.info("Cloudflare验证已完成")
                return True
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
                else:
                    self.logger.warning(f"未知的pre-login动作类型: {action_type}")
                    
            return True
            
        except Exception as e:
            self.logger.error("Pre-login操作失败", exc_info=True)
            return False