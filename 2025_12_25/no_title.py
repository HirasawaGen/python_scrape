# 查询已被筛掉的文件
from pathlib import Path
import json


RESULTS_ROOT = Path(__file__).parent / 'results'

json_data_dict: dict[str, dict] = {}
jsonl_data_dict: dict[str, dict] = {}


json_file_names = {
    '锂电网_新闻报告_新闻_4828.json',
    '锂电网_行业研究_产业分析_770.json',
    '锂电网_材料研究_技术_204.json'
}

for jsonl_file in RESULTS_ROOT.glob('*.jsonl'):
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    for result in results:
        jsonl_data_dict[result['url']] = result
        
print(f'jsonl_data: {len(jsonl_data_dict)}')

for json_file_name in json_file_names:
    json_file = RESULTS_ROOT / json_file_name
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for item in data:
        if item['url'] in jsonl_data_dict:
            jsonl_data = jsonl_data_dict[item['url']]
            item['content'] = jsonl_data['content']
            item['title'] = jsonl_data['title']
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
