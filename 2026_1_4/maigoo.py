import asyncio
from asyncio import Queue
from pathlib import Path
import json

from playwright.async_api import async_playwright
from playwright.async_api import Page, Browser
from aiofiles import open


MAX_PAGE = 5


PAGE_QUEUE: Queue[Page] = Queue(maxsize=MAX_PAGE)
HEADLESS = False
ROOT = Path(__file__).parent
CATG = '知识百科'
SOURCE = '买购网'


async def fetch_page(browser: Browser):
    page = await browser.new_page()
    await page.goto('https://www.maigoo.com/goomai/list_9533.html')
    while True:
        await asyncio.sleep(1)
        a_tag = page.locator('a.addmore')
        a_tag_text = await a_tag.inner_text()
        a_tag_text = a_tag_text.strip()
        if a_tag_text == '加载中..':
            continue
        if a_tag_text == '加载更多':
            await a_tag.click()
        else:
            break
    # await page.pause()
    print('loaded all.')
    item_box = page.locator('div.itembox')
    items = await item_box.locator('div.item').all()
    ans: list[dict] = []
    for item in items[:73]:
        contbox = item.locator('div.contbox')
        a_tag = contbox.locator('a.title')
        title, url = await asyncio.gather(
            a_tag.inner_text(),
            a_tag.get_attribute('href')
        )
        print(f'title: {title}')
        ans.append({
            'title': title,
            'url': url,
        })
    await page.close()
    page_file = ROOT / 'pages' / 'page.json'
    with page_file.open('w', encoding='utf-8') as f:
        json.dump(ans, f, ensure_ascii=False, indent=4)
    print(f'fetched all {len(ans)} items.')
    return ans
    

async def fetch_articles(item: dict, page_queue: Queue[Page]) -> dict:
    page = await page_queue.get()
    url = item['url']
    await page.goto(url, wait_until='domcontentloaded')
    html_content = await page.content()
    if '您正在访问外部的第三方网址' in html_content:
        await page_queue.put(page)
        print(f'external url: {url}')
        return item
    articlecont = page.locator('div.articlecont')
    content = await articlecont.inner_text()
    # print(f'content: {content}')
    await page_queue.put(page)
    item['content'] = content
    item['publish_time'] = '2026-1-4 00:00:00'
    item['catg'] = CATG
    item['source'] = SOURCE
    print(f'fetched article: {item["title"]}')
    return item


async def main():
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=HEADLESS)
        # ans = await fetch_page(browser)
        with (ROOT / 'pages' / 'page.json').open('r', encoding='utf-8') as f:
            ans = json.load(f)
        for _ in range(MAX_PAGE):
            page = await browser.new_page()
            await PAGE_QUEUE.put(page)
        # ans = ans[:2]  # for test
        tasks = [fetch_articles(item, PAGE_QUEUE) for item in ans]
        results = await asyncio.gather(*tasks)
        with (ROOT / 'results' / f'result.json').open('w', encoding='utf-8') as f:
            json.dump(ans, f, ensure_ascii=False, indent=4)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())

