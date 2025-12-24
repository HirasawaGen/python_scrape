import json
from collections import OrderedDict
from pathlib import Path

from playwright.sync_api import sync_playwright, Page


URL_PATTERN = 'http://www.li-b.cn/search.php?q=%E9%94%82&page={}'
TOTAL_PAGE = 1366
# TOTAL_PAGE = 3
HEADLESS = False
ROOT = Path(__file__).parent
START_ID = 30003402
TIMEOUT = 500000  # 网速太慢了


def locate_links(page: Page) -> list[str]:
    page.wait_for_selector('div.post-multi h2 > a', timeout=TIMEOUT)
    a_tags = page.locator('div.post-multi h2 > a')
    a_tags_count = a_tags.count()
    links = ['' for _ in range(a_tags_count)]
    for i in range(a_tags_count):
        links[i] = a_tags.nth(i).get_attribute('href')
    return links


def extract_data(page: Page) -> OrderedDict:
    page.wait_for_selector('#article', timeout=TIMEOUT)
    data = OrderedDict()
    catehead = page.locator('div.catehead')
    catehead_h2 = catehead.locator('h2')
    catehead_span = catehead.locator('span')
    span_inner_text = catehead_span.inner_text()
    div_article = page.locator('#article')
    content = div_article.inner_text().strip()
    splited_span_inner_text = span_inner_text.split('|')
    splited_span_inner_text = [s.strip() for s in splited_span_inner_text]
    publish_time = [s for s in splited_span_inner_text if s.startswith('时间')][0]
    publish_time = publish_time.split('：')[1].strip() + ' 00:00:00'
    data['title'] = catehead_h2.inner_text()
    data['publish_time'] = publish_time
    data['source'] = '锂电网'
    data['url'] = page.url
    data['content'] = content
    data['catg'] = '新闻公告'
    return data


def main():
    results: list[OrderedDict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=2000)
        page = browser.new_page()
        
        for i in range(1, TOTAL_PAGE+1):
            url = URL_PATTERN.format(i)
            print(f'Loading {url}')
            try:
                page.goto(url, timeout=TIMEOUT)
            except Exception as e:
                print(f'Error: {e}')
                print(f'at page {i}')
                continue
            links = locate_links(page)
            for j, link in enumerate(links):
                print(f'Fetching {j+1}-th link of page {i}: {link}')
                new_page = browser.new_page()
                new_page.goto(link, timeout=TIMEOUT)
                try:
                    result = extract_data(new_page)
                    results.append(result)
                except Exception as e:
                    print(f'Error: {e}')
                    print(f'at page {i}, {j+1}-th link: {link}')
                new_page.close()
            # 每隔一页就保存一次，防止数据丢失
            print(f'Saving data to file...')
            with open(ROOT / 'results' / f'raw_data_{i}.json').open('w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
                    

if __name__ == '__main__':
    main()
    