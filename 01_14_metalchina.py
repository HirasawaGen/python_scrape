import asyncio
import random
from asyncio import Lock, Queue, Semaphore
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
import aiohttp
from aiohttp import ClientSession
from playwright.async_api import async_playwright
from playwright.async_api import Page, Browser

from database import ZenianData, ZenianTable

SEM = Semaphore(5)


async def fetch_pages(session: ClientSession, page_idx: int, keyword: str):
    url = "https://www.metalchina.com/front/api/content/getContents"
    
    payload = {
        "page": page_idx,
        "limit": 8,
        "columnId": "f7538c04870647fda71ade4cd1deb58a",
        "channelId": KEYWORD_MAP[keyword],
    }
    
    async with session.post(url, json=payload) as response:
        if response.status != 200:
            print(f"请求失败: {response.status}")
            raise Exception(f"请求失败: {response.status}")

        try:
            result = await response.json()
            ans: list[ZenianData] = []
            data: list[dict] = result['data']['data']
            for datum in data:
                title = datum.get('title', '滚木标题')
                if not keyword in title:
                    continue
                id_ = datum.get('id')
                url = f'https://www.metalchina.com/contents/detail?id={id_}'
                publish_time = datum.get('publishTime', '2022-01-14 00:00:00')
                source = '中国金属网'
                catg = '新闻公告'
                section = keyword
                ans.append({
                    'title': title,
                    'publish_time': publish_time,
                    'source': source,
                    'url': url,
                    'catg': catg,
                    'section': section,
                })
            async with ZenianTable() as table:
                await table.save(ans)
            print(f'fetched {len(ans)} data from page {page_idx} of keyword "{keyword}"')
            return ans
        except Exception as e:
            print(f"JSON解析失败: {e}")
            text = await response.text()
            print(f"响应文本: {text}")


# async def fill_content(page_queue: Queue[Page], url: str):
#     page = await page_queue.get()
#     print(f'fetching content of {url}.')
#     await page.goto(url, wait_until='networkidle', timeout=1000000)
#     await asyncio.sleep(random.uniform(1.5, 3.5))
#     html_text = await page.content()
#     await page_queue.put(page)
#     print(f'fetching content of {url} done.')
#     if '登录后查看文章内容' in html_text:
#         content = '要会员'
#     else:
#         soup = BeautifulSoup(html_text, 'lxml')
#         rich_text = soup.find('div', class_='rich-div')
#         if rich_text is None:
#             print(f'content of {url} is empty.')
#             return
#         content = rich_text.get_text()
#         if '免责声明' in content:
#             content = content[:content.index('免责声明')]
#     async with ZenianTable() as table:
#         await table.fill_content(url, content)
#     print(f'content: {content[:20]}...')

async def fill_content(session: ClientSession, url: str):
    param_id = extract_param_id(url)
    if not len(param_id):
        return
    api_url = f'https://www.metalchina.com/front/api/content/detail/{param_id}?flag=1'
    await asyncio.sleep(random.uniform(2.5, 4.5))
    async with SEM:
        print(f'feching content of {url}.')
        async with session.get(api_url) as resp:
            if resp.status!= 200:
                print(f'BadRequest: {resp.status}')
                return
            data = await resp.json()
    try:
        data = data['data']['data']
    except KeyError:
        print('KeyError')
        return
    soup = BeautifulSoup(data['contentText'], 'lxml')
    content = soup.get_text()
    content = content.replace('\xa0', '')
    content = content.replace('\u3000', '')
    if '免责声明' in content:
        content = content[:content.index('免责声明')]
    async with ZenianTable() as table:
        await table.fill_content(url, content)
    print(f'content: {content[:20]}...')
    

async def fetch_article(session: ClientSession, keyword: str):
    async with ZenianTable() as table:
        data = await table.load(source='中国金属网', section=keyword)
    urls = [
        datum['url']
        for datum in data
        if datum.get('content', '') == 'None'
    ]
    tasks = [
        fill_content(session, url)
        for url in urls
    ]
    print(f'total data count of keyword "{keyword}": {len(tasks)}')
    await asyncio.gather(*tasks)


def extract_param_id(url: str) -> str:
    parsed_url = urlparse(url)
    query_dict = parse_qs(parsed_url.query)
    return query_dict.get('id', [''])[0]


KEYWORD_MAP = {
    '稀土': '2dc2514f2fe44397997b3202008f5a2a',
    '铜': '6bab7929c7aa457690ffce0eedca4b97',
    '铝': 'da85c9e3916b4a6b805f9d6a724eefad',
    '锂': '44aef0f33da04b0295b87842ee1ecb70'
}

INTERVAL = {
    '稀土': (785, 784),  # 
    '铜': (367, 300),  # 
    '铝': (1001, 1000),  # 
    '锂': (501, 500),  # 
}

async def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,zh-TW;q=0.5,ja;q=0.4",
        "Origin": "https://www.metalchina.com",
        "Referer": "https://www.metalchina.com/industry?id=4f3c4a0378aa45169a680e02a9a22d5d&name=%E8%A1%8C%E4%B8%9A%E8%B5%84%E8%AE%AF",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "sec-ch-ua": '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "token": ""
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        # for keyword in KEYWORD_MAP:
        #     start_page, max_page = INTERVAL[keyword]
        #     for i in range(start_page, max_page + 1):
        #         data = await fetch_pages(session, i, keyword)
        #         if not len(data):
        #             continue
        #         last_publish_time = data[-1]['publish_time']
        #         year = last_publish_time[:4]
        #         await asyncio.sleep(random.uniform(1.5, 3.5))
        #         thresh_year = '2021'
        #         if year < thresh_year:
        #             print(f'读取第{i}页数据结束，数据已到{thresh_year}年以前，退出循环')
        #             break
        for keyword in ('铝', '锂', '铜', '稀土'):
            await fetch_article(session, keyword)
        
        async with ZenianTable() as table:
            await table.process_all_content()
            for keyword in KEYWORD_MAP:
                await table.export('中国金属网', '新闻公告', keyword)
                
        

if __name__ == '__main__':
    asyncio.run(main())
