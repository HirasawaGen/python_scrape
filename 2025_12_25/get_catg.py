import aiohttp
import asyncio
from pathlib import Path
import json
from asyncio import Semaphore
import aiofiles

from bs4 import BeautifulSoup

HTTP_SEM = Semaphore(0X08)  # Limit concurrent requests
FILE_SEM = Semaphore(0X40)  # Limit concurrent file writes
RESULTS_ROOT = Path(__file__).parent / 'results'


async def get_catg(session: aiohttp.ClientSession, page: int) -> list[dict[str, str]]:
    '''
    :returns: A dictionary containing the URL and the category name.
    '''
    mapping = {
        '新闻': '新闻公告',
        '技术': '材料研究',
        '分析': '行业研究',
    }
    link = f'http://www.li-b.cn/search.php?q=%E9%94%82&page={page}'
    async with HTTP_SEM:
        async with session.get(link, timeout=60000) as response:
            html_content = await response.text()
    print(f'Got html content from page {page}')
    soup = BeautifulSoup(html_content, 'lxml')
    divcate = soup.select_one('#divcate')
    if not divcate:
        return []
    div_post_multi = divcate.select('div.post-multi')
    results = []
    for div in div_post_multi:
        a_tag = div.select_one('h2 > a')
        span_tag = div.select_one('span')
        title = a_tag.text.strip()
        if not '锂' in title:
            continue
        if not a_tag or not span_tag:
            continue
        url = a_tag['href']
        span_tag_text = span_tag.text.strip()
        splited_span_inner_text = span_tag_text.split('|')
        splited_span_inner_text = [s.strip() for s in splited_span_inner_text]
        splited_span_inner_text = [s for s in splited_span_inner_text if s.startswith('文章分类')]
        if not splited_span_inner_text:
            continue
        catg = splited_span_inner_text[0]
        catg = catg.split('：')[-1].strip()
        if not catg in mapping:
            continue
        catg = mapping[catg]
        results.append({
            'url': url,
            'catg': catg,
        })
    print(f'Got {len(results)} categories from page {page}, try to write to file')
    async with FILE_SEM:
        async with aiofiles.open(RESULTS_ROOT / 'catg' / f'{page}.json', 'w', encoding='utf-8') as f:
            await f.write(json.dumps(results, ensure_ascii=False, indent=4))
    # with (RESULTS_ROOT / 'catg' / f'{page}.json').open('w', encoding='utf-8') as f:
    #     json.dump(results, f, ensure_ascii=False, indent=4)
    print(f'Wrote {len(results)} categories to file for page {page}')
    return results


async def main():
    
    # links = links[:10]
    range_ = []
    for i in range(1, 1366+1):
        if not (RESULTS_ROOT / 'catg' / f'{i}.json').exists():
            range_.append(i)
    if not len(range_):
        print('All categories have been downloaded.')
        return
    async with aiohttp.ClientSession() as session:
        tasks = [get_catg(session, i) for i in range_]
        catgs = await asyncio.gather(*tasks)
    # catgs = sum(catgs, [])  # flatten list of lists
    print(f'Got {len(catgs)} categories from {len(range_)} pages')
    # for catg, pages in zip(catgs, range_):
    #     with (RESULTS_ROOT / 'catg' / f'{pages}.json').open('w', encoding='utf-8') as f:
    #         json.dump(catg, f, ensure_ascii=False, indent=4)
    # print('All categories have been downloaded.')


if __name__ == '__main__':
    asyncio.run(main())
