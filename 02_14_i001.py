import asyncio
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from loguru import logger as LOGGER

from page_pool import PagePool
from database import ZenianData, ZenianTable


SOURCE = '中国金属资讯网'
CATG = '新闻公告'
SECTION = '有色资讯'


async def search(
    page_pool: PagePool,
    table: ZenianTable,
    page_idx: int,
) -> list[ZenianData]:
    search_url = f'http://www.i001.com/yousenews-11-有色金属.shtml'
    async with page_pool() as page:
        if 'www.i001.com' not in page.url:
            await page.goto(search_url, wait_until='domcontentloaded')
        await page.evaluate(f'''() => {{
            __doPostBack('AspNetPager1','{page_idx}')
        }}''')
        await asyncio.sleep(2)
        await page.wait_for_load_state('domcontentloaded')
        html_content = await page.content()
    soup = BeautifulSoup(html_content, 'lxml')
    a_tags = soup.select('div.xjs > ul > li > a')
    LOGGER.info(f'第 {page_idx} 页共 {len(a_tags)} 条文章')
    ans: list[ZenianData] = []
    for a_tag in a_tags:
        title = a_tag.text.strip()
        if '国家统计局' in title:
            LOGGER.warning(f'文章"{title}"标题包含"国家统计局"，跳过')
            continue
        if '有色金属' not in title:
            LOGGER.warning(f'文章"{title}"标题不包含"有色金属"，跳过')
            continue
        url = str(a_tag['href'])
        if not url.startswith('http'):
            url = f'http://www.i001.com{url}'
        ans.append({
            'title': title,
            'url': url,
            'source': SOURCE,
            'catg': CATG,
            'section': SECTION,
        })
    LOGGER.info(f'第 {page_idx} 页共 {len(ans)} 条有效文章')
    saved_count = await table.save(ans)
    LOGGER.info(f'第 {page_idx} 页共保存 {saved_count} 条有效文章')
    return ans


def write_content(content: str):
    with open('content.html', 'w', encoding='utf-8') as f:
        f.write(content)


LIMITER = AsyncLimiter(1, 1)


async def fetch_content(
    session: ClientSession,
    table: ZenianTable,
    data: ZenianData,
) -> ZenianData:
    url = data['url']
    if not 'title' in data:
        return data
    title = data['title']
    async with (
        # LIMITER,
        session.get(url) as resp,
    ):
        LOGGER.info(f'获取文章"{title}"')
        if resp.status != 200:
            LOGGER.warning(f'获取文章"{url}"失败，状态码 {resp.status}')
            return data
        html_content = await resp.text()
        LOGGER.info(f'获取文章"{title}"成功')
    soup = BeautifulSoup(html_content, 'lxml')
    zhengwen = soup.select_one('div.zhengwen')
    if zhengwen is None:
        LOGGER.warning(f'获取文章"{url}"失败，没有找到正文')
        return data
    zw_fb = zhengwen.select_one('p.zw_fb')
    if zw_fb is None:
        LOGGER.warning(f'获取文章"{url}"失败，没有找到正文内容')
        return data
    zw_fb_text: str = zw_fb.text.strip()
    content: str = zhengwen.text.strip()
    content = content.replace(zw_fb_text, '', 1)
    content = content.replace(title, '', 1)
    mianze1 = '免责声明：此文仅供参考，未经核实，概不对交易结果负责，并请自行承担责任！'
    mainze2 = '返回>>'
    content = content.replace(mianze1, '')
    content = content.replace(mainze2, '')
    spans = zw_fb.select('span')
    if len(spans) < 2:
        LOGGER.warning(f'获取文章"{url}"失败，没有找到发布时间')
        return data
    publish_time_span = spans[1].next_sibling
    if publish_time_span is None:
        LOGGER.warning(f'获取文章"{url}"失败，没有找到发布时间')
        return data
    process_time = lambda x: datetime.strptime(x, '%Y/%m/%d').strftime('%Y-%m-%d')
    publish_time = process_time(publish_time_span.text.strip())
    data['content'] = content
    data['publish_time'] = publish_time
    LOGGER.info(f'获取文章"{title}"成功：\n{content[:50]}')
    await table.fill_content_and_time(url, content, publish_time)
    return data

    
async def task1():
    async with (
        async_playwright() as p,
        ZenianTable() as table,
    ):
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        await context.route('**/*', lambda route, request:
            route.abort() if request.resource_type == "image" else route.continue_()
        )
        page_pool = PagePool(context, 3, 1)
        await asyncio.gather(*[
            search(page_pool, table, i)
            for i in range(1, 26 + 1)
        ])


async def task2():
    async with (
        ClientSession() as session,
        ZenianTable() as table,
    ):
        data = await table.load(SOURCE, CATG, SECTION)
        data = [
            datum
            for datum in data
            if datum.get('content', 'None') in ['None', '']
        ]
        tasks = [
            fetch_content(session, table, d)
            for d in data
        ]
        LOGGER.info(f'共 {len(tasks)} 篇文章需要获取内容')
        results = await asyncio.gather(*tasks)


async def task3():
    async with (
        ZenianTable() as table,
    ):
        await table.export(SOURCE, CATG, SECTION)
        

if __name__ == '__main__':
    asyncio.run(task3())

