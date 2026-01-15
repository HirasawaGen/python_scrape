import json
import asyncio
from collections import OrderedDict
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser


URL_PATTERN = 'http://www.li-b.cn/search.php?q=%E9%94%82&page={}'
TOTAL_PAGE = 1366
# TOTAL_PAGE = 3
HEADLESS = False
ROOT = Path(__file__).parent
START_ID = 30003402
TIMEOUT = 500000  # 网速太慢了


# TODO: 可以使用消息队列,一个协程返回link，另一个协程将link转为字典，最后一个协程将数据保存至本地

async def locate_links(page: Page) -> list[str]:
    await page.wait_for_selector('div.post-multi h2 > a', timeout=TIMEOUT)
    a_tags = page.locator('div.post-multi h2 > a')
    a_tags_count = await a_tags.count()
    links = []
    # ===============================>
    for i in range(a_tags_count):
        a_tag = a_tags.nth(i)
        text = await a_tag.inner_text()
        if '锂' not in text:
            continue
        href = await a_tag.get_attribute('href')
        links.append(href)
    return links


async def extract_data(link: str, browser: Browser) -> OrderedDict:
    print(f'Extracting data from {link}')
    data = OrderedDict()
    page = await browser.new_page()
    try:
        await page.goto(link, timeout=TIMEOUT, wait_until='domcontentloaded')
        await page.wait_for_selector('#article', timeout=TIMEOUT)
    except Exception as e:
        data['error'] = str(e)
        print(f'Failed to extract data from {link}: {e}')
        await page.close()
        return data
    catehead = page.locator('div.catehead')
    catehead_h2 = catehead.locator('h2')
    catehead_span = catehead.locator('span')
    span_inner_text = await catehead_span.inner_text()
    div_article = page.locator('#article')
    content = await div_article.inner_text()
    content = content.strip()
    splited_span_inner_text = span_inner_text.split('|')
    splited_span_inner_text = [s.strip() for s in splited_span_inner_text]
    publish_time = [s for s in splited_span_inner_text if s.startswith('时间')][0]
    publish_time = publish_time.split('：')[1].strip() + ' 00:00:00'
    data['title'] = await catehead_h2.inner_text()
    data['publish_time'] = publish_time
    data['source'] = '锂电网'
    data['url'] = page.url
    data['content'] = content
    data['catg'] = '新闻公告'
    await page.close()
    print(f'Extracted data from {link}')
    return data


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        page = await browser.new_page()
        for i in range(1334, TOTAL_PAGE+1):
            url = URL_PATTERN.format(i)
            print(f'Loading {url}')
            try:
                await page.goto(url, timeout=TIMEOUT, wait_until='domcontentloaded')
            except Exception as e:
                print(f'Failed to load {url}: {e}')
                continue
            links = await locate_links(page)
            print(f'Found {len(links)} links on page {i}')
            tasks = [extract_data(link, browser) for link in links]
            results = await asyncio.gather(*tasks)
            with (ROOT / 'results' / f'page_{i}.json').open('w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
        await browser.close()

def merge_results():
    results = []
    for i in range(1, TOTAL_PAGE+1):
        file_path = ROOT /'results' / f'page_{i}.json'
        if not file_path.exists():
            continue
        with file_path.open('r', encoding='utf-8') as f:
            results.extend(json.load(f))
    with (ROOT /'results' /'results.json').open('w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
                    

if __name__ == '__main__':
    asyncio.run(main())
    merge_results()
    