from typing import Literal
import json
import asyncio
from urllib.parse import quote, urlparse
import random

from requests import Session
from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth
from loguru import logger
from aiolimiter import AsyncLimiter
from bs4 import BeautifulSoup

from database import ZenianData, ZenianTable
from page_pool import PagePool


SECTION = '永磁材料研报'


async def get_cookies(keyword: str) -> dict[str, str]:
    # url = f'https://so.eastmoney.com/news/s?keyword={quote(keyword)}&type=content'
    url = f'https://caifuhao.eastmoney.com/'
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url, wait_until='load')
        cookies = await page.context.cookies()
        await browser.close()
    return {
        cookie['name']: cookie['value']
        for cookie in cookies
        if 'name' in cookie
        and 'value' in cookie
    }


LIMITER = AsyncLimiter(1, 5)
TYPE = 'researchReport'


async def fetch_page(
    session: Session,
    j_query_param1: str,
    j_query_param2: str,
    keyword: str,
    search_scope: Literal["CONTENT", "TITLE"],
    page_idx: int,
    table: ZenianTable,
    type_: str,
) -> list[ZenianData]:
    cb = f'jQuery{j_query_param1}_{j_query_param2}'
    param_ = {
        'uid': '',
        'keyword': keyword,
        'type': [type_],
        'client': 'web',
        'clientType': 'web',
        'clientVersion': 'curr',
        'param': {
            type_: {
                'searchScope': search_scope,
                'sort': 'DEFAULT',
                'pageSize': 10,
                'pageIndex': page_idx,
                'preTag': '',
                'postTag': '',
            }
        }
    }
    param = json.dumps(
        param_,
        ensure_ascii=False,
        indent=None
    )
    param = param.replace(' ', '')
    param = param.replace('{', '%7B')
    param = param.replace('}', '%7D')
    param = param.replace('[', '%5B')
    param = param.replace(']', '%5D')
    param = param.replace(':', '%3A')
    param = param.replace(',', '%2C')

    url = f'https://search-api-web.eastmoney.com/search/jsonp?cb={cb}&param={param}'
    async with LIMITER:
        resp = session.get(url)
    if resp.status_code != 200:
        logger.error(f'Failed to fetch data from eastmoney, status code: {resp.status_code}')
        return []
    else:
        raw_json = resp.text[len(cb) + 1:-1]
        raw_data = json.loads(raw_json)
        try:
            raw_data = raw_data['result'][TYPE]
        except KeyError:
            logger.error(f'Failed to parse data from eastmoney, keyword: {keyword}, page {page_idx}')
            return []
        if len(raw_data) == 0:
            logger.error(f'No data found from eastmoney, keyword: {keyword}, page {page_idx}')
            return []
        data: list[ZenianData] = [
            {
                'url': datum['url'],
                'title': datum['title'],
                'source': '东方财富网',
                'catg': '新闻公告',
                'section': SECTION,
                'publish_time': datum['date']
            }
            for datum in raw_data
            if {'url', 'title', 'date'}.issubset(datum.keys())
        ]
        logger.info(f'Got {len(data)} data from eastmoney, keyword: {keyword}, page {page_idx}')
        # with open(f'data_{keyword}_{page_idx}_{page_idx+page_size}.json', 'w', encoding='utf-8') as f:
        #     f.write(json.dumps(
        #         data,
        #         ensure_ascii=False,
        #         indent=4
        #     ))
        saved_count = await table.save(data)
        logger.info(f'Saved {saved_count} data to database, keyword: {keyword}, page {page_idx}')
        return data

SELECTOR_MAPPING = {
    'data.eastmoney.com': 'div.ctx-body',
    'finance.eastmoney.com': 'div.txtinfos',
    'stock.eastmoney.com': 'div.txtinfos',  # 会重定向到finance.eastmoney.com，所以用一个selector
    'biz.eastmoney.com': 'div.txtinfos',  # 会重定向到finance.eastmoney.com，所以用一个selector
    'caifuhao.eastmoney.com': 'div.article-body',
    'fund.eastmoney.com': '#ContentBody',
}

