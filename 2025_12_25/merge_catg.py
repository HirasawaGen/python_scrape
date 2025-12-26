from pathlib import Path
import json


CATG_ROOT = Path(__file__).parent / 'results' / 'catg'
results: dict[str, str] = {}

for i in range(1, 1366+1):
    with (CATG_ROOT / f'{i}.json').open(encoding='utf-8', mode='r') as f:
        data = json.load(f)
    for item in data:
        url = item['url']
        catg = item['catg']
        results[url] = catg

with (CATG_ROOT.parent / 'all_catg.json').open(encoding='utf-8', mode='w') as f:
    json.dump(results, f, ensure_ascii=False, indent=4)
