import json
import re
import time
from urllib.parse import urljoin

from DrissionPage import Chromium, ChromiumOptions
from loguru import logger


def parse_cookies(cookies_str: str, domain: str) -> list:
    """解析cookies字符串为列表格式"""
    try:
        cookies_data = []
        for line in cookies_str.split(';'):
            if '=' in line:
                name, value = line.strip().split('=', 1)
            cookies_data.append({'name': name.strip(), 'value': value.strip()})
        
        # 确保每个cookie都有domain字段
        for cookie in cookies_data:
            if 'domain' not in cookie:
                cookie['domain'] = domain
        
        return cookies_data
    except Exception as e:
        logger.error(f"解析cookies失败: {str(e)}")
        return []
    
def run_playground(command):
    try:
        options = ChromiumOptions()
            
        options.headless(True).auto_port()
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

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            # 'X-CSRF-Token': 'your-csrf-token',
            # 'Host': 'hhanclub.top',
            'cookie': 'domain=hdfans.org;c_secure_ssl=eWVhaA%3D%3D; c_secure_uid=NTc1Mjk%3D; c_secure_pass=e444fb5e48aa5db1485a4f78dbe231a7; c_secure_tracker_ssl=eWVhaA%3D%3D; c_secure_login=bm9wZQ%3D%3D'
        }
        # tab.get(url)
        # tab.listen.start('getusertorrentlistajax')
        # result = tab.get(url)
        # print(result)
        # packet = tab.listen.wait(timeout=20,fit_count=False)
        # print(packet.response.body)
        # # for packet in tab.listen.steps(3,timeout=20):
        # #     print("running================")
        # #     print(packet)
        tab = browser.latest_tab
        manual_cookies="domain=hdfans.org;c_secure_ssl=eWVhaA%3D%3D; c_secure_uid=NTc1Mjk%3D; c_secure_pass=e444fb5e48aa5db1485a4f78dbe231a7; c_secure_tracker_ssl=eWVhaA%3D%3D; c_secure_login=bm9wZQ%3D%3D",
        # domain = "hhanclub.top"
        # cookies_list = parse_cookies(manual_cookies, domain)
        # tab.set.cookies(cookies_list)
        tab.set.cookies(manual_cookies)
        # tab.set.headers(headers)
        # tab.set.headers(headers)
        url = "https://hdfans.org/getusertorrentlistajax.php"
        tab.change_mode("s")
        params = {
            "userid": "57529",
            "type": "seeding",
            "page": 0,
            "ajax": 1
        }
        tab.get(url, params=params) 
        print(tab.html)
        print(tab.url)
        for row in tab.ele("tag:table@@text():实际上传@@border=1").eles("tag:tr")[1:]:
            # print(row.html)
            size_str = row.ele("tag:td",index=3).text
            print(re.search(r"(([\d.])+[\s\n]*([KMGTPE]?i?B))", size_str).group(0))
        # print(tab.cookies)
        # print(tab.mode)
        # print(tab.url)
        # print(tab.html)
        # print(tab.ele("tag:td").text)
        # outer = tab.ele("#outer")
        # print(outer.html)
        # tb = tab.ele('tag:table@@text():下载量')
        # size = tb.text # 先获取表格，再获取非表头的行，再获取表格的第四列
        # print(size)
        # print(re.search(r"(做种积分|做種積分|Seeding Points).*?:\s*([\d,.]+)", size).group(0))
        # user_class = outer.ele('等级').parent().ele("@tag()=img").attr("title")
        # print(user_class)
        # size_fi = tab.ele("tag:td@@text():下载量").text
        # print(size_fi)
        # print(re.search(r"([\d.]+)\s*([KMGTPE]?i?B)", size).group(0))
        # rows = tab.eles("tag:tr")
        # print(rows.html)
        # for row in rows:
        #     size = row.ele("tag:td",index=4).text
    
            # print(size)
        

    except Exception as e:
        print(f"执行出错: {str(e)}")

if __name__ == "__main__":
    # 示例命令
    command = "document.title"
    run_playground(command)