async def fetch_content(
    session: Session,
    url: str,
    table: ZenianTable,
):
    domain = urlparse(url).netloc
    # if domain == 'caifuhao.eastmoney.com':
    #     # 被这个网页反爬了。先跳过吧。
    #     logger.info(f'Skip caifuhao.eastmoney.com, url: {url}')
    #     return
    if not domain in SELECTOR_MAPPING:
        logger.error(f'No selector for domain {domain}')
        return
    selector = SELECTOR_MAPPING[domain]

    async with LIMITER:
        resp = session.get(url)
        if resp.status_code != 200:
            logger.error(f'Failed to fetch content from {url}, status code: {resp.status_code}')
            return
        html_content = resp.text

    soup = BeautifulSoup(html_content, 'lxml')
    content_div = soup.select_one(selector)
    if content_div is None:
        logger.error(f'No content div found for {url}')
        return
    content = content_div.get_text(strip=True)
    content = content.replace('炒股第一步，先开个股票账户','')
    await table.fill_content(url, content)
    logger.info(f'Got content for {url}: {content[:100]}')


async def main():
    #  jQuery35106909354129353065_1770814414954
    j_query_param1 = '3510698419074577396'
    j_query_param2 = '1770813587536'
    keyword = '永磁材料'
    search_scope = 'CONTENT'
    # page_size = 100
    cookies = await get_cookies(keyword)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36',
        'Referer': 'https://so.eastmoney.com/',
    }
    session = Session()
    session.cookies.update(cookies)
    session.headers.update(headers)
    async with ZenianTable() as table:
        data = await table.load(source='东方财富网', catg='新闻公告')
        data = [
            datum
            for datum in data
            if datum.get('content', 'None') == 'None'
        ]
        logger.info(f'Got {len(data)} data from database')
        tasks = [
            fetch_content(
                session,
                datum['url'],
                table,
            )
            for datum in data
        ]
        random.shuffle(tasks)
        await asyncio.gather(*tasks)
        for section in ['永磁材料资讯', '永磁材料研报', '永磁材料文章']:
            await table.export(source='东方财富网', catg='新闻公告', section=section)
        # tasks = [
        #     fetch_page(
        #         session,
        #         j_query_param1,
        #         j_query_param2,
        #         keyword,
        #         search_scope,
        #         i,
        #         table,
        #         TYPE,
        #     )
        #     for i in range(1, 2)
        # ]
        # results = await asyncio.gather(*tasks)


async def fetch_content_pw(
    page_pool: PagePool,
    url: str,
    table: ZenianTable,
):
    domain = urlparse(url).netloc
    if not domain in SELECTOR_MAPPING:
        logger.error(f'No selector for domain {domain}')
        return
    selector = SELECTOR_MAPPING[domain]
    async with page_pool() as page:
        try:
            await page.goto(url, wait_until='domcontentloaded')
        except Exception as e:
            logger.error(f'Failed to fetch content from {url}, error: {e}')
            return
        html_content = await page.content()
    soup = BeautifulSoup(html_content, 'lxml')
    content_div = soup.select_one(selector)
    if content_div is None:
        logger.error(f'No content div found for {url}')
        return
    content = content_div.get_text(strip=True)
    content = content.replace('炒股第一步，先开个股票账户','')
    await table.fill_content(url, content)
    logger.info(f'Got content for {url}: {content[:100]}')


async def main_():
    cookies_ = await get_cookies('')
    cookies = [
        {
            'name': name,
            'value': value,
            'domain': 'caifuhao.eastmoney.com',
            'path': '/',
            'expires': -1,
            'httpOnly': False,
        }
        for name, value in cookies_.items()
    ]
    async with (
        async_playwright() as p,
        ZenianTable() as table,
    ):
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36',
            extra_http_headers={
                'Referer': 'https://caifuhao.eastmoney.com/',
            },
            accept_downloads=True,
        )
        stealth = Stealth()
        await stealth.apply_stealth_async(context)
        await context.add_cookies(cookies)  # type: ignore
        page_pool = PagePool(context, 3, 2)
        data = await table.load(source='东方财富网', catg='新闻公告')
        data = [
            datum
            for datum in data
            if datum.get('content', 'None') == 'None'
        ]
        logger.info(f'Got {len(data)} data from database')
        tasks = [
            fetch_content_pw(
                page_pool,
                datum['url'],
                table,
            )
            for datum in data
        ]
        random.shuffle(tasks)
        await asyncio.gather(*tasks)
        for section in ['永磁材料资讯', '永磁材料研报', '永磁材料文章']:
            await table.export(source='东方财富网', catg='新闻公告', section=section)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main_())

