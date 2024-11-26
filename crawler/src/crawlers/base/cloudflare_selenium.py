import sys
import time
import json
import logging
from typing import Dict, Optional
from DrissionPage import ChromiumPage, ChromiumOptions

# 配置日志
def setup_logging():
    logger = logging.getLogger('cloudflare_handler')
    logger.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # 添加处理器到logger
    logger.addHandler(console_handler)
    
    return logger

class CloudflareHandler:
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
            
            # 初始化配置
            ChromiumOptions().set_browser_path(self.browser_path).save()
            
            # 恢复标准输出并忽略配置信息
            sys.stdout = original_stdout
            self.logger.info("浏览器配置初始化完成")
        except Exception as e:
            self.logger.error(f"浏览器配置初始化失败: {str(e)}")
            raise

    def handle_challenge(self, url: str) -> dict:
        try:
            # 创建新的页面实例
            self.browser = ChromiumPage()
            self.logger.info(f"开始访问URL: {url}")
            self.browser.get(url)

            # 等待并检查是否需要处理Cloudflare验证
            if not self._is_cloudflare_present():
                self.logger.info("未检测到Cloudflare验证，可能已经通过或不需要验证")
                return self._create_success_response()

            self.logger.info("等待 Cloudflare 验证框架...")
            
            # 等待验证完成
            start_time = time.time()
            while time.time() - start_time < 30:  # 30秒超时
                if not self._is_cloudflare_present():
                    self.logger.info("Cloudflare 验证已完成")
                    return self._create_success_response()
                time.sleep(1)

            raise Exception("验证超时")

        except Exception as e:
            return self._handle_error(str(e))
        finally:
            if self.browser:
                self.browser.quit()

    def _is_cloudflare_present(self) -> bool:
        """检查页面是否存在Cloudflare验证框架"""
        try:
            # 检查常见的Cloudflare元素
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
                    element = self.browser.ele_exists(indicator)
                    if element and element.is_displayed():
                        return True
                except:
                    continue
                    
            return False
        except:
            return False

    def _create_success_response(self) -> dict:
        """创建成功响应"""
        try:
            # 使用DrissionPage官方的cookies获取方式
            all_cookies = self.browser.cookies(all_domains=False, all_info=True)
            
            self.logger.info(f"获取到原始cookies: {len(all_cookies)} 个")
            
            # 转换cookies格式
            cookies = []
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
                cookies.append(cookie_data)
                self.logger.info(f"处理cookie: {cookie_data['name']} = {cookie_data['value'][:10]}...")
            
            self.logger.info(f"成功处理 {len(cookies)} 个cookies")
            return {
                "status": "success",
                "cookies": cookies
            }
        except Exception as e:
            self.logger.error(f"获取cookies时出错: {str(e)}")
            import traceback
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            return self._handle_error(f"获取cookies失败: {str(e)}")

    def _handle_error(self, error_message: str) -> dict:
        """处理错误并创建错误响应"""
        self.logger.error(f"Cloudflare 验证失败: {error_message}")
        
        # 保存错误截图和页面源码
        try:
            if self.browser:
                self.browser.get_screenshot('error_screenshot.png')
                self.logger.info("错误截图已保存为 error_screenshot.png")
                
                with open("error_page_source.html", "w", encoding="utf-8") as f:
                    f.write(self.browser.html)
                self.logger.info("页面源码已保存为 error_page_source.html")
        except Exception as e:
            self.logger.error(f"保存错误信息失败: {str(e)}")
            
        return {
            "status": "error",
            "error": error_message
        }

def main():
    # 从命令行参数获取URL，如果没有则使用默认值
    url = sys.argv[1] if len(sys.argv) > 1 else "https://ourbits.club/login.php"
    
    try:
        handler = CloudflareHandler()
        result = handler.handle_challenge(url)
        
        # 确保只输出JSON结果
        print(json.dumps(result, ensure_ascii=False))
        sys.stdout.flush()  # 确保输出被立即刷新
        
    except Exception as e:
        error_result = {
            "status": "error",
            "error": str(e)
        }
        print(json.dumps(error_result, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
