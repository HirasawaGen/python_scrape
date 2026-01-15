import asyncio
import json
from asyncio import Queue
from pathlib import Path
import urllib
import random

import aiofiles
from playwright.async_api import async_playwright
from playwright.async_api import Page, Browser
from bs4 import BeautifulSoup


MAX_PAGE_INDEX = 120
MAX_PAGE_NUM = 5
HEADLESS = False
ROOT = Path(__file__).parent


TAG_TABLE: dict[str, tuple[str, str] | str] = {
    'news.smm.cn': [
        ('div', 'detail_news_newsDetailArticleContent__15hk3')
    ],
    'hq.smm.cn': [
        ('div', 'news_body'),
        ('div', 'content_news-components')
    ],
    'new-energy.smm.cn': [
        ('div', '_breed_id__newsDetail__KJ2Y7')
    ],
    'steel.smm.cn': '要会员'
}


async def fetch_page_links(page_idx: int, page_queue: Queue[Page]) -> list[dict]:
    page_file = ROOT / 'pages' / f'page_{page_idx}.json'
    if page_file.exists():
        return []
    url = f'https://news.smm.cn/search?keywords=%E6%9C%89%E8%89%B2%E9%87%91%E5%B1%9E&page={page_idx}&field=3&time=&type=focus&keynote='
    page = await page_queue.get()
    await page.goto(url, wait_until='domcontentloaded')
    html_content = await page.content()
    await page_queue.put(page)
    soup = BeautifulSoup(html_content, 'lxml')
    div_tags = soup.find_all('div', class_='search_right__3AOzr')
    ans: list[dict] = []
    for div_tag in div_tags:
        a_tag = div_tag.find('a')
        info = div_tag.find('p', class_='search_contentInfo__wkYEy')
        label_tags = info.find_all('label')
        url = a_tag['href']
        title = a_tag.text.strip()
        publish_time = label_tags[-1].text.strip()
        ans.append({
            'url': url,
            'title': title,
            'publish_time': publish_time
        })
    async with aiofiles.open(page_file, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(ans, ensure_ascii=False, indent=4))
    print(f'Page {page_idx} fetched.')
    return ans


async def fetch_articles(page_idx: int, page_queue: Queue[Page]) -> list[dict]:
    page_file = ROOT / 'pages' / f'page_{page_idx}.json'
    result_file = ROOT / 'results' / f'result_{page_idx}.json'
    if not page_file.exists():
        return []
    if result_file.exists():
        return []
    json_data: list[dict]
    async with aiofiles.open(page_file, 'r', encoding='utf-8') as f:
        json_data = json.loads(await f.read())
    for i in range(len(json_data)):
        url = json_data[i]['url']
        domain: str = urllib.parse.urlparse(url).netloc
        if domain not in TAG_TABLE:
            print(f'Domain {domain} not supported.')
        table_val = TAG_TABLE[domain]
        if isinstance(table_val, str):
            # 寻找棍母了属于是
            print(f'Domain {domain} not supported.')
            continue
        page = await page_queue.get()
        await page.goto(url, wait_until='domcontentloaded')
        if domain == 'new-energy.smm.cn':
            await page.pause()  # 要登陆
        sleep_time = random.uniform(2, 5)
        await asyncio.sleep(sleep_time)
        html_content = await page.content()
        await page_queue.put(page)
        soup = BeautifulSoup(html_content, 'lxml')
        if '抱歉，您查看的页面不存在～～' in html_content:
            continue
        for tag, class_ in table_val:
            content = soup.find(tag, class_=class_)
            if content is not None:
                break
        if content is None:
            raise ValueError(f'No content found for {url}.')
        json_data[i]['content'] = content.text.strip()
        print(f'fetched {i+1}-th article of page {page_idx}')
    async with aiofiles.open(result_file, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(json_data, ensure_ascii=False, indent=4))
    print(f'Page {page_idx} fetched.')


async def main():
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=HEADLESS)
        page_queue = Queue()
        for _ in range(MAX_PAGE_NUM):
            page = await browser.new_page()
            await page_queue.put(page)
        tasks = [
            # fetch_page_links(i, page_queue)
            fetch_articles(i, page_queue)
            for i in range(1, MAX_PAGE_INDEX+1)
        ]
        await asyncio.gather(*tasks)
    

if __name__ == '__main__':
    asyncio.run(main())


