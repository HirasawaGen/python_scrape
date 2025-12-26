from pathlib import Path
import json
from collections import OrderedDict


START_ID = 30007418
ROOT = Path(__file__).parent
START_PAGE = 901
END_PAGE = 1366


def main():
    results = []
    id_ = START_ID
    for i in range(START_PAGE, END_PAGE+1):
        file_path = ROOT / 'results' / f'page_{i}.json'
        if not file_path.exists():
            continue
        with file_path.open('r', encoding='utf-8') as f:
            result = json.load(f)
        for res in result:
            flag = '锂' in res.get('title', '')
            if not flag:
                continue
            ordered_res = OrderedDict()
            ordered_res['id'] = id_
            ordered_res['title'] = res.get('title', '')
            ordered_res['publish_time'] = res.get('publish_time', '')
            ordered_res['source'] = res.get('source', '')
            ordered_res['url'] = res.get('url', '')
            ordered_res['content'] = res.get('content', '')
            ordered_res['catg'] = res.get('catg', '')
            results.append(ordered_res)
            id_ += 1
    with (ROOT / 'results' / f'锂电网_新闻报告_新闻{START_PAGE}~{END_PAGE}_{len(results)}.json').open('w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)


if __name__ == '__main__':
    main()
