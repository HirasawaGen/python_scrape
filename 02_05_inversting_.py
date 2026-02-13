import asyncio
from pathlib import Path
from typing import AsyncGenerator
import json
from datetime import datetime
from asyncio import Queue
from random import shuffle
from contextlib import asynccontextmanager
import winsound

import aiofiles
from playwright.async_api import async_playwright
from playwright.async_api import Page, BrowserContext
from aiolimiter import AsyncLimiter

from database import ZenianData, ZenianTable
from page_pool import PagePool


def normalize_date(date_str):
    """将不规则日期格式统一为 YYYY-MM-DD"""
    if '以前' in date_str:
        return '2026-02-05'
    try:
        # 解析各种分隔符和格式
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        # 处理 2020-4-2 这种缺零的格式
        parts = date_str.replace('/', '-').replace('.', '-').split('-')
        if len(parts) == 3:
            year, month, day = parts
            return f"{year}-{int(month):02d}-{int(day):02d}"
            
    except Exception:
        pass
    
    return date_str  # 解析失败返回原值


async def get_data(json_file: Path) -> list[ZenianData]:
    async with aiofiles.open(json_file, mode='r', encoding='utf-8') as f:
        data = json.loads(await f.read())
    return [
        {
            'title': datum['name'],
            'publish_time': normalize_date(datum['date'].replace('年', '-').replace('月', '-').replace('日', '')) + ' 00:00:00',
            'source': '英为财情',
            'url': f'https://cn.investing.com{datum['link']}',
            'catg': '行业研究',
            'section': '资讯',
        }
        for datum in data
    ]


async def main():
    tasks = []
    for json_file in Path().glob('news_*.json'):
        print(f'Processing {json_file}...')
        tasks.append(get_data(json_file))
    data = sum(await asyncio.gather(*tasks), [])
    print(f'Got {len(data)} data.')
    async with ZenianTable() as table:
        count = await table.save(data)
        print(f'Saved {count} data.')


@asynccontextmanager
async def queue_item[T](queue: Queue[T]) -> AsyncGenerator[T, None]:
    item = await queue.get()
    yield item
    await queue.put(item)


@asynccontextmanager
async def page_queue_manager(queue: Queue[Page]) -> AsyncGenerator[Page, None]:
    async with queue_item(queue) as page:
        yield page
        await page.evaluate('window.stop()')


LIMITER = AsyncLimiter(30)  # 每分钟最多访问 30 次


async def _fill_content(page_pool: PagePool, table: ZenianTable, url: str):
    async with (
        page_pool() as page,
        LIMITER,
    ):
        print(f'Fetching {url}...')
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        except Exception:
            winsound.Beep(2000, 1000)  # 声音警告
            print(f'Failed to fetch {url}. timeout')
            return
        title = await page.title()
        if 'Just a moment' in title:
            await asyncio.sleep(1)
            await page.reload()
            title = await page.title()
        if '404' in title:
            print(f'Got 404 for {url}.')
            content = '404 Not Found'
        else:
            print(f'loaded {title}')
            try:
                await page.wait_for_selector('#article')
                content = await page.locator('#article').inner_text()
            except Exception:
                winsound.Beep(2000, 1000)  # 声音警告
                print(f'Failed to fetch {title}. empty content')
                return
    print(f'Got content for {url}: {content[:100]}')
    winsound.Beep(440, 1000)  # 声音提醒
    await table.fill_content(url, content)


async def _page_processor(page: Page):
    await page.route("**/*", lambda route: 
        route.fulfill(body="")  # 空响应，比 abort 更快
        if route.request.resource_type != "document" 
        else route.continue_()
    )
    return page


async def fill_content():
    async with (
        async_playwright() as p,
        ZenianTable() as table,
    ):
        max_workers = 5
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page_pool = PagePool(context, max_workers, page_processor=_page_processor)
        data = await table.load(source='英为财情')
        data = [
            datum
            for datum in data
            if datum.get('content', '') in {'', 'None'}
        ]
        tasks = [
            _fill_content(page_pool, table, datum['url'])
            for datum in data
        ]
        shuffle(tasks)
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == '__main__':
    # 多运行几遍 反正有漏网之鱼
    asyncio.run(fill_content())

