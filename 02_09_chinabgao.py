import asyncio
from asyncio import Queue
import random

from playwright.async_api import async_playwright
from playwright.async_api import Page, Route, Browser, Response, Request
from loguru import  logger as LOGGER
from bs4 import BeautifulSoup

from database import ZenianData, ZenianTable
from page_pool import PagePool


DOMAIN = 'https://s.chinabgao.com'
SOURCE = '中国报告大厅'
CATG = '产业分析'
SECTION = '产业分析'


async def fetch_page(params: str, browser: Browser, queue: Queue[BeautifulSoup | None]):
    '''
    :param params: GET的请求参数，例如：w=锌&r=6
    :param page: playwright的Page对象
    :param queue: 给消费者的队列
    '''
    url = f'{DOMAIN}/?{params}'
    LOGGER.info(f'开始抓取{url}')
    page = await browser.new_page()

    async def handle_route(route: Route, req: Request):
        """Playwright官方推荐的请求拦截方式（类型注解完整）"""
        # 拦截图片请求（最常用的resource_type方式）
        if req.resource_type == "image" and not 'captcha' in req.url:
            # LOGGER.warning(f'拦截图片请求：{req.url}')
            await route.abort()  # Route对象的abort()，Pylance完全识别
        else:
            # 放行其他请求
            await route.continue_()  # Route对象的continue_()

    await page.route("**/*", handle_route)
    await page.goto(url, wait_until='domcontentloaded')
    LOGGER.info('请手动拖动滑块验证')
    await page.pause()  # 暂停，手动拖滑块

    while True:
        await page.wait_for_load_state('load')  # 不知道是哪个阶段加载出来的，先随便试试
        await asyncio.sleep(random.uniform(1.5, 2.5))
        next_page_btn = page.locator('li.page-item:has-text("下一页"):not(.disabled)')
        has_btn = await next_page_btn.count() > 0
        search_list = await page.query_selector('.srchlist')
        if search_list is None:
            LOGGER.warning('没有找到搜索结果列表')
            break
        html_content = await search_list.inner_html()
        soup = BeautifulSoup(html_content, 'lxml')
        await queue.put(soup)
        if not has_btn:
            break
        await next_page_btn.click()
    await queue.put(None)
    await page.close()


async def save_raw_data(table: ZenianTable, queue: Queue[BeautifulSoup | None]):
    while True:
        item = await queue.get()
        queue.task_done()
        if item is None:
            break
        # await table.save(item)  # 暂时不保存
        data: list[ZenianData] = []
        listtitle_div_tags = item.select('div.listtitle')
        for listtile in listtitle_div_tags:
            a_tag = listtile.select_one('a')
            if a_tag is None:
                continue
            title = a_tag.text.strip()
            url = a_tag['href']
            if not isinstance(url, str):
                continue
            if url.startswith('//'):
                url = f'https:{url}'
            # 不存publish_time了先，因为必须得点开链接才能看到时分秒
            data.append({
                'url': url,
                'title': title,
                'source': SOURCE,
                'catg': CATG,
                'section': SECTION,
            })
            LOGGER.info(f'发现新文章：{title[:50]}')
        await table.save(data)
        await asyncio.sleep(1)
    LOGGER.info('全部数据保存完成')


async def fetch_content(
    url: str,
    page_pool: PagePool,
    table: ZenianTable,
):
    async with page_pool() as page:
        LOGGER.info(f'开始抓取文章{url}')
        await page.goto(url, wait_until='domcontentloaded')
        if 'not fonud' in await page.title():
            LOGGER.warning(f'文章{url}不存在')
            await table.fill_content_and_time(url, 'not found', '1970-01-01 00:00:00')
            return
        arccon, pubTime = await asyncio.gather(
            page.query_selector('.arccon'),
            page.query_selector('.pubTime'),
        )
        LOGGER.info(f'文章{url}页面加载完成')
        while arccon is None or pubTime is None:
            LOGGER.warning(f'遇到反爬。请手动人机验证')
            await page.pause()
            await page.reload()
            arccon, pubTime = await asyncio.gather(
                page.query_selector('.arccon'),
                page.query_selector('.pubTime'),
            )
        content, publish_time = await asyncio.gather(
            arccon.inner_text(),
            pubTime.inner_text(),
        )
    await table.fill_content_and_time(url, content, publish_time)
    LOGGER.info(f'文章{url}内容数据库内容已更新')




async def task1():
    async with (
        async_playwright() as p,
        ZenianTable() as table,
    ):
        browser = await p.chromium.launch(headless=False)
        queue: Queue[BeautifulSoup | None] = Queue(maxsize=10)
        tasks = [
            fetch_page('w=锌&r=6', browser, queue),
            save_raw_data(table, queue),
        ]
        await asyncio.gather(*tasks)


async def task2():
    async with (
        async_playwright() as p,
        ZenianTable() as table,
    ):
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page_pool = PagePool(context=context, max_pages=3, max_rate=20)
        data = await table.load(SOURCE)
        data = [
            datum
            for datum in data
            if datum.get('content', 'None') == 'None'
        ]
        tasks = [
            fetch_content(datum['url'], page_pool, table)
            for datum in data
        ]
        random.shuffle(tasks)
        LOGGER.info(f'开始抓取{len(tasks)}篇文章')
        await asyncio.gather(*tasks)



async def task3():
    async with ZenianTable() as table:
        for catg in ('产业分析', '行业资讯', '财经分析'):
            await table.export(SOURCE, catg=catg, min_length=50)


if __name__ == '__main__':
    asyncio.run(task3())
