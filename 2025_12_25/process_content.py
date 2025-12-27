import re
import json
from pathlib import Path

RESULTS_ROOT = Path(__file__).parent / 'results'

def normalize_raw_newlines(text):
    split_text = text.split('\n')
    split_text = [t.strip() for t in split_text if t.strip()]
    return '\n'.join(split_text)

# 测试示例
if __name__ == "__main__":
    # # 模拟你的原始文本（包含连续的'\n'字符组合）
    # original_text = r'Hello\n\nworld\n\n\n\npython'  # 使用r前缀表示raw string，等价于'Hello\\n\\nworld\\n\\n\\n\\npython'
    # print("原始文本：", original_text)
    
    # # 处理文本
    # processed_text = normalize_raw_newlines(original_text)
    # print("处理后文本：", processed_text)
    json_file_names = {
        '锂电网_新闻报告_新闻_4828.json',
        '锂电网_行业研究_产业分析_770.json',
        '锂电网_材料研究_技术_204.json'
    }
    
    for json_file_name in json_file_names:
        json_file = RESULTS_ROOT / json_file_name
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for i in range(len(data)):
            data[i]['content'] = normalize_raw_newlines(data[i]['content'])
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)