import asyncio
from typing import Callable, Awaitable
from functools import wraps
import json
from pathlib import Path
from time import time_ns
from collections import OrderedDict
import re

import aiohttp
import aiofiles
from bs4 import BeautifulSoup


ROOT = Path(__file__).parent


def output_json(file_path_template: str):
    '''
    将函数的运行结果保存为json
    
    :param file_path_template: 文件路径模板，使用占位符表示参数
    :return: 装饰器
    '''
    def deco[**P](func: Callable[P, Awaitable[list | dict]]) -> Callable[P, Awaitable[list | dict]]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            root = Path(__file__).parent
            file_path = root / (file_path_template % args)
            data = await func(*args, **kwargs)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return data
        return wrapper
    return deco


def delay(seconds: int, delay_count: float = 1.0):
    '''
    让某协程每n次执行之间必须sleep一段时间
    
    :param seconds: 等待时间
    :param delay_count: 每n次执行之间必须sleep，delay_count就是那个n
    '''
    def deco[**P, R](func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        nano_seconds = seconds * 1000000000
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_execute_time: int | None = getattr(func, '__last_execute_time__', None)
            execute_count: int = getattr(func, '__execute_count__', 0)
            now = time_ns()
            wait_time = 0.0
            if execute_count % delay_count == 0 and last_execute_time is not None:
                wait_time = (nano_seconds - (now - last_execute_time)) / 1000000000
                await asyncio.sleep(wait_time)
            res = await func(*args, **kwargs)
            setattr(func, '__last_execute_time__', time_ns())
            setattr(func, '__execute_count__', execute_count + 1)
            return res
        return wrapper
    return deco


@output_json('results/page_%d.json')
@delay(10, 5)
async def fetch_page(page: int) -> list[dict]:
    '''
    访问某一页并将结果保存到json
    
    :param page: 页码
    :return: 包含链接的列表
    '''
    cookie = (ROOT / 'cookie.txt').read_text()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Cookie': cookie,
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        # resp = await session.get(f'https://www.cnfeol.com/xitu/a-{page}.aspx')
        # resp = await session.get(f'https://www.cnfeol.com/xitu_ab_14/all-{page}.aspx')
        # resp = await session.get(f'https://www.cnfeol.com/xituhuahewu_ab_3/all-{page}.aspx')
        resp = await session.get(f'https://www.cnfeol.com/xituhuahewu_ab_17/all-{page}.aspx')
        html_content = await resp.text()
    soup = BeautifulSoup(html_content, 'html.parser')
    data_list_box = soup.select_one('div.dataListBox')
    if data_list_box is None:
        return []
    a_tags = data_list_box.select('a')
    return [{'url': str(a_tag.get('href', ''))} for a_tag in a_tags]


@delay(30)
async def fetch_content(page: int, cookie: str = '') -> None:
    '''
    读取json结果，并fetch其中的url

    将html保存到pages文件夹

    :param page: 页码
    :return: 获取失败的
    '''
    json_path = ROOT / 'results' / f'page_{page}.json'
    
    if not json_path.exists():
        raise FileNotFoundError('file not found')
    
    with json_path.open('r', encoding='utf-8') as f:
        json_content = json.load(f)
    
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0'
        )
    }
    if len(cookie):
        headers = {'Cookie': cookie}
    
    for i, item in enumerate(json_content):
        url = item['url']
        if i % 5 == 0 and i > 0:
            print('sleep...')
            await asyncio.sleep(30)
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as resp:
                html_content = await resp.text(encoding='utf-8')
            if '人机验证' in html_content:
                print(f'fetch content_{i} at page_{page} failed.')
                continue
            html_page_root = ROOT / 'pages' / f'page_{page}'
            if not html_page_root.exists():
                html_page_root.mkdir(parents=True)
            html_path = html_page_root / f'content_{i}.html'
            html_path.write_text(html_content, encoding='utf-8')
            print(f'fetched content_{i} at page_{page}')


async def _load_file(path: Path) -> str:
    async with aiofiles.open(path, 'r', encoding='utf-8') as f:
        content = await f.read()
    return content


async def load_content(page: int) -> list[str]:
    '''
    load html content from pages folder
    '''
    content_root = ROOT / 'pages' / f'page_{page}'
    tasks: list[Awaitable[str]] = [
        _load_file(file)
        for file in sorted(
            content_root.glob('*.html'),
            key=lambda x: int(x.stem.split('_')[1])
        )
    ]
    contents = await asyncio.gather(*tasks)
    return contents


