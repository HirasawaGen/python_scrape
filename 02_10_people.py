import asyncio
import datetime


from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from bs4 import BeautifulSoup
from loguru import logger as LOGGER


from database import ZenianTable, ZenianData


LIMITER = AsyncLimiter(60)  # 30 requests per minute


async def fetch(
    session: ClientSession,
    table: ZenianTable,
    page_idx: int,
    keyword: str,
    is_fuzzy: bool,
):
    url = 'http://search.people.cn/search-platform/front/search'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
        'Content-Type': 'application/json;charset=UTF-8',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-US;q=0.7',
        'Connection': 'keep-alive',
    }

    payload = {
        "key": keyword,
        "page": page_idx,
        "limit": 10,
        "hasTitle": True,
        "hasContent": True,
        "isFuzzy": is_fuzzy,
        "type": 0,
        "sortType": 2,
        "startTime": 0,
        "endTime": 0,
        "belongsId": []
    }

    # Post this payload to the search API

    async with (
        LIMITER,
        session.post(
            url,
            json=payload,
            headers=headers,
        ) as resp
    ):
        LOGGER.info(f"Fetching page {page_idx} of keyword {keyword} ...")
        if resp.status != 200:
            LOGGER.error(f"Failed to fetch page {page_idx} of keyword {keyword} with status {resp.status}")
            LOGGER.error(await resp.text())
            return
        json_resp = await resp.json()
        LOGGER.info(f"Got http response from page {page_idx} of keyword {keyword}, processing...")
    if not isinstance(json_resp, dict) and 'data' not in json_resp:
        LOGGER.error('Invalid response format')
        return
    json_resp = json_resp['data']
    if not isinstance(json_resp, dict) and 'records' not in json_resp:
        LOGGER.error('Invalid response format')
        return
    records = json_resp['records']
    if not isinstance(records, list):
        LOGGER.error('Invalid response format')
        return
    data: list[ZenianData] = [{
            'url': record['url'],
            'title': BeautifulSoup(record['title'], 'lxml').get_text(),
            'publish_time': datetime.datetime.fromtimestamp(record['inputTime'] // 1000).strftime('%Y-%m-%d %H:%M:%S'),
            'content': BeautifulSoup(record['contentOriginal'], 'lxml').get_text(),
            'source': '人民网',
            'catg': '新闻公告',
            'section': f'{keyword}新闻',
        } for record in records
        if isinstance(record, dict)
        and {
            'url',
            'title',
            'inputTime',
            'contentOriginal'
        }.issubset(record.keys())
    ]
    LOGGER.info(f"Processed {len(data)} records from page {page_idx} of keyword {keyword}")
    await table.save(data)
    LOGGER.info(f"Saved {len(data)} records from page {page_idx} of keyword {keyword} to database")


# TOTAL = 2685
# KEYWORD = '储氢材料'

PARAMS = [
    {'total': 1882, 'keyword': '镍', 'is_fuzzy': True},
    {'total': 1823, 'keyword': '锡', 'is_fuzzy': True},
    {'total': 482, 'keyword': '锆', 'is_fuzzy': False},
    {'total': 402, 'keyword': '锗', 'is_fuzzy': False},
    {'total': 147, 'keyword': '储氢材料', 'is_fuzzy': False},
    {'total': 324, 'keyword': '永磁材料', 'is_fuzzy': False},
    {'total': 241, 'keyword': '发光材料', 'is_fuzzy': False},
]


async def main():
    for param in PARAMS:
        total = param['total']
        keyword = param['keyword']
        max_pages = total // 10 + 1
        is_fuzzy = param['is_fuzzy']
        async with (
            ZenianTable() as table,
            ClientSession() as session,
        ):
            tasks = [
                fetch(session, table, i, keyword, is_fuzzy)
                for i in range(1, max_pages+1)
            ]
            # tasks = tasks[:1]  # for debug
            await asyncio.gather(*tasks)
            await table.export('人民网', '新闻公告', f'{keyword}新闻', min_length=50)


if __name__ == '__main__':
    asyncio.run(main())
