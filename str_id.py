'''
Some json files I set `id` as int type,
which is wrong.
This script will convert `id` to string type.
'''
import json
from pathlib import Path


FILES = [
    '中国有色金属加工工业协会_新闻公告_会员动态 154条.json',
    '中国有色金属加工工业协会_新闻公告_协会动态 622条.json',
]


def convert_id_to_str(filepath: Path):
    if not filepath.exists():
        print(f'{str(filepath)} not found.')
    file_stem = filepath.stem
    filepath_copy = filepath.parent / f'{file_stem}_copy.json'
    json_data: list[dict]
    with filepath.open('r', encoding='utf-8') as f:
        json_data = json.load(f)
    with filepath_copy.open('w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
    for i in range(len(json_data)):
        json_data[i]['id'] = str(json_data[i]['id'])
    with filepath.open('w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
    print(f'{file_stem} converted successfully.')


if __name__ == '__main__':
    for file in FILES:
        filepath = Path(file)
        convert_id_to_str(filepath)


