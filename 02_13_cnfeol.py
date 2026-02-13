from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def get_cookies(url: str) -> dict:
    stealth = Stealth()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await stealth.apply_stealth_async(context)
        page = await context.new_page()
        await page.goto(url)
        await page.pause()
        cookies_ = await page.context.cookies()
        await browser.close()
    return {
        cookie['name']: cookie['value']
        for cookie in cookies_
        if 'name' in cookie and 'value' in cookie
    }


async def main():
    cookies = await get_cookies('https://www.cnfeol.com/')

