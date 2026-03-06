'''
通过有头playwright获取某个url对应的cookie

可以用来给aiohttp.ClientSession用
'''


from playwright.async_api import async_playwright


async def get_cookie(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url)
        cookies = await page.context.cookies()
        await browser.close()
    return {
        c['name']: c['value']
        for c in cookies
        if 'name' in c and 'value' in c
    }
