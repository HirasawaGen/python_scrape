import asyncio
from playwright.async_api import async_playwright


async def screenshot_page(url: str, filename: str):
    """访问单个页面并截图"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        await page.screenshot(path=filename)
        print(f"已截图: {filename}")
        await browser.close()


async def main():
    # 创建两个并发任务
    await asyncio.gather(
        screenshot_page('https://www.baidu.com', 'baidu.png'),
        screenshot_page('https://www.bing.com', 'bing.png')
    )
    print("所有截图完成！")


if __name__ == '__main__':
    asyncio.run(main())