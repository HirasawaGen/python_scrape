import asyncio
import datetime

from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from bs4 import BeautifulSoup
from loguru import logger as LOGGER

from database import ZenianData, ZenianTable


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
    'Content-Type': 'application/json;charset=UTF-8',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-US;q=0.7',
    'Connection': 'keep-alive',
}

LIMITER = AsyncLimiter(30)
SOURCE = '中国有色网'
CATG = '新闻公告'
SECTION = '储氢材料'


async def fetch_search(
    session: ClientSession,
    table: ZenianTable,
    start: int,
    keyword: str,
) -> list[ZenianData]:
    assert start >= 0 and start % 10 == 0, 'Start must be a positive integer multiple of 10'
    fetch_url = (
        'https://search.cnmn.com.cn/Search.aspx'
        f'?q={keyword}'
        f'&start={start}'
    )
    async with (
        LIMITER,
        session.get(fetch_url) as resp,
    ):
        if resp.status != 200:
            LOGGER.error(f'Failed to fetch {fetch_url}, status code: {resp.status}')
            return []
        html_content = await resp.text()
        LOGGER.info(f'Fetched starting from {start} for keyword {keyword}')
    soup = BeautifulSoup(html_content, 'lxml')
    results = soup.select('div.result')
    data: list[ZenianData] = []
    for result in results:
        '''html
        <div class="result"> 
            <h4>                
                <a href="http://www.cnmn.com.cn/ShowNews1.aspx?id=462620">国内首个模块化镁基固态自动供氢系统发布</a>
            </h4>
            <p> 
                艾氢技术1号自动化镁基模块供氢系统6月5日艾氢技术苏州有限公司以下简称ldquo艾氢技术rdquo发布国内首个模块化镁基固态供氢系统mdashmdash艾氢技术1号自动化镁基模块供氢系统该系统以镁基固态储氢材料为核心融合自动化模块化及兼容性的创新设计为多元用氢场景提供高效灵活的解决方案该系统由储氢
            </p>
            <div>
                <span class="path">
                    <a href="http://www.cnmn.com.cn/ShowNews1.aspx?id=462620">http://www.cnmn.com.cn/ShowNews1.aspx?id=462620</a>
                </span>
                <span class="time">2025/6/17 10:41:00</span>
            </div>  
        </div>
        '''
        a_tag = result.select_one('h4 a')
        if a_tag is None:
            continue
        title = a_tag.text.strip()
        url = a_tag['href']
        if not isinstance(url, str):
            continue
        span_time = result.select_one('div span.time')
        if span_time is None:
            continue
        publish_time_ = datetime.datetime.strptime(span_time.text.strip(), '%Y/%m/%d %H:%M:%S')
        publish_time = publish_time_.strftime('%Y-%m-%d %H:%M:%S')
        data.append({
            'title': title,
            'url': url,
            'publish_time': publish_time,
            'source': SOURCE,
            'catg': CATG,
            'section': SECTION,
        })
    LOGGER.info(f'Got {len(data)} results for keyword {keyword} starting from {start}')
    await table.save(data)
    LOGGER.info(f'Saved {len(data)} results for keyword {keyword} starting from {start} to database')
    return data


async def fetch_content(
    session: ClientSession,
    table: ZenianTable,
    url: str,
) -> str:
    async with (
        LIMITER,
        session.get(url, headers=HEADERS) as resp,
    ):
        if resp.status != 200:
            LOGGER.error(f'Failed to fetch {url}, status code: {resp.status}')
            return ''
        html_content = await resp.text()
        LOGGER.info(f'Fetched content for {url}')
    soup = BeautifulSoup(html_content, 'lxml')
    txt_cont = soup.select_one('#txtcont')
    if txt_cont is None:
        LOGGER.error(f'Failed to find content for {url}')
        return ''
    content = txt_cont.text.strip()
    await table.fill_content(url, content)
    LOGGER.info(f'Saved content for {url} to database: {content[:50]}...')
    return content


async def main():
    async with (
        ClientSession(headers=HEADERS) as session,
        ZenianTable() as table,
    ):
        # tasks = [
        #     fetch_search(session, table, i*10, '储氢材料')
        #     for i in range(0, 8+1)
        # ]
        # await asyncio.gather(*tasks)
        data = await table.load(SOURCE, CATG, SECTION)
        tasks = [
            fetch_content(session, table, datum['url'])
            for datum in data
        ]
        await asyncio.gather(*tasks)
        await table.export(SOURCE, CATG, SECTION)



if __name__ == '__main__':
    asyncio.run(main())
