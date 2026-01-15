import asyncio
import json
from asyncio import Queue
from pathlib import Path
import urllib
import random
from itertools import batched

import aiofiles
from playwright.async_api import async_playwright
from playwright.async_api import Page, Browser
from bs4 import BeautifulSoup


MAX_PAGE_INDEX = 66
MAX_PAGE_NUM = 5
HEADLESS = False
ROOT = Path(__file__).parent


TAG_TABLE: dict[str, tuple[str, str] | str] = {
    'news.smm.cn': [
        ('div', 'detail_news_newsDetailArticleContent__15hk3'),
        ('div', 'detail_newsLiveDetailContentText__pTM-G')
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


async def fetch_page_links(browser: Browser) -> list[dict]:
    url = 'https://www.smm.cn/search?keyword=%E9%92%A8&type=news&field=7&newsType=94'
    page: Page = await browser.new_page()
    await page.goto(url, wait_until='domcontentloaded')
    # await page.pause() # maybe need login
    while True:
        # break # for debug
        more = page.locator('div.load-more-news')
        count = await more.count()
        if count == 0:
            break
        inner_text = await more.inner_text()
        if inner_text == '查看更多':
            try:
                await more.click()
            except:
                break
            await page.wait_for_load_state('domcontentloaded')
            sleep_time = random.uniform(0.5, 1.5)
            await asyncio.sleep(sleep_time)
        else:
            break
    html_content = await page.content()
    soup = BeautifulSoup(html_content, 'lxml')
    all_item_div_tags = soup.find_all('div', class_='search-news-live-item')
    for i, item_div_tags in enumerate(batched(all_item_div_tags, 20)):
        page_file = ROOT / 'pages' / f'page_{i+1}.json'
        json_data = []
        for item_div in item_div_tags:
            a_tag = item_div.find('a')
            if a_tag is None:
                continue
            url = a_tag['href']
            title = a_tag.text.strip()
            # NOTE: reminber to remove it.
            if '钨' not in title: continue
            # info = item_div.find('p', class_='search-news-contentInfo')
            # publish_time: str = info.find_all('label')[-1].text
            # publish_time = publish_time.strip()
            # publish_time += ' 00:00:00'
            span_live_date = item_div.find('span', class_='live-date')
            publish_time = span_live_date.text.strip()
            json_data.append({
                'url': url,
                'title': title,
                'publish_time': publish_time
            })
            # print(f'fetched {len(json_data)} articles of page {i+1}')
        with page_file.open('w', encoding='utf-8') as f:
            f.write(json.dumps(json_data, ensure_ascii=False, indent=4))
    await page.close()

    
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
        if '页面加载失败..' in html_content:
            continue
        for tag, class_ in table_val:
            content = soup.find(tag, class_=class_)
            if content is not None:
                break
        if content is None:
            print(f'No content found for {url}.')
            json_data[i]['content'] = ''
        else:
            json_data[i]['content'] = content.text.strip()
        print(f'fetched {i+1}-th article of page {page_idx}')
    async with aiofiles.open(result_file, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(json_data, ensure_ascii=False, indent=4))
    print(f'Page {page_idx} fetched.')
        
async def main():
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=HEADLESS)
        # await fetch_page_links(browser)
        page_queue = Queue()
        for _ in range(MAX_PAGE_NUM):
            page = await browser.new_page()
            await page_queue.put(page)
        tasks = [
            fetch_articles(i, page_queue)
            for i in range(1, MAX_PAGE_INDEX+1)
        ]
        await asyncio.gather(*tasks)
    

if __name__ == '__main__':
    asyncio.run(main())


