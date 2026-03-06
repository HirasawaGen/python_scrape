import asyncio

from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from bs4 import BeautifulSoup
from loguru import logger as LOGGER

from database import ZenianData, ZenianTable


LIMITER = AsyncLimiter(max_rate=1, time_period=1)


async def search(
    session: ClientSession,
    table: ZenianTable,
    page_idx: int,
):
    if page_idx == 1:
        idx_ = 'index'
    else:
        idx_ = str(page_idx)
    search_url = f'https://titan.chinania.org.cn//html/xingyezixun/{idx_}.html'
    async with (
        LIMITER,
        session.get(search_url) as resp,
    ):
        LOGGER.info(f'Fetching page-{page_idx}')
        if resp.status!= 200:
            LOGGER.error(f'Failed to fetch page-{page_idx}, status code: {resp.status}')
            return []
        html_content = await resp.text()
    LOGGER.info(f'Parsing page-{page_idx}')
    soup = BeautifulSoup(html_content, 'lxml')
    a_tags = soup.select('a.inbox')
    data: list[ZenianData] = []
    for a_tag in a_tags:
        div_word = a_tag.select_one('div.word')
        div_time = a_tag.select_one('div.time')
        url = a_tag['href']
        if div_word is None or div_time is None:
            LOGGER.warning(f'Invalid data on page-{page_idx}, skipping')
            continue
        if not isinstance(url, str):
            LOGGER.warning(f'Invalid url on page-{page_idx}, skipping')
            continue
        title = div_word.text.strip()
        publish_time = div_time.text.strip() + ' 00:00:00'
        data.append({
            'url': url,
            'title': title,
            'publish_time': publish_time,
            'catg': '行业研究',
            'source': '中国有色金属协会钛锆铪钒分会',
        })
    LOGGER.info(f'Fetched {len(data)} items on page-{page_idx}')
    saved_count = await table.save(data)
    LOGGER.info(f'Saved {saved_count} items on page-{page_idx}')
    return data


'''
行业资讯，内容带稀土，做好去重
行业资讯，内容带有色金属，注意相关性，做好去重
行业资讯，内容带钛，注意相关性，做好去重
行业资讯，内容带锆，注意相关性，做好去重
行业资讯，内容带铪，注意相关性，做好去重
行业资讯，内容带钒，注意相关性，做好去重
'''


sections = ('稀土', '有色金属', '钛', '锆', '铪', '钒')


async def fetch_content(
    session: ClientSession,
    table: ZenianTable,
    data: ZenianData,
) -> tuple[str, str]:
    url = data['url']
    if not 'title' in data:
        LOGGER.warning(f'Empty title of {url}, skipping')
        return '', ''
    title = data['title']
    async with (
        LIMITER,
        session.get(url) as resp,
    ):
        LOGGER.info(f'Fetching content of {title}')
        if resp.status != 200:
            LOGGER.error(f'Failed to fetch content of {title}, status code: {resp.status}')
            return '', ''
        html_content = await resp.text()
    soup = BeautifulSoup(html_content, 'lxml')
    detail_body = soup.select_one('div.detail_body')
    if detail_body is None:
        LOGGER.error(f'Invalid content of {title}, skipping')
        return '', ''
    content = detail_body.text.strip()
    section = ''
    for section_ in sections:
        if section_ in content or section_ in title:
            section = section_
            break
    if not len(section):
        LOGGER.warning(f'No section found for {title}, skipping')
        return '', ''
    LOGGER.info(f'Fetched content of {title}:\n{content[:100]}')
    await table.fill_content_and_section(url, content, section)
    return content, section


async def main():
    async with (
        ClientSession() as session,
        ZenianTable() as table,
    ):
        # await asyncio.gather(*[
        #     search(session, table, i)
        #     for i in range(1, 169+1)
        # ])
        data = await table.load('中国有色金属协会钛锆铪钒分会', '行业研究')
        data = [
            datum
            for datum in data
            if datum.get('content', 'None') == 'None'
        ]
        LOGGER.info(f'Fetching content of {len(data)} items')
        await asyncio.gather(*[
            fetch_content(session, table, datum)
            for datum in data
        ])
        await asyncio.gather(*[
            table.export('中国有色金属协会钛锆铪钒分会', '行业研究', section)
            for section in sections
        ])


if __name__ == '__main__':
    asyncio.run(main())


