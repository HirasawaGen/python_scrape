import asyncio
from asyncio import Queue, Semaphore
from pathlib import Path
import random
import json

from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from playwright.async_api import Page, Browser
from bs4 import BeautifulSoup
import aiofiles


SEM = Semaphore(10)
URL = 'https://www.cgs.gov.cn/was5/web/search?page={page_idx}&channelid=271109&searchword='
HEADLESS = False
MAX_PAGE_NUM = 3
ROOT = Path(__file__).parent / 'cgs_gov'


async def fetch_page_links(page_queue: Queue[Page], page_idx: int, keyword: str) -> list[dict]:
    file_path = ROOT / 'pages' / f'page_{keyword}_{page_idx}.json'
    file_exists = await asyncio.to_thread(file_path.exists)
    if file_exists:
        return []
    ans = []
    url = URL.format(page_idx=page_idx) + keyword
    page = await page_queue.get()
    sleep_time = random.uniform(1.5 * MAX_PAGE_NUM, 2.5 * MAX_PAGE_NUM)
    # 因为代码的并发性很高，所以这里设置得sleep时间比较长
    await asyncio.sleep(sleep_time)
    try:
        print(f'loading page {page_idx} of keyword "{keyword}"...')
        await page.goto(url, wait_until='networkidle', timeout=30000000)
    except Exception as e:
        print(f'page {page_idx} failed: {e}')
        await page_queue.put(page)
        return []
    html_content = await page.content()
    await page_queue.put(page)
    print(f'loaded page {page_idx} of keyword "{keyword}".')
    soup = BeautifulSoup(html_content, 'html.parser')
    div_xly_boxa_tags = soup.find_all('div', class_='xly_boxa')
    if not div_xly_boxa_tags:
        print(f'no div.xly_boxa of file {file_path}')
        return []
    for div_xly_boxa_tag in div_xly_boxa_tags:
        a_tag = div_xly_boxa_tag.find('a')
        div_pubtime_tag = div_xly_boxa_tag.find('div', class_='pubtime')
        if div_pubtime_tag is None or a_tag is None:
            await page_queue.put(page)
            continue
        title = a_tag.get_text()
        url = a_tag.get('href')
        publish_time = div_pubtime_tag.get_text().strip()
        publish_time = publish_time.split('发布时间：')[-1]
        publish_time = publish_time.replace('.', '-')
        ans.append({'title': title, 'url': url, 'publish_time': publish_time})
    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(ans, ensure_ascii=False, indent=4))
    print(f'page {page_idx} of keyword "{keyword}" fetched.')
    return ans


async def fetch_articles(page_queue: Queue[Page], page_idx: int, keyword: str) -> list[dict]:
    page_path = ROOT / 'pages' / f'page_{keyword}_{page_idx}.json'
    result_path = ROOT / 'results' / f'result_{keyword}_{page_idx}.json'
    result_exists = await asyncio.to_thread(result_path.exists)
    if result_exists:
        return []
    json_data: list[dict]
    async with aiofiles.open(page_path, 'r', encoding='utf-8') as f:
        json_data = json.loads(await f.read())
    async with SEM:
        for i, json_datum in enumerate(json_data):
            url = json_datum['url']
            if not (url.startswith('http')):
                url = 'https://www.cgs.gov.cn' + url
                json_data[i]['url'] = url
            if 'www.cgs.gov.cn' not in url:
                continue
            page = await page_queue.get()
            sleep_time = random.uniform(3.2 * MAX_PAGE_NUM, 12.8 * MAX_PAGE_NUM)
            await asyncio.sleep(sleep_time)
            await page.goto(url, wait_until='networkidle', timeout=30000000)
            html_content = await page.content()
            await page_queue.put(page)
            soup = BeautifulSoup(html_content, 'lxml')
            c_body = soup.find('div', class_='c_body')
            if c_body is None:
                print(f'no div.c_body of file {page_path}[{i}]')
                continue
            content = c_body.get_text().strip()
            json_data[i]['content'] = content
            print(f'{i+1}-th article of keyword {keyword} page {page_idx}, is fetched.')
            print(f'content: {content[:20].replace('\n', r'\n').replace('\r', r'\r')}...')
    async with aiofiles.open(result_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(json_data, ensure_ascii=False, indent=4))
    return json_data
        



async def check_file(file_path: Path):
    exists = await asyncio.to_thread(file_path.exists)
    if not exists:
        print(f'file {file_path} not exists.')
        return False
    return True



async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()
        await context.clear_cookies()
        page_queue = Queue()
        slealth = Stealth()
        for i in range(MAX_PAGE_NUM):
            page = await browser.new_page()
            await slealth.apply_stealth_async(page)
            await page_queue.put(page)
        # 钨 page_idx in [1, 117]
        mapping = {
            '有色金属': 96,
            '钨': 117,
            '锂': 95,
            '铜': 299,
            '铝': 78,
            '镁': 34
        }
        
        fetch_link_tasks = []
        for keyword, max_page_idx in mapping.items():
            fetch_link_tasks += [fetch_page_links(page_queue, page_idx, keyword) for page_idx in range(1, max_page_idx+1)]
        await asyncio.gather(*fetch_link_tasks)
        fetch_articles_tasks = []
        for keyword, max_page_idx in mapping.items():
            fetch_articles_tasks += [fetch_articles(page_queue, page_idx, keyword) for page_idx in range(1, max_page_idx+1)]
        await asyncio.gather(*fetch_articles_tasks)

        

if __name__ == '__main__':
    asyncio.run(main())
        