import asyncio
from asyncio import Queue
from pathlib import Path
import json
import urllib

from playwright.async_api import async_playwright
from playwright.async_api import Page, Browser
from bs4 import BeautifulSoup
import aiofiles


ROOT = Path(__file__).parent
MAX_PAGE_NUM = 5
KEYWORDS = ['有色金属', '钨', '锂']
# KEYWORDS = ['有色金属']
PAGE_QUEUE: Queue[Page] = Queue()
HEADLESS = False


ARTICLE_POS_TABLE: dict[str, str] = {
    'www.newskj.com': 'div.content-zw',
    'wz.newskj.com': 'div.wenzzw',
    'www.jxgztv.com': '棍母域名',
}


CONTINUE_URLS = {
    'http://www.newskj.com/news/system/2021/11/02/030345545.shtml',
    'http://www.newskj.com/news/system/2022/04/30/030406808.shtml',
    'http://www.newskj.com/news/system/2021/02/20/030272304.shtml',
    'http://www.newskj.com/news/system/2019/01/04/030012887.shtml',
    'http://www.newskj.com/vr/system/2018/12/31/030011363.shtml',
}


async def fetch_page_links(page: Page, keyword: str):
    await page.goto(
        'https://search.newskj.com/m_fullsearch/searchurl/mfullsearch!descResult.do',
        wait_until='domcontentloaded'
    )
    input_tag = await page.query_selector('input.hdi')
    submic_tag = await page.query_selector('input.btn-global')
    await input_tag.type(keyword)
    await submic_tag.click()
    page_idx = 1
    while True:
        await asyncio.sleep(1)
        await page.wait_for_load_state('domcontentloaded')
        soup = BeautifulSoup(await page.content(), 'lxml')
        tbody_tags = soup.find_all('tbody')
        if len(tbody_tags) != 3:
            break
        tbody_tag = tbody_tags[1]
        if tbody_tag is None:
            break
        tr_tags = tbody_tag.find_all('tr')
        article_num = len(tr_tags) // 3
        ans: list[dict] = []
        for i in range(article_num):
            tr_tag1 = tr_tags[i*3]
            tr_tag3 = tr_tags[i*3+2]
            search_title = tr_tag1.find_all('td')[1]
            a_tag = search_title.find_all('a')[0]
            url = a_tag.get('href')
            title = a_tag.get_text()
            search_botton = tr_tag3.find_all('td')[1]
            search_botton_text = search_botton.get_text()
            publish_time = search_botton_text.split()[1]
            publish_time += ' 00:00:00'
            ans.append({
                'url': url,
                'title': title,
                'publish_time': publish_time,
            })
        file_root = ROOT / 'pages' / keyword
        if not file_root.exists():
            file_root.mkdir(parents=True)
        file_path = file_root / f'page_{page_idx}.json'
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(
                ans,
                ensure_ascii=False,
                indent=4
            ))
        page_idx += 1
        await page.evaluate(f'() => pageNoSubmit({page_idx})')
        print(f'page {page_idx} of "{keyword}" is loaded')
        

async def fetch_article(
    keyword: str,
    page_idx: int,
    page_queue: Queue[Page]
) -> list[dict]:
    page_path = ROOT / 'pages' / keyword / f'page_{page_idx}.json'
    if not page_path.exists():
        return []
    result_root = ROOT /'results' / keyword
    if not result_root.exists():
        result_root.mkdir(parents=True)
    result_path = result_root / f'result_{page_idx}.json'
    if result_path.exists():
        return []
    async with aiofiles.open(page_path, 'r', encoding='utf-8') as f:
        page_data = json.loads(await f.read())
    for i in range(len(page_data)):
        await asyncio.sleep(1)
        url = page_data[i]['url']
        if url in CONTINUE_URLS:
            continue
        domain = urllib.parse.urlparse(url).netloc
        pos = ARTICLE_POS_TABLE.get(domain, '')
        if pos == '':
            raise ValueError(f'domain "{domain}" has no article position')
        if pos == '棍母域名':
            page_data[i]['content'] = '棍母域名'
            continue
        tag_name, class_name = pos.split('.')
        page = await page_queue.get()
        for j in range(3):
            try:
                await page.goto(url, wait_until='domcontentloaded')
                break
            except Exception as e:
                sleep_time = (1+j)**2
                print(f'page {page_idx} of "{keyword}" failed to load, retry in {sleep_time} seconds')
                await asyncio.sleep(sleep_time)
        try:
            html_content = await page.content()
        except Exception as e:
            print(f'url: {url}\n')
            raise e
        soup = BeautifulSoup(await page.content(), 'lxml')
        await page_queue.put(page)
        if '您要找的页面不存在或已删除，点击跳转到首页' in soup.get_text():
            page_data[i]['content'] = '棍母内容'
            continue
        content = soup.find(tag_name, class_=class_name)
        if content is None:
            choice = input(f'page: {url}\nis not available, do you want to continue? (y/n) ')
            if choice.lower() == 'y':
                continue
        page_data[i]['content'] = content.get_text().strip()
        print(f'The {i+1}-th article of page {page_idx} is fetched')
    async with aiofiles.open(result_path, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(
            page_data,
            ensure_ascii=False,
            indent=4
        ))
    print(f'page {page_idx} of "{keyword}" is all fetched')
    return page_data

    
async def main():
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=HEADLESS)
        # search_pages: list[Page] = await asyncio.gather(*[
        #     browser.new_page()
        #     for _ in range(len(KEYWORDS))
        # ])
        # initial_tasks = [
        #     fetch_page_links(page, keyword)
        #     for page, keyword in zip(search_pages, KEYWORDS)
        # ]
        # await asyncio.gather(*initial_tasks)
        for _ in range(MAX_PAGE_NUM):
            page = await browser.new_page()
            await PAGE_QUEUE.put(page)
        # tasks_钨 = [
        #     fetch_article('钨', i, PAGE_QUEUE)
        #     for i in range(1, 100+1)
        # ]
        tasks_锂 = [
            fetch_article('锂', i, PAGE_QUEUE)
            for i in range(1, 68+1)
        ]
        for i in range(1, 4):
            tasks = [
                fetch_article('锂', j, PAGE_QUEUE)
                for j in range(i*20, i*20+20)
            ]
            await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
