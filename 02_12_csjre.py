import asyncio
import re

from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from bs4 import BeautifulSoup
from loguru import logger as LOGGER

from database import ZenianData, ZenianTable


PHPSESSID = 'b5b54faee2e3c8463e14ebfe86c878bd'
LIMITER = AsyncLimiter(max_rate=1, time_period=1.5)  # 1 request per 1.5 seconds


''' demo request headers
GET /listinfo.php?t=news&id=8343 HTTP/1.1
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7
Accept-Encoding: gzip, deflate
Accept-Language: zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,zh-TW;q=0.5,ja;q=0.4
Cache-Control: max-age=0
Connection: keep-alive
Cookie: PHPSESSID=b5b54faee2e3c8463e14ebfe86c878bd
Host: csjre.cn
Upgrade-Insecure-Requests: 1
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0
'''

'''http://csjre.cn/robots.txt
User-agent: *
Disallow: /a/
Disallow: /admin/
Disallow: /cache/
Disallow: /common/
Disallow: /data/
Disallow: /doc/
Disallow: /install/
Disallow: /javascript/
Disallow: /style/
Disallow: /tpl/
Disallow: /static.php
'''

SECTIONS = {
    '政策法规': '资料荟萃-政策法规',
    '知识产权': '资料荟萃-知识产权',
    '行业标准': '资料荟萃-行业标准',
    '行业分析': '资料荟萃-行业分析',
    '行业期刊': '资料荟萃-行业期刊',
    '综合评述': '业界资讯-综合评述',
    '行业资讯': '业界资讯-行业资讯',
    '产业科技': '业界资讯-产业科技',
    '环保动态': '业界资讯-环保动态',
}


async def fetch(session: ClientSession, id_: str, t_ = 'news') -> ZenianData | None:
    url = f'http://csjre.cn/listinfo.php?t={t_}&id={id_}'
    async with (
        LIMITER,
        session.get(url) as resp,
    ):
        LOGGER.info(f'Fetching {id_}')
        html_content = await resp.text()
        LOGGER.info(f'Got html source for id {id_}')
    soup = BeautifulSoup(html_content, 'lxml')
    zhengwen = soup.select_one('div.zhengwen')
    if zhengwen is None:
        LOGGER.error(f'Failed to fetch content for id {id_}')
        return
    h3 = zhengwen.find('h3')
    if h3 is None:
        LOGGER.error(f'Failed to find section for id {id_}')
        return
    h3_text = h3.text.strip()
    if '提示信息' in h3_text:
        LOGGER.warning(f'content for id {id_} is VIP only.')
        return
    section = ''
    for key, value in SECTIONS.items():
        if key in h3_text:
            section = value
            break
    if not len(section):
        LOGGER.error(f'Failed to find section for id {id_}')
        return
    h1 = zhengwen.select_one('h1')
    if h1 is None:
        LOGGER.error(f'Failed to find title for id {id_}')
        return
    title = h1.text.strip()
    # 从zhengwen中剔除掉h1和h3，就是正文内容
    content = zhengwen.text.strip()
    content = content.replace(h3_text, '').replace(title, '').strip()
    content = re.sub(r'来源：.*?作者：.*?\n', '', content)
    if '稀土' not in content and '稀土' not in title:
        LOGGER.warning(f'content for id {id_} does not contain "稀土"')
        return
    LOGGER.info(f'Got content for id {id_}: {content[:100]}')
    ans: ZenianData = {
        'url': url,
        'title': title,
        'content': content,
        'section': section,
        'source': '长三角稀土网',
        'catg': '新闻公告',
        'publish_time': '2026-02-12 00:00:00',
    }
    async with ZenianTable() as table:
        await table.save([ans])
    LOGGER.info(f'Saved data for id {id_}')
    return ans


async def main():
    async with ZenianTable() as table:
        for section in SECTIONS.values():
            await table.export('长三角稀土网', '新闻公告', section)

    return

    async with (
        ClientSession(
            cookies={'PHPSESSID': PHPSESSID},
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,zh-TW;q=0.5,ja;q=0.4',
                'Accept-Encoding': 'gzip, deflate',
                'Cache-Control':'max-age=0',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Host': 'csjre.cn',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            }
        ) as session,
    ):
        LOGGER.info('All managers are ready')
        # if t is 'image', range is [1, 174]
        tasks_news = [
            fetch(session, str(id_), 'news')
            for id_ in range(239, 8343 + 1)
        ]
        tasks_image = [
            fetch(session, str(id_), 'image')
            for id_ in range(1, 174 + 1)
        ]
        LOGGER.info(f'Fetching {len(tasks_news)} pages')
        results = await asyncio.gather(*tasks_news, return_exceptions=False)
        results = [
            result
            for result in results
            if isinstance(result, dict)
        ]
        LOGGER.info(f'Got {len(results)} results of news')
        results_image = await asyncio.gather(*tasks_image, return_exceptions=False)
        results_image = [
            result
            for result in results_image
            if isinstance(result, dict)
        ]
        LOGGER.info(f'Got {len(results_image)} results of image')


if __name__ == '__main__':
    asyncio.run(main())
