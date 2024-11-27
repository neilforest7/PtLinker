import sys
import time
import json
import logging
import argparse
from typing import Dict, Optional
from DrissionPage import ChromiumPage, ChromiumOptions

def setup_logging():
    logger = logging.getLogger('login_handler')
    logger.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    return logger

class LoginResult:
    def __init__(self, success: bool, cookies: list = None, error: str = None):
        self.success = success
        self.cookies = cookies or []
        self.error = error

    def to_dict(self) -> dict:
        return {
            "status": "success" if self.success else "error",
            "cookies": self.cookies if self.success else None,
            "error": self.error if not self.success else None
        }

class LoginHandler:
    def __init__(self, browser_path: str = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'):
        self.logger = setup_logging()
        self.browser = None
        self.browser_path = browser_path
        self._init_browser_config()

    def _init_browser_config(self) -> None:
        """初始化浏览器配置"""
        try:
            # 重定向标准输出以捕获DrissionPage的配置信息
            import sys
            import io
            original_stdout = sys.stdout
            sys.stdout = io.StringIO()
            
            ChromiumOptions().set_browser_path(self.browser_path).save()
            
            sys.stdout = original_stdout
            self.logger.info("浏览器配置初始化完成")
        except Exception as e:
            self.logger.error(f"浏览器配置初始化失败: {str(e)}")
            raise

    def handle_login(self, url: str, username: str, password: str) -> LoginResult:
        """处理完整的登录流程"""
        try:
            # 创建新的页面实例
            self.browser = ChromiumPage()
            self.logger.info(f"开始访问URL: {url}")
            self.browser.get(url)

            # 处理可能的Cloudflare验证
            if not self._handle_cloudflare():
                return LoginResult(False, error="Cloudflare验证失败")

            # 等待登录表单
            self.logger.info("等待登录表单加载...")
            if not self._wait_for_login_form():
                return LoginResult(False, error="未找到登录表单")

            # 执行登录
            if not self._perform_login(username, password):
                return LoginResult(False, error="登录失败")

            # 验证登录结果
            if not self._verify_login():
                return LoginResult(False, error="登录验证失败")

            # 获取所有cookies
            cookies = self._get_all_cookies()
            
            return LoginResult(True, cookies=cookies)

        except Exception as e:
            self.logger.error(f"登录过程出错: {str(e)}")
            return LoginResult(False, error=str(e))
        finally:
            if self.browser:
                self.browser.quit()

    def _handle_cloudflare(self) -> bool:
        """处理Cloudflare验证"""
        try:
            # 检查是否需要处理Cloudflare验证
            if not self._is_cloudflare_present():
                self.logger.info("未检测到Cloudflare验证")
                return True

            self.logger.info("等待Cloudflare验证完成...")
            start_time = time.time()
            while time.time() - start_time < 30:
                if not self._is_cloudflare_present():
                    self.logger.info("Cloudflare验证已完成")
                    return True
                time.sleep(1)

            self.logger.error("Cloudflare验证超时")
            return False

        except Exception as e:
            self.logger.error(f"Cloudflare验证处理出错: {str(e)}")
            return False

    def _is_cloudflare_present(self) -> bool:
        """检查是否存在Cloudflare验证页面"""
        try:
            cloudflare_indicators = [
                "//iframe[contains(@src, 'challenges.cloudflare.com')]",
                "//div[@class='cf-browser-verification']",
                "//*[contains(text(), 'Checking if the site connection is secure')]",
                "//*[contains(text(), '正在验证您的浏览器')]"
            ]
            
            page_source = self.browser.html.lower()
            if "cloudflare" not in page_source:
                return False
                
            for indicator in cloudflare_indicators:
                try:
                    element = self.browser.ele(indicator)
                    if element and element.is_displayed:
                        return True
                except:
                    continue
                    
            return False
        except:
            return False

    def _wait_for_login_form(self) -> bool:
        """等待登录表单加载"""
        try:
            time.sleep(5)
            login_form_indicators = self.browser.wait.ele_displayed('@action=takelogin.php')
            self.logger.info(f"找到登录表单: {login_form_indicators}")
            # 等待用户名和密码输入框
            username_input = self.browser.wait.ele_displayed('@name=username', timeout=5)
            self.logger.info(f"找到用户名输入框: {username_input}")
            password_input = self.browser.wait.ele_displayed('@name=password', timeout=5)
            self.logger.info(f"找到密码输入框: {password_input}")
            
            return bool(username_input and password_input)
        except Exception as e:
            self.logger.error(f"等待登录表单时出错: {str(e)}")
            return False

    def _perform_login(self, username: str, password: str) -> bool:
        """执行登录操作"""
        try:
            # 填写登录表单
            self.browser.ele('@name=username').input(username)
            self.logger.info(f"输入用户名: {username}")
            self.browser.ele('@name=password').input(password)
            self.logger.info(f"输入密码: {password}")
            
            # 点击登录按钮
            submit_button = self.browser.ele('@type=submit')
            self.logger.info(f"找到登录按钮: {submit_button}")
            if not submit_button:
                self.logger.error("未找到登录按钮")
                return False
                
            submit_button.click()
            return True
            
        except Exception as e:
            self.logger.error(f"执行登录操作时出错: {str(e)}")
            return False

    def _verify_login(self) -> bool:
        """验证登录是否成功"""
        try:
            # 等待页面加载
            time.sleep(2)
            
            # 检查是否存在登录失败的提示
            error_messages = [
                "密码错误",
                "用户名错误",
                "登录失败",
                "Invalid username or password"
            ]
            
            page_source = self.browser.html
            for msg in error_messages:
                if msg in page_source:
                    self.logger.error(f"登录失败: {msg}")
                    return False
            
            # 检查是否存在登录成功的标志（比如用户信息元素）
            success_indicators = [
                'a[href*="logout"]',
                '#user-info',
                '.user-profile'
            ]
            
            for indicator in success_indicators:
                if self.browser.wait.ele_displayed(indicator):
                    self.logger.info("登录成功验证通过")
                    return True
            
            self.logger.error("未找到登录成功的标志")
            return False
            
        except Exception as e:
            self.logger.error(f"验证登录状态时出错: {str(e)}")
            return False

    def _get_all_cookies(self) -> list:
        """获取所有cookies"""
        try:
            all_cookies = self.browser.cookies()
            cookies_list = []
            
            for cookie in all_cookies:
                cookie_data = {
                    'name': cookie.get('name'),
                    'value': cookie.get('value'),
                    'domain': cookie.get('domain', '.ourbits.club'),
                    'path': cookie.get('path', '/'),
                    'secure': cookie.get('secure', True),
                    'httpOnly': cookie.get('httpOnly', True),
                    'sameSite': cookie.get('sameSite', 'Lax')
                }
                cookies_list.append(cookie_data)
                
            self.logger.info(f"成功获取 {len(cookies_list)} 个cookies")
            return cookies_list
            
        except Exception as e:
            self.logger.error(f"获取cookies时出错: {str(e)}")
            return []

def main():
    parser = argparse.ArgumentParser(description='PT站点登录处理器')
    parser.add_argument('url', help='登录页面URL')
    parser.add_argument('username', help='用户名')
    parser.add_argument('password', help='密码')
    
    args = parser.parse_args()
    
    try:
        handler = LoginHandler()
        result = handler.handle_login(args.url, args.username, args.password)
        
        # 输出JSON结果
        print(json.dumps(result.to_dict(), ensure_ascii=False))
        sys.stdout.flush()
        
    except Exception as e:
        error_result = LoginResult(False, error=str(e))
        print(json.dumps(error_result.to_dict(), ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
