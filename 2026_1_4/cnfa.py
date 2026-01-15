import asyncio
from asyncio import Queue
from pathlib import Path
import json
from collections import OrderedDict

from playwright.async_api import async_playwright
from playwright.async_api import Page, Browser
from aiofiles import open


MAX_PAGE = 5
BEGIN_PAGE = 1
END_PAGE = 2
PAGE_QUEUE: Queue[Page] = Queue(maxsize=MAX_PAGE)
HEADLESS = False
ROOT = Path(__file__).parent
CATG = '行业研究'


async def fetch_links(page_idx: int, page_queue: Queue[Page]) -> list[dict]:
    page_file = ROOT / 'pages' / f'page_{page_idx}.json'
    if page_file.exists():
        return []
    base_url = f'https://www.cnfa.net.cn/data/143/{page_idx}.aspx'
    page: Page = await page_queue.get()
    await page.goto(base_url, wait_until='domcontentloaded')
    schq_left = page.locator('div.schq_left')
    dynamic_list = await schq_left.locator('div.dynamic_list').all()
    ans: list[dict] = []
    for item in dynamic_list:
        dynamic_r = item.locator('div.dynamic_r')
        a_tag = dynamic_r.locator('a')
        news_xx = dynamic_r.locator('div.news_xx')
        dynamic_title = dynamic_r.locator('div.dynamic_title')
        news_time = news_xx.locator('div.news_time')
        url, title, publish_time = await asyncio.gather(
            a_tag.get_attribute('href'),
            dynamic_title.text_content(),
            news_time.text_content()
        )
        publish_time += ' 00:00:00'
        publish_time = publish_time.strip()
        ans.append({
            'url': url,
            'title': title,
            'publish_time': publish_time
        })
    await page_queue.put(page)
    async with open(page_file, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(ans, ensure_ascii=False, indent=4))
    print(f'Fetching links for page {page_idx}')
    return ans

async def fetch_links_(page_idx: int, page_queue: Queue[Page]) -> list[dict]:
    page_file = ROOT / 'pages' / f'page_{page_idx}.json'
    if page_file.exists():
        return []
    base_url = f'https://www.cnfa.net.cn/data/143/{page_idx}.aspx'
    page: Page = await page_queue.get()
    await page.goto(base_url, wait_until='domcontentloaded')
    schq_left = page.locator('div.schq_left')
    dynamic_list = await schq_left.locator('div.news_list').all()
    ans: list[dict] = []
    for item in dynamic_list:
        dynamic_r = item
        a_tag = dynamic_r.locator('a')
        news_xx = dynamic_r.locator('div.news_xx')
        # dynamic_title = dynamic_r.locator('div.dynamic_title')
        news_time = news_xx.locator('div.news_time')
        url, title, publish_time = await asyncio.gather(
            a_tag.get_attribute('href'),
            a_tag.text_content(),
            news_time.text_content()
        )
        publish_time += ' 00:00:00'
        publish_time = publish_time.strip()
        ans.append({
            'url': url,
            'title': title,
            'publish_time': publish_time
        })
    await page_queue.put(page)
    async with open(page_file, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(ans, ensure_ascii=False, indent=4))
    print(f'Fetching links for page {page_idx}')
    return ans

async def fetch_article(page_idx: int, page_queue: Queue[Page]) -> list[dict]:
    '''
    :param url: URL of the article to fetch
    '''
    # Use queue rather than creating new page for better performance
    page_file = ROOT / 'pages' / f'page_{page_idx}.json'
    result_file = ROOT / 'results' / f'page_{page_idx}.json'
    if result_file.exists():
        return []
    async with open(page_file, 'r', encoding='utf-8') as f:
        items: list[dict] = json.loads(await f.read())
    ans: list[dict] = []
    page: Page = await page_queue.get()
    for item in items:
        url = 'https://www.cnfa.net.cn' + item['url']
        await page.goto(
            url,
            wait_until='domcontentloaded',
            timeout=10000000
        )
        xhxx_font = page.locator('div.xhxx_font')
        content = await xhxx_font.text_content()
        content = content.strip()
        result = OrderedDict()
        result['title'] = item['title']
        result['publish_time'] = item['publish_time']
        result['source'] = '中国有色金属加工工业协会'
        result['url'] = url
        result['content'] = content
        result['catg'] = CATG
        print(f'Fetching article {url} at page {page_idx}')
        ans.append(result)
    await page_queue.put(page)
    async with open(result_file, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(ans, ensure_ascii=False, indent=4))
    print(f'save all articles of page {page_idx} to file')
    return ans


async def main():
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=HEADLESS)
        all_pages_num = END_PAGE - BEGIN_PAGE + 1
        for _ in range(min(all_pages_num, MAX_PAGE)):
            page: Page = await browser.new_page()
            await PAGE_QUEUE.put(page)
        tasks = []
        for i in range(BEGIN_PAGE, END_PAGE+1):
            # tasks.append(fetch_links(i, PAGE_QUEUE))
            tasks.append(fetch_article(i, PAGE_QUEUE))
        await asyncio.gather(*tasks)
        await browser.close()
        
        
if __name__ == '__main__':
    asyncio.run(main())
        
        

        