@output_json('results/page_%d.json')
async def load_data(page: int) -> list[dict]:
    '''
    读取json文件和保存起来的html文件
    use beautiful to extract some data from html
    and resave the json file.
    
    origin json:
    ```json
    [
        {'url': 'www.xxx.com/art-1.html'},
        {'url': 'www.xxx.com/art-2.html'},
        ...
    ]
    ```
    
    content after use this func:
    ```json
    [
        {
            'url': 'xxx',
            'title': 'xxx',
            ...
        },
        {...},
        ...
    ]
    ```
    '''
    json_file = ROOT / 'results' / f'page_{page}.json'
    with json_file.open('r', encoding='utf-8') as f:
        data = json.load(f)
    # html_contents = await load_content(page)
    for i in range(len(data)):
        html_file = ROOT / 'pages' / f'page_{page}' / f'content_{i}.html'
        with html_file.open('r', encoding='utf-8') as f:
            html_content = f.read()
        if '当前信息仅供正式会员浏览' in html_content:
            print(f'page_{page} content_{i} is VIP only.')
            data[i]['content'] = 'VIP only'
            continue
        soup = BeautifulSoup(html_content, 'lxml')
        article_box = soup.select_one('div.articleBox')
        content_soup = article_box.select_one('#contentdetail_info_detail')
        p_tag_content: list[str] = []
        for p_tag in content_soup.find_all('p'):
            p_tag_content.append(p_tag.get_text(strip=True))
        content = '\n'.join(p_tag_content)
        title = article_box.select_one('h3').get_text(strip=True)
        article_subtitle = article_box.select_one('div.prodCategory > div:nth-child(1) > div.articleSubTitle')
        article_subtitle_span_tags = article_subtitle.select('span')
        publish_time = article_subtitle_span_tags[0].get_text(strip=True)
        source = article_subtitle_span_tags[1].get_text(strip=True)
        data[i]['title'] = title
        data[i]['content'] = content
        data[i]['publish_time'] = publish_time
        data[i]['source'] = source
    return data


def regex_check(page: int):
    json_file = ROOT / 'results' / f'page_{page}.json'
    with json_file.open('r', encoding='utf-8') as f:
        data = json.load(f)
    # 2024年07月25日
    publish_time_pattern = re.compile(r'^\d{4}年\d{2}月\d{2}日$')
    # 来源:xxx
    for i in range(len(data)):
        try:
            publish_time = data[i]['publish_time']
            source = data[i]['source']
        except KeyError:
            print(f'page_{page} content_{i} is missing publish_time or source.')
            continue
        if not publish_time_pattern.match(publish_time):
            print(f'page_{page} content_{i} publish_time is invalid: {publish_time}')
        if '来源:' not in source:
            print(f'page_{page} content_{i} source is invalid: {source}')


def format_data(page: int):
    json_file = ROOT / 'results' / f'page_{page}.json'
    with json_file.open('r', encoding='utf-8') as f:
        data = json.load(f)
    for i in range(len(data)):
        try:
            publish_time = data[i]['publish_time']
            source = data[i]['source']
        except KeyError:
            print(f'page_{page} content_{i} is missing publish_time or source.')
            continue
        publish_time = publish_time.replace('年', '-').replace('月', '-').replace('日', '')
        publish_time += ' 00:00:00'
        data[i]['publish_time'] = publish_time
        data[i]['source'] = source.split('来源:')[1]
    with json_file.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    return data


def merge_data(start_id: int) -> list[OrderedDict]:
    all_data = []
    id_ = start_id
    for i in range(1, 1+1):
        json_file = ROOT / 'results' / f'page_{i}.json'
        with json_file.open('r', encoding='utf-8') as f:
            data = json.load(f)
        for j in range(len(data)):
            if len(data[j]['content']) <= 50:
                continue
            if data[j]['publish_time'][:4] < '2010':
                continue
            ordered_data = OrderedDict()
            ordered_data['id'] = f'{id_:08d}'
            ordered_data['title'] = data[j]['title']
            ordered_data['publish_time'] = data[j]['publish_time'] + ' 00:00:00'
            ordered_data['source'] = data[j]['source']
            ordered_data['url'] = data[j]['url']
            ordered_data['content'] = data[j]['content']
            ordered_data['catg'] = '行业研究'
            all_data.append(ordered_data)
            id_ += 1
    with (ROOT / 'all_data.json').open('w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)
    return all_data


async def main():
    cookies = (ROOT / 'cookie.txt').read_text()
    for i in range(1, 1+1):
        # data = await fetch_page(i)
        # print(f'page_{i} fetched, {len(data)} links.')
        # await fetch_content(i, cookies)
        # await load_data(i)
        # format_data(i)
        ...
        
    merge_data(30002580)

if __name__ == '__main__':
    asyncio.run(main())
    
    
    
    