# 铁合金在线的反爬做得太决绝了
# 因此不考虑aiohttp，还是用异步有头playwright比较好
# 拦截掉所有图片文件的加载
# https://t.captcha.qq.com/cap_union_new_getcapbysig除外
# 验证码识别直接pause下来自己手动拖动


import asyncio
from pathlib import Path

from playwright.async_api import async_playwright
from playwright.async_api import Page, BrowserContext
from playwright_stealth import Stealth
from bs4 import BeautifulSoup
from loguru import logger as LOGGER
import yaml

from page_pool import PagePool
from database import ZenianData, ZenianTable


KEYWORD_MAPPING = {
    '钼': 'mu',
}


async def search(
    page_pool: PagePool,
    table: ZenianTable,
    keyword: str,
    page_idx: int,
) -> list[ZenianData]:
    assert keyword in KEYWORD_MAPPING, f"不支持的关键字: {keyword}"
    assert page_idx > 0, "页码必须大于0"
    url = (
        'https://www.cnfeol.com'
        f'/{KEYWORD_MAPPING[keyword]}'
        f'/n-8-{page_idx}.aspx'
    )

    async with page_pool() as page:
        LOGGER.info(f"正在搜索: {keyword}, 第{page_idx}页")
        await page.goto(url, wait_until='load')
        title = await page.title()
        if '人机验证' in title:
            LOGGER.warning(f"人机验证，请手动完成验证")
            await page.pause()
            await page.wait_for_load_state('load')
        html_content = await page.content()
        LOGGER.debug(f"搜索完成：{keyword}，第{page_idx}页")

    soup = BeautifulSoup(html_content, 'lxml')
    data_list_box = soup.select_one('div.dataListBox')
    if data_list_box is None:
        LOGGER.warning(f"没有找到数据列表")
        return []
    a_tags = data_list_box.select('a')
    ans: list[ZenianData] = []
    for a_tag in a_tags:
        span = a_tag.select_one('span:first-child')
        if span is None:
            continue
        title = span.text.strip()
        url = a_tag['href']
        if not isinstance(url, str):
            continue
        ans.append({
            'title': title,
            'url': url,
            'source': '铁合金在线',
            'catg': '政策法规',
            'section': keyword,
        })
    await table.save(ans)
    return ans


async def main():
    COOKIES = Path() / 'cookies_cnfeol.yaml'
    stealth = Stealth()
    async with (
        async_playwright() as p,
        ZenianTable() as table,
    ):
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        await stealth.apply_stealth_async(context)
        if COOKIES.exists():
            cookies = yaml.safe_load(COOKIES.read_text())
            await context.add_cookies(cookies)
        page_pool = PagePool(context, 1, 3)
        tasks = [
            search(page_pool, table, '钼', i)
            for i in range(8, 22+1)
        ]
        cookies = await context.cookies()
        yaml.safe_dump(cookies, COOKIES.open('w'))
        await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())

