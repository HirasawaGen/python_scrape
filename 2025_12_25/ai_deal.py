import json
from pathlib import Path
import re
import winsound
from asyncio import Semaphore, Lock, Event, gather, run, sleep, create_task
from openai import AsyncOpenAI


RESULTS_ROOT = Path(__file__).parent / "results"
BASE_URL = 'https://ark.cn-beijing.volces.com/api/v3'
API_KEY = '702fd554-5c0a-4426-a802-c84d88b18536'
MODEL = 'doubao-seed-1-6-flash-250828'

USER_LOCK = Lock()  # 与用户交互的semaphore
FILE_LOCK = Lock()  # 与文件读写的semaphore
API_SEM = Semaphore(10)  # 访问api的最大并行数

PATTERN_图 = re.compile(r'图\s*\d+')
PATTERN_表 = re.compile(r'表\s*\d+')
# JSON_FILE = RESULTS_ROOT / '锂电网_材料研究_技术_203.json'
# JSON_FILE = RESULTS_ROOT / '锂电网_行业研究_产业分析_768.json'
JSON_FILE = RESULTS_ROOT / '锂电网_新闻报告_新闻_4823.json'
OUTPUT_FILE = RESULTS_ROOT / f'{JSON_FILE.stem}_processed.json'
BEEP = False

# PROMPT_TEMPLATE = """
# 请严格按照以下规则处理文章内容，只执行删除操作，其他内容保持原样：
# 1. 核心任务：删除所有与图表相关的引用标识，包括但不限于：
#    - "图1"、"图 2"、"(图4)"、"见图1"、"如图3所示"等所有包含"图+数字"的组合
#    - "表1"、"表 2"、"(表4)"、"见表1"、"如表3所示"等所有包含"表+数字"的组合
# 2. 操作规则：
#    - 仅删除上述图表引用标识本身，不要删除标识前后的任何文字（包括标点符号）
#    - 不要修改、增删任何其他内容，保持原文的格式、标点、换行、大小写完全不变
#    - 不要添加任何额外解释或说明，只输出处理后的纯文本内容
# 3. 错误禁止：
#    - 禁止删除非图表引用的文字
#    - 禁止修改原文的数值、公式、专业术语
#    - 禁止调整原文的段落结构和换行格式

# 例如：
# 原文：python的内存空间分为堆内存和栈内存，堆内存用于存储运行时数据。（见图1）
# 处理后：python的内存空间分为堆内存和栈内存，堆内存用于存储运行时数据。

# 原文：图6为电池组中单节电池电压检测仿真结果，可见采用过流放电支路均充的办法，该电路可正常工作。
# 处理后：电池组中单节电池电压检测仿真结果，可见采用过流放电支路均充的办法，该电路可正常工作。

# 文章内容：
# """

PROMPT_TEMPLATE = """
请严格按照以下规则处理文章内容，仅执行删除操作，其他内容保持原样：
1. 需要删除的内容：
   - 所有邮箱地址（包含@符号的字符串）
   - 所有电话号码、传真号码（如138xxxx1234、010-xxxx8888、+86xxxx等）
   - 文末的记者、作者、编辑的姓名（如“记者：张三”、“作者李四”、“编辑：王五”）
2. 操作规则：
   - 仅删除上述目标内容本身，不删除前后的任何文字、标点符号
   - 保持原文的格式、换行、标点、大小写完全不变
   - 不要添加任何额外解释，只输出处理后的纯文本内容
3. 错误禁止：
   - 禁止删除非目标内容的文字
   - 禁止修改原文的数值、公式、专业术语
   - 禁止调整原文的段落结构和换行格式

文章内容：
"""

global_json_data: list[dict] = []

async def beep(stop_event: Event):
    while not stop_event.is_set():
        winsound.Beep(2500, 500)
        await sleep(0.5)


async def process_line(ai_client: AsyncOpenAI, line: str) -> str:
    # if not (len(PATTERN_图.findall(line)) or len(PATTERN_表.findall(line))):
    #     return line
    prompt = PROMPT_TEMPLATE + line
    async with API_SEM:
        print('Calling API...')
        response = await ai_client.chat.completions.create(
            model=MODEL,  # 指定使用的模型
            messages = [    # 对话消息列表，符合 OpenAI 格式规范
                {"role": "system", "content": "你是一个专业的文本处理助手，擅长清理和优化文本内容。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # 生成温度，控制回复的随机性
            max_tokens=4096   # 最大生成令牌数
        )
        # 提取并返回模型的回复内容
    result = response.choices[0].message.content
    if result is None:
        print("模型生成的回复为空，请检查输入内容是否正确。")
        return line
    result = result.strip()
    if result == line.strip():
        return line
    async with USER_LOCK:
        print('-----------')
        print(f'原文内容：\n{line}')
        print('-----------')
        print(f"AI 生成的回复：\n{result}")
        print('-----------')
        winsound.Beep(2500, 1000)
        user_input = input('是否接受该修改？(y/n) ：')
        if user_input.lower() == 'y':
            return result
        return line


async def process_content(ai_client: AsyncOpenAI, index: int) -> None:
    global global_json_data
    content = global_json_data[index]['content']
    lines = content.splitlines()
    results = await gather(*[
        process_line(ai_client, line)
        for line in lines
    ])
    new_content = '\n'.join(results)
    if new_content == content:
        print(f'第 {index+1} 篇文章无需修改。')
        return
    content = new_content
    async with FILE_LOCK:
        print(f'正在写入第 {index+1} 篇文章...')
        global_json_data[index]['content'] = content
        with OUTPUT_FILE.open('w', encoding='utf-8') as f:
            json.dump(global_json_data, f, ensure_ascii=False, indent=4)
        print(f'第 {index+1} 篇文章处理完成。')


async def main():
    ai_client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL) 
    global global_json_data
    with JSON_FILE.open('r', encoding='utf-8') as f:
        global_json_data = json.load(f)
    await gather(*[
        process_content(ai_client, i)
        for i in range(647, len(global_json_data))
    ])
    # for i, item in enumerate(json_data):
    #     item['content'] = processed_content[i]
    # with OUTPUT_FILE.open('w', encoding='utf-8') as f:
    #     json.dump(json_data, f, ensure_ascii=False, indent=4)
        
    
    
if __name__ == '__main__':
    run(main())
    

    


