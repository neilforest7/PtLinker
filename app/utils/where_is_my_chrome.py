import pyppeteer

# 获取Chromium执行文件的路径
chromium_executable_path = pyppeteer.launcher.executablePath()

print("Chromium executable path:", chromium_executable_path)

import asyncio
from pyppeteer import launch

async def main():
    # 启动浏览器
    browser = await launch(headless=True)  # headless=False 会显示浏览器界面
    page = await browser.newPage()
    await page.goto('https://example.com')
    content = await page.content()
    print(content)
    await browser.close()

asyncio.get_event_loop().run_until_complete(main())
