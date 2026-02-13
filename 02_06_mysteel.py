import asyncio
import random

import aiohttp
from aiohttp import ClientSession
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from database import ZenianData, ZenianTable
from aiolimiter import AsyncLimiter


# 记得开VPN，不然会被411
# 这就很奇怪，411不是拒绝接受未定义Content-Length的状态吗？

END_PAGE_IDX = 1
START_PAGE_IDX = 1
MAX_RATE = 120

SOURCE = '我的钢铁网'
# CATG = '行业研究'
# SECTION = '行业资讯'
CATG = '知识百科'
SECTION = '知识园区'

LIMITER = AsyncLimiter(MAX_RATE)


async def get_cookie(url: str) -> dict[str, str]:
    '''
    通过有头playwright获取cookie
    '''
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url, wait_until='load', timeout=60000)
        cookies = await page.context.cookies()
    return {
        c['name']: c['value']
        for c in cookies
        if 'name' in c and 'value' in c
    }


async def fetch_page_(table: ZenianTable) -> list[ZenianData]:
    '''
    反正只有一页，我就把html保存到本地了
    '''
    with open('content.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, 'lxml')
    li_tags = soup.select('.article-list li:not([class])')
    ans: list[ZenianData] = []
    for li_tag in li_tags:
        a_tag = li_tag.select_one('a')
        span_tag = li_tag.select_one('span.date')
        if a_tag is None or span_tag is None:
            print(f'Invalid data')
            continue
        url = str(a_tag.get('href', ''))
        if not len(url):
            print(f'Invalid href')
            continue
        title = a_tag.text.strip()
        publish_time = span_tag.text.strip() + ':00'
        ans.append({
            'url': url,
            'title': title,
            'publish_time': publish_time,
            'source': SOURCE,
            'catg': CATG,
            'section': SECTION,
        })
    await table.save(ans)
    print(f'Saved {len(ans)} items')
    return ans


async def fetch_page(table: ZenianTable, session: ClientSession, idx: int) -> list[ZenianData]:
    # url_ = f'https://list1.mysteel.com/article/p-1934----0204---------{idx}.html?keyWord='
    url_ = f'https://list1.mysteel.com/article/p-2355----0204---------{idx}.html?keyWord='
    li_tags = []
    async with LIMITER:
        for i in range(3):
            async with session.get(url_) as response:
                print(f'Fetching page {idx}')
                html_content = await response.text()
            soup = BeautifulSoup(html_content, 'lxml')
            li_tags = soup.select('.article-list li:not([class])')
            if len(li_tags):
                break
            else:
                sleep_time = random.uniform(0.5, 3.5) * (i + 1) ** 2
                print(f'No data for page {idx}, sleeping for {sleep_time:.3f} seconds')
                await asyncio.sleep(sleep_time)
    if not len(li_tags):
        print(f'No more pages for page {idx}')
        return []
    ans: list[ZenianData] = []
    for li_tag in li_tags:
        a_tag = li_tag.select_one('a')
        span_tag = li_tag.select_one('span.date')
        if a_tag is None or span_tag is None:
            print(f'Invalid data')
            continue
        url = str(a_tag.get('href', ''))
        if not len(url):
            print(f'Invalid href')
            continue
        title = a_tag.text.strip()
        publish_time = span_tag.text.strip() + ':00'
        ans.append({
            'url': url,
            'title': title,
            'publish_time': publish_time,
            'source': SOURCE,
            'catg': CATG,
            'section': SECTION,
        })
    await table.save(ans)
    print(f'Saved {len(ans)} items for page {idx}')
    return ans


async def fetch_content(table: ZenianTable, session: ClientSession, url: str) -> str:
    async with LIMITER:
        async with session.get(url) as response:
            print(f'Fetching content for {url}')
            html_content = await response.text()
    soup = BeautifulSoup(html_content, 'lxml')

    ariticle_content = soup.select_one('#article-content')
    if ariticle_content is None:
        print(f'Invalid content for {url}')
        return ''
    vip = soup.select_one('#login-detail') is not None
    if vip:
        print(f'VIP content for {url}')
        await table.fill_content(url, 'VIP Only')
        return 'VIP Only'
    content = ariticle_content.get_text(strip=True)
    editor = soup.select_one('.editor')
    if editor is not None:
        content = content.replace(editor.get_text(strip=True), '')
    print(f'content: {content[:50]}')
    await table.fill_content(url, content)
    return content


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
    'Referer': 'https://list1.mysteel.com/',
}


async def main():
    cookies = {}
    async with ZenianTable() as table:
        data = await table.load(SOURCE, CATG, SECTION)
        data = [d for d in data if d.get('content', 'None') == 'None']
        if len(data):
            print(f'Loaded {len(data)} items')
        else:
            await table.export(SOURCE, CATG, SECTION, min_length=50)
            return
    cookies = await get_cookie(data[0]['url'])
    print(f'Got {len(cookies)} cookies')
    async with (
        aiohttp.ClientSession(
            headers=HEADERS,
            cookies=cookies,
        ) as session,
        ZenianTable() as table,
    ):
        await asyncio.gather(*[
            LIMITER.acquire()
            for _ in range(MAX_RATE)
        ])
        # await asyncio.gather(*[
        #     fetch_page_(
        #         table
        #     )
        #     for i in range(START_PAGE_IDX, END_PAGE_IDX + 1)
        # ])
        await asyncio.gather(*[
            fetch_content(table, session, datum['url'])
            for datum in data
        ])


if __name__ == '__main__':
    asyncio.run(main())