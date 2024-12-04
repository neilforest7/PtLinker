import time
from urllib.parse import urljoin

from DrissionPage import Chromium


def run_playground(command):
    try:
        # 连接到已打开的 Chrome
        browser = Chromium(9333)
        # 获取最新标签页
        tab = browser.latest_tab
        print(tab.url)
        start_time = time.time()
        # 执行 JS 命令并获取结果
        result = tab.ele("@class$User_Name")
        result = result.text
        print(result)
        end_time = time.time()
        print(f"执行时间: {end_time - start_time}秒")
        # 打印结果
        # url = urljoin(tab.url, "/getusertorrentlistajax.php")
        # print(result)
        # print(url)
        # print(tab.mode)
        # # tab.change_mode("s")
        
        # url = "https://carpt.net/getusertorrentlistajax.php?userid=35038&type=seeding"
        # data = {
        #     'id': '35038',
        #     'type': 'seeding',
        # }
        # headers = {
        #     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        #     'X-CSRF-Token': 'your-csrf-token',
        # }
        # cookies = tab.cookies()

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