import asyncio
from asyncio import Queue
from pathlib import Path
import random
import json

from playwright.async_api import async_playwright
from playwright.async_api import Page, Browser
from bs4 import BeautifulSoup
import aiofiles


HEADLESS = False
MAX_PAGE_NUM = 1
ROOT = Path(__file__).parent / 'list1_mysteel'

is_login = False


async def fetch_page_links(page_queue: Queue[Page], page_idx: int) -> list[dict]:
    file_path = ROOT / 'pages' / f'page_{page_idx}.json'
    if file_path.exists():
        return []
    page_url = f'https://list1.mysteel.com/article/p-1949,4815----02---------8.html?page={page_idx}'
    page = await page_queue.get()
    sleep_time = random.randint(1, 3) * MAX_PAGE_NUM
    await asyncio.sleep(sleep_time)
    await page.goto(page_url)
    soup = BeautifulSoup(await page.content(), 'html.parser')
    await page_queue.put(page)
    article_list_tag = soup.find('div', class_='article-list')
    if article_list_tag is None:
        await page_queue.put(page)
        return []
    news_list_ul_tag = article_list_tag.find('ul', class_='news-list')
    li_tags = news_list_ul_tag.find_all('li')
    ans = []
    for li_tag in li_tags:
        if li_tag.get('class') == ['dashed']:
            continue
        span_date = li_tag.find('span', class_='date')
        publish_time = span_date.text.strip()
        a_tag = li_tag.find('a')
        url = a_tag['href']
        title = a_tag.text.strip()
        ans.append({'title': title, 'url': url, 'publish_time': publish_time})
    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(ans, ensure_ascii=False, indent=4))
    print(f'Page {page_idx} fetched and saved to {file_path}')
    return ans


async def fetch_articles(page_queue: Queue[Page], page_idx: int) -> list[dict]:
    page_path = ROOT / 'pages' / f'page_{page_idx}.json'
    result_path = ROOT / 'results' / f'result_{page_idx}.json'
    result_exists = await asyncio.to_thread(result_path.exists)
    if result_exists:
        return []
    json_data: list[dict]
    async with aiofiles.open(page_path, 'r', encoding='utf-8') as f:
        json_data = json.loads(await f.read())
    for i, json_datum in enumerate(json_data):
        url = json_datum['url']
        page = await page_queue.get()
        sleep_time = (random.random() + 1.0) * MAX_PAGE_NUM
        await asyncio.sleep(sleep_time)
        await page.goto(url, wait_until='networkidle', timeout=1000000)
        html_content = await page.content()
        await page_queue.put(page)
        soup = BeautifulSoup(html_content, 'lxml')
        article_content = soup.find('div', id='article-content')
        if article_content is None:
            content = '棍母'
        else:
            content = article_content.get_text().strip()
        if '开通权限请联系客服：400-671-1818' in content or '使用  我的钢铁 APP  扫码登录' in content:
            content = '暂无权限'
        json_datum['content'] = content
        print(f'fetched {i+1}-th article of page {page_idx} with content: "{content[:20].replace('\n', r'\n').replace('\r', r'\r')} ..."')
    async with aiofiles.open(result_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(json_data, ensure_ascii=False, indent=4))
    print(f'Page {page_idx} fetched and saved to {result_path}')
    return json_data



async def main():
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(
            headless=HEADLESS,
            args=[
                '--disable-blink-features=AutomationControlled',  # 移除自动化标识
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        page_queue = Queue()
        for _ in range(MAX_PAGE_NUM):
            page = await browser.new_page(
                # 伪造真实User-Agent
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                # 伪造真实浏览器特性
                extra_http_headers={
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Referer': 'https://www.mysteel.com/',  # 添加来源页
                }
            )
            await page_queue.put(page)
        # tasks = [fetch_page_links(page_queue, i) for i in range(1, 16+1)]
        tasks = [fetch_articles(page_queue, i) for i in range(16, 4, -1)]
        await asyncio.gather(*tasks)
        

if __name__ == '__main__':
    asyncio.run(main())
