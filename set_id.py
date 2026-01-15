from pathlib import Path
import json


START_ID = 30012774
FILE = '锂_975.json'


json_data: list[dict] = []
file = Path() / FILE


with file.open('r', encoding='utf-8') as f:
    json_data = json.load(f)
    
for i in range(len(json_data)):
    json_data[i]['id'] = str(START_ID + i)

print(f'next id: {i + START_ID + 1}')

with file.open('w', encoding='utf-8') as f:
    json.dump(json_data, f, ensure_ascii=False, indent=4)


