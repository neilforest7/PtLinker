import json
import os
from datetime import datetime
from time import sleep
from typing import Any, Dict, Optional

from DrissionPage import Chromium
from loguru import logger
from models.crawler import CrawlerTaskConfig, LoginConfig
from services.captcha.captcha_service import CaptchaService
from storage.storage_manager import StorageManager


class LoginHandler:
    def __init__(self, task_config: CrawlerTaskConfig):
        self.task_config = task_config
        self.logger = logger.bind(task_id=task_config.task_id)
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

            # 等待登录表单
            self.logger.debug(f"等待登录表单出现，选择器: {login_config.form_selector}")
            form = tab.ele(login_config.form_selector, timeout=10)
            if not form:
                self.logger.error(f"登录表单未找到 - 选择器: {login_config.form_selector}")
                raise Exception("登录表单未找到")
            self.logger.debug(f"登录表单已找到 - 元素ID: {form.attr('id')}, 类名: {form.attr('class')}")

            # 填充表单字段
            self.logger.debug("开始填充表单字段")
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
            if login_config.captcha:
                self.logger.debug("检测到验证码配置")
                # 检查站点的验证码处理方式
                site_method = os.getenv('CAPTCHA_SITE_METHODS', '{}')
                try:
                    site_methods = json.loads(site_method)
                    if site_methods.get(self.task_config.site_id) == 'skip':
                        self.logger.info(f"站点 {self.task_config.site_id} 配置为跳过验证码")
                    else:
                        self.logger.debug("开始验证码处理流程")
                        await self._handle_captcha(tab, login_config)
                except json.JSONDecodeError:
                    self.logger.warning("解析站点验证码配置失败，继续处理验证码")
                    await self._handle_captcha(tab, login_config)
                self.logger.debug("验证码处理完成")


            submit_btn = login_config.fields.get('submit')
            if submit_btn:
                self.logger.debug(f"使用配置的提交按钮 - 选择器: {submit_btn.selector}")
                submit_btn = tab.ele(submit_btn.selector)
                if submit_btn:
                    self.logger.debug(f"找到提交按钮 - ID: {submit_btn.attr('id')}, 文本: {submit_btn.text}")
                    submit_btn.click()
                    self.logger.debug("已点击提交按钮")
                else:
                    self.logger.warning(f"未找到配置的提交按钮: {submit_btn.selector}")
            else:
                default_submit = f"{login_config.form_selector} [type=submit]"
                self.logger.debug(f"使用默认提交按钮 - 选择器: {default_submit}")
                submit_btn = tab.ele(default_submit)
                if submit_btn:
                    self.logger.debug(f"找到默认提交按钮 - ID: {submit_btn.attr('id')}, 文本: {submit_btn.text}")
                    submit_btn.click()
                    self.logger.debug("已点击默认提交按钮")
                else:
                    self.logger.warning("未找到任何提交按钮")

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

        except Exception as e:
            self.logger.error(f"登录过程发生错误: {str(e)}", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            self.logger.debug(f"错误堆栈: ", exc_info=True)
            return False

    async def _handle_captcha(self, tab, login_config: LoginConfig) -> None:
        """处理验证码"""
        if not login_config.captcha:
            return

        try:
            # 获取验证码元素
            self.logger.debug(f"等待验证码元素 - 选择器: {login_config.captcha.element['selector']}")
            captcha_element = tab.ele(login_config.captcha.element["selector"], timeout=10)
            if not captcha_element:
                self.logger.error(f"验证码元素未找到 - 选择器: {login_config.captcha.element['selector']}")
                raise Exception("验证码元素未找到")
            
            self.logger.debug(f"验证码元素已找到 - ID: {captcha_element.attr('id')}")
            
            # 使用验证码服务处理
            self.logger.debug("开始调用验证码识别服务")
            captcha_text = await self.captcha_service.handle_captcha(
                captcha_element,
                self.task_config.site_id
            )
            
            if not captcha_text:
                self.logger.error("验证码识别失败 - 返回结果为空")
                raise Exception("验证码识别失败")
            self.logger.debug(f"验证码识别成功 - 结果: {captcha_text}")

            # 填充验证码
            self.logger.debug(f"查找验证码输入框 - 选择器: {login_config.captcha.input.selector}")
            captcha_input = tab.ele(login_config.captcha.input.selector)
            if not captcha_input:
                self.logger.error(f"验证码输入框未找到 - 选择器: {login_config.captcha.input.selector}")
                raise Exception("验证码输入框未找到")
            
            self.logger.debug(f"找到验证码输入框 - ID: {captcha_input.attr('id')}")
            captcha_input.input(captcha_text)
            self.logger.debug("验证码已填充到输入框")

            # 处理验证码hash
            if login_config.captcha.hash:
                self.logger.debug("检测到验证码hash配置")
                hash_selector = login_config.captcha.hash.get('selector')
                if hash_selector:
                    self.logger.debug(f"查找hash元素 - 选择器: {hash_selector}")
                    hash_element = tab.ele(hash_selector)
                    if hash_element:
                        hash_value = hash_element.attr('value')
                        if hash_value:
                            target_field = login_config.captcha.hash.get('targetField', 'imagehash')
                            self.logger.debug(f"查找hash输入框 - 名称: {target_field}")
                            hash_input = tab.ele(f'input[name="{target_field}"]')
                            if hash_input:
                                hash_input.input(hash_value)
                                self.logger.debug(f"已填充验证码hash: {hash_value}")
                            else:
                                self.logger.warning(f"未找到hash输入框: {target_field}")
                    else:
                        self.logger.warning(f"未找到hash元素: {hash_selector}")

        except Exception as e:
            self.logger.error(f"验证码处理失败: {str(e)}", exc_info=True)
            self.logger.debug(f"错误详情: {type(e).__name__}")
            self.logger.debug(f"错误堆栈: ", exc_info=True)
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
            self.logger.error(f"登录验证失败: {str(e)}")
            self.logger.debug(f"错误详情: {type(e).__name__}")
            self.logger.debug(f"错误堆栈: ", exc_info=True)
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
            self.logger.error(f"保存浏览器状态失败: {str(e)}")
            self.logger.debug(f"错误详情: {type(e).__name__}")
            self.logger.debug(f"错误堆栈: ", exc_info=True)
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
            self.logger.error(f"加载浏览器状态失败: {str(e)}")
            self.logger.debug(f"错误详情: {type(e).__name__}")
            self.logger.debug(f"错误堆栈: ", exc_info=True)
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
                
                self.logger.debug("完整Cookies恢复完成")
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
            self.logger.error(f"恢复浏览器状态失败: {str(e)}")
            self.logger.debug(f"错误详情: {type(e).__name__}")
            self.logger.debug(f"错误堆栈: ", exc_info=True)
            return False