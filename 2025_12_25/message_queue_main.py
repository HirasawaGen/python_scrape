import asyncio
from asyncio import Queue, Event, Semaphore
from collections import OrderedDict
from pathlib import Path
import json

from playwright.async_api import Browser, async_playwright


URL_PATTERN = 'http://www.li-b.cn/search.php?q=%E9%94%82&page={}'
TIMEOUT = 500000
START_PAGE = 1158
END_PAGE = 1366
ROOT = Path(__file__).parent

dones = [Event() for _ in range(START_PAGE, END_PAGE + 1)]
link_counts: dict[int, int] = {}  # valid link counts for each page
task_done = Event()

# article_links_queue: Queue[tuple[int, str]] = Queue(maxsize=20)
article_links_queue: Queue[tuple[int, str]] = Queue(maxsize=20)
# results_queue: Queue[tuple[int, OrderedDict]] = Queue(maxsize=1000)
results_queues: list[Queue[OrderedDict]] = [Queue(maxsize=30) for _ in range(START_PAGE, END_PAGE + 1)]


async def produce_page_links(
    start_page: int,
    end_page: int,
    browser: Browser
):
    page = await browser.new_page()
    for i in range(start_page, end_page + 1):
        url = URL_PATTERN.format(i)
        try:
            await page.goto(url, timeout=TIMEOUT, wait_until='domcontentloaded')
        except Exception as e:
            # print(f'Failed to load page {url}: {e}')
            await dones[i - start_page].wait()
            continue
        await page.wait_for_selector('div.post-multi h2 > a', timeout=TIMEOUT)
        a_tags = page.locator('div.post-multi h2 > a')
        a_tags_count = await a_tags.count()
        link_counts[i] = 0
        for j in range(a_tags_count):
            a_tag = a_tags.nth(j)
            text = await a_tag.inner_text()
            if '锂' not in text:
                continue
            link_counts[i] += 1
            href = await a_tag.get_attribute('href')
            await article_links_queue.put((i, href))
        print(f'Found {link_counts[i]} links on page {i}')
            
            # print(f'Queue size: {article_links_queue.qsize()}')


# 堵住了 一直不消费 不知道堵哪了
async def consume_article_links(browser: Browser):
    page = await browser.new_page()
    while not task_done.is_set():
        data = OrderedDict()
        # print(f'Waiting for article link...')
        page_index, link = await article_links_queue.get()
        print(f'Got article link {link} from page {page_index}')
        # print(f'Extracting data from {link}')
        try:
            await page.goto(link, timeout=TIMEOUT, wait_until='domcontentloaded')
            await page.wait_for_selector('#article', timeout=TIMEOUT)
        except Exception as e:
            data['error'] = str(e)
            # print(f'Failed to extract data from {link}: {e}')
            # await page.close()
            continue
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
        await results_queues[page_index - START_PAGE].put(data)
        link_counts[page_index] -= 1
        if link_counts[page_index] <= 0:
            dones[page_index - START_PAGE].set()
            del link_counts[page_index]
        print(f'Extracted data from {link} at page {page_index}')
    await page.close()
    print('PAGE CLOSED!!!')


async def save_results():
    for i in range(START_PAGE, END_PAGE + 1):
        results: list[OrderedDict] = []
        print(f'Waiting for page {i} to finish...')
        await dones[i - START_PAGE].wait()
        print(f'Saving results of page {i}')
        while not results_queues[i - START_PAGE].empty():
            data = await results_queues[i - START_PAGE].get()
            results.append(data)
        with (ROOT / 'results' / f'page_{i}.json').open('w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
    task_done.set()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page_links_producer = produce_page_links(START_PAGE, END_PAGE, browser)
        article_links_consumers = [consume_article_links(browser) for _ in range(20)]
        results_saver = save_results()
        await asyncio.gather(page_links_producer, *article_links_consumers, results_saver)
        browser.close()


if __name__ == '__main__':
    asyncio.run(main())