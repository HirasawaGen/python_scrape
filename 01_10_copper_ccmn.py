import asyncio
import random

from bs4 import BeautifulSoup

from fetchers import BasePageFetcher, BaseArticleFetcher
from database import ZenianData
from playwright.async_api import async_playwright


class PageFetcher长江有色金属网(BasePageFetcher):
    async def parse_soup(self, soup: BeautifulSoup) -> list[ZenianData]:
        content_tags = soup.find_all('div', class_='finance_content')
        ans = []
        for tag in content_tags:
            finance_title = tag.find('p', class_='finance_title')
            a_tag = finance_title.find('a')
            url = a_tag.get('href')
            title = a_tag.get_text().strip()
            finance_other = tag.find('p', class_='finance_others')
            if not url.startswith('https://copper.ccmn.cn'):
                url = 'https://copper.ccmn.cn' + url
            if not finance_other:
                print(f'finance_other is None: {url}')
                publish_time = '2026-1-10 00:00:00'
            else:
                span = finance_other.find('span')
                publish_time = span.get_text().strip() + ' 00:00:00'
            ans.append({
                'title': title,
                'url': url,
                'publish_time': publish_time,
            })
        return ans
            
    
    async def _init_page(self, page):
        click_count = 0
        while True:
            button = page.locator('//div[@class="load-more"]')
            count = await button.count()
            if count == 0:
                break
            text = await button.text_content()
            if '加载更多' not in text:
                break
            await button.click()
            print(f'clicked once: {click_count}')
            click_count += 1
            await asyncio.sleep(random.uniform(1.5, 3))
            await page.wait_for_load_state('domcontentloaded')
            
        
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        queue = asyncio.Queue()
        await queue.put(page)
        fetcher = PageFetcher长江有色金属网(
            'https://copper.ccmn.cn/copperyszs/',
            queue,
            max_page_idx=1,
            source='长江铜业网',
            catg='知识百科',
            section='铜知识'
        )
        await fetcher()
        
        
if __name__ == '__main__':
    asyncio.run(main())
