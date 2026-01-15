import asyncio

from bs4 import BeautifulSoup

from fetchers import BasePageFetcher, BaseArticleFetcher
from database import ZenianData
from playwright.async_api import async_playwright


class PageFetcher中粉锂电(BasePageFetcher):
    async def parse_soup(self, soup: BeautifulSoup) -> list[ZenianData]:
        items = soup.find_all('div', class_='jishu_txt')
        ans: list[ZenianData] = []
        for item in items:
            a_tag = item.select_one('a')
            span_tag = item.select_one('span')
            url = a_tag['href']
            if not url.startswith('http'):
                url = 'https://lbm.cnpowder.com.cn/' + url
            title = a_tag.text.strip()
            span_text = span_tag.text.strip()
            publish_time = span_text[:10]
            publish_time = publish_time.replace('年', '-').replace('月', '-').replace('日', '')
            publish_time += ' 00:00:00'
            ans.append({
                'url': url,
                'title': title,
                'publish_time': publish_time,
            })
        return ans


class ArticleFetcher中粉锂电(BaseArticleFetcher):
    async def parse_soup(self, soup: BeautifulSoup) -> str:
        content = soup.find('div', class_='zixunxq_txt')
        if content is None:
            return ''
        return content.text.strip()


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        queue = asyncio.Queue()
        await queue.put(page)
        page_fetcher_技术资料 = PageFetcher中粉锂电(
            page_queue=queue,
            url_pattern='https://lbm.cnpowder.com.cn/jishu.php?pn={}',
            max_page_idx = 62,
            source='中粉锂电',
            catg='材料研究',
            section='技术资料',
        )
        # await page_fetcher_技术资料()
        article_fetcher_技术资料 = ArticleFetcher中粉锂电(
            page_queue=queue,
            min_sleep_time=2.5,
            max_sleep_time=5.0,
            source='中粉锂电',
            catg='材料研究',
            section='技术资料',
        )
        # await article_fetcher_技术资料()
        page_fetcher_应用 = PageFetcher中粉锂电(
            page_queue=queue,
            url_pattern='https://lbm.cnpowder.com.cn/yingyong.php?pn={}',
            max_page_idx = 1,
            source='中粉锂电',
            catg='应用消费',
            section='应用',
        )
        # await page_fetcher_应用()
        page_fetch_资讯 = PageFetcher中粉锂电(
            page_queue=queue,
            url_pattern='https://lbm.cnpowder.com.cn/news.php?pn={}',
            min_page_idx=290,
            max_page_idx = 290,
            source='中粉锂电',
            catg='资讯',
            section='资讯',
        )
        # FIXME: page 196 0 data???  290
        # await page_fetch_资讯()
        article_fetcher_应用 = ArticleFetcher中粉锂电(
            page_queue=queue,
            min_sleep_time=2.5,
            max_sleep_time=5.0,
            source='中粉锂电',
            catg='应用消费',
            section='应用',
        )
        # await article_fetcher_应用()
        article_fetcher_资讯 = ArticleFetcher中粉锂电(
            page_queue=queue,
            min_sleep_time=2.5,
            max_sleep_time=5.0,
            source='中粉锂电',
            catg='资讯',
            section='资讯',
        )
        # await article_fetcher_资讯()
        await asyncio.gather(
            article_fetcher_技术资料(),
            article_fetcher_应用(),
            article_fetcher_资讯(),
        )


if __name__ == '__main__':
    asyncio.run(main())
