from pathlib import Path
import json


FILES = [
    '客家新闻网_新闻公告_有色金属_995.json',
    '客家新闻网_新闻公告_钨_1959.json',
    '客家新闻网_新闻公告_锂_1347.json',
]


json_data_有色金属: list[dict] = []
json_data_钨: list[dict] = []
json_data_锂: list[dict] = []


all_data: list[dict] = []
all_url: set[str] = set()

for file in FILES:
    path = Path() / file
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for datum in data:
        url = datum['url']
        if url in all_url:
            continue
        all_url.add(url)
        all_data.append(datum)

print(len(all_data))


for datum in all_data:
    content = datum['content']
    if '有色金属' in content:
        json_data_有色金属.append(datum)
    elif '钨' in content and '锂' in content:
        json_data_有色金属.append(datum)
    elif '锂' in content:
        json_data_锂.append(datum)
    elif '钨' in content:
        json_data_钨.append(datum)


for i, json_data in enumerate((json_data_有色金属, json_data_钨, json_data_锂)):
    with open(f'json_data_{i}.json', 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)


print(len(json_data_有色金属))
print(len(json_data_钨))
print(len(json_data_锂))






