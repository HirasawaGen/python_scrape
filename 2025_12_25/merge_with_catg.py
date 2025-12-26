from pathlib import Path
import json


RESULTS_ROOT = Path(__file__).parent / "results"


with (RESULTS_ROOT / 'all_catg.json').open('r', encoding='utf-8') as f:
    all_catg = json.load(f)


all_results = []
results_材料研究 = []
results_行业研究 = []
results_新闻公告 = []

for result_file in RESULTS_ROOT.glob("锂电网_*.json"):
    with result_file.open('r', encoding='utf-8') as f:
        results = json.load(f)
    for res in results:
        url = res['url']
        catg = all_catg.get(url, None)
        if catg is None:
            continue
        res['catg'] = catg
        if catg == '材料研究':
            results_材料研究.append(res)
        elif catg == '行业研究':
            results_行业研究.append(res)
        elif catg == '新闻公告':
            results_新闻公告.append(res)
        
# with (RESULTS_ROOT / 'all_results.json').open('w', encoding='utf-8') as f:
    # json.dump(all_results, f, ensure_ascii=False, indent=4)

with (RESULTS_ROOT / '材料研究.json').open('w', encoding='utf-8') as f:
    json.dump(results_材料研究, f, ensure_ascii=False, indent=4)

with (RESULTS_ROOT / '行业研究.json').open('w', encoding='utf-8') as f:
    json.dump(results_行业研究, f, ensure_ascii=False, indent=4)

with (RESULTS_ROOT / '新闻公告.json').open('w', encoding='utf-8') as f:
    json.dump(results_新闻公告, f, ensure_ascii=False, indent=4)
