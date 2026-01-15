import asyncio
from pathlib import Path
import json
from collections import OrderedDict
import re

from aiofiles import open

JSON_ROOT = Path() / '2026_1_5' / 'results'
START_ID = 30016568
SOURCE = '上海有色网'
CATG = '新闻公告'



async def read_json(file_path: Path) -> list[dict]:
    async with open(file_path, mode='r', encoding='utf-8') as f:
        data = await f.read()
    return json.loads(data)


def clean_content(content: str) -> str:
    content = content.strip()
    content = content.replace(' ', '')
    content = content.replace('\t', '')
    content = content.replace('\r', '\n')
    content = re.sub(r'\n{2,}', '\n', content)
    return content


async def merge_json(file_root: Path) -> list[dict]:
    if not file_root.is_dir():
        raise ValueError(f'{file_root} is not a directory')
    file_paths = list(file_root.glob('result_*.json'))
    tasks = [read_json(file_path) for file_path in file_paths]
    results_split: list[list[dict]] = await asyncio.gather(*tasks)
    results = []
    id_ = START_ID
    for res in sum(results_split, []):
        res2append = OrderedDict()
        content = clean_content(res.get('content', ''))
        if len(content) <= 50:
            continue
        if content.startswith('Regan奇'):
            continue
        res2append['id'] = str(id_)
        res2append['title'] = res['title']
        res2append['publish_time'] = res['publish_time']
        res2append['source'] = res.get('source', SOURCE)
        res2append['url'] = res['url']
        res2append['content'] = content
        res2append['catg'] = res.get('catg', CATG)
        results.append(res2append)
        id_ += 1
    with (Path() / 'merged.json').open(mode='w', encoding='utf-8') as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    print(f'lenth of results: {len(results)}')
    print(f'next id: {id_}')
    return results

    
if __name__ == '__main__':
    asyncio.run(merge_json(JSON_ROOT))