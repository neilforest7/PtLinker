from urllib.parse import urljoin

from DrissionPage import Chromium


def run_playground(command):
    try:
        # 连接到已打开的 Chrome
        browser = Chromium(9333)
        # 获取最新标签页
        tab = browser.latest_tab
        print(tab.url)

        url = "https://carpt.net/getusertorrentlistajax.php?userid=35038&type=seeding"

        cookies = tab.cookies()

        tab.listen.start('getusertorrentlistajax')
        result = tab.get(url)
        print(result)
        packet = tab.listen.wait(timeout=20,fit_count=False)
        print(packet.response.body)
        # for packet in tab.listen.steps(3,timeout=20):
        #     print("running================")
        #     print(packet)
        
    except Exception as e:
        print(f"执行出错: {str(e)}")

if __name__ == "__main__":
    # 示例命令
    command = "document.title"
    run_playground(command)