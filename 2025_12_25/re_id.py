from pathlib import Path
import json


RESULTS_ROOT = Path(__file__).parent /'results'


def re_id(json_path: Path, id_: int):
    with open(json_path, 'r', encoding='utf-8') as f:
        results = json.load(f)
    for i in range(len(results)):
        results[i]['id'] = id_ + i
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
        
        
if __name__ == '__main__':
    json_path = RESULTS_ROOT / '行业研究.json'
    id_ = 30008230
    re_id(json_path, id_)
    
