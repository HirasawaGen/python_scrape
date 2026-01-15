import json
from pathlib import Path
import re

email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PATTERN_图 = re.compile(r'图\s*\d+')
PATTERN_表 = re.compile(r'表\s*\d+')

RESULTS_ROOT = Path(__file__).parent / 'results'

if __name__ == "__main__":
    json_file_names = {
        '锂电网_新闻报告_新闻_4823.json',
        '锂电网_行业研究_产业分析_768.json',
        '锂电网_材料研究_技术_203.json'
    }
    
    for json_file_name in json_file_names:
        json_file = RESULTS_ROOT / json_file_name
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for i in range(len(data)):
            content = data[i]['content']
            publish_time = data[i]['publish_time']
            if publish_time[:4] < '2010':
                print(f'id: {data[i]["id"]}, file: {json_file_name}, publish time too old')
            if len(content) <= 50:
                print(f'id: {data[i]["id"]}, file: {json_file_name}, content too short')
            emails = email_pattern.findall(content)
            if '原文链接' in content:
                print(f'id: {data[i]["id"]}, file: {json_file_name}, found original link')
            if len(emails):
                print(f'id: {data[i]["id"]}, file: {json_file_name}, found emails: {emails}')
            tu_n = PATTERN_图.findall(content)
            if len(tu_n):
                print(f'id: {data[i]["id"]}, file: {json_file_name}, found tu_n: {tu_n}')
            biao_n = PATTERN_表.findall(content)
            if len(biao_n):
                print(f'id: {data[i]["id"]}, file: {json_file_name}, found biao_n: {biao_n}')