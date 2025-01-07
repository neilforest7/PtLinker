import time
from urllib.parse import urljoin
from loguru import logger
from DrissionPage import Chromium, ChromiumOptions


def run_playground(command):
    try:
        options = ChromiumOptions()
            
        options.headless(False).auto_port()
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
        logger.debug(f"浏览器实例创建成功")
        # 打印结果
        # url = urljoin(tab.url, "/getusertorrentlistajax.php")
        # print(result)
        # print(url)
        # print(tab.mode)
        # # tab.change_mode("s")
        tab = browser.latest_tab
        url = "https://www.hddolby.com/details.php?id=156404"
        tab.get(url)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'X-CSRF-Token': 'your-csrf-token',
        }
        cookies = ""
        tab.set.cookies(cookies)
        tab.get(url)
        # tab.listen.start('getusertorrentlistajax')
        # result = tab.get(url)
        # print(result)
        # packet = tab.listen.wait(timeout=20,fit_count=False)
        # print(packet.response.body)
        # # for packet in tab.listen.steps(3,timeout=20):
        # #     print("running================")
        # #     print(packet)
        
    except Exception as e:
        print(f"执行出错: {str(e)}")

if __name__ == "__main__":
    # 示例命令
    command = "document.title"
    run_playground(command)