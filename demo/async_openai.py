from openai import AsyncOpenAI
import asyncio


BASE_URL = 'https://ark.cn-beijing.volces.com/api/v3'
API_KEY = '702fd554-5c0a-4426-a802-c84d88b18536'
MODEL = 'doubao-seed-1-6-flash-250828'


async def chat(client: AsyncOpenAI, text: str) -> str:
    try:
        # 调用 chat.completions.create 接口（OpenAI 标准异步调用方式）
        print(f"Calling model with text: {text}")
        response = await client.chat.completions.create(
            model=MODEL,  # 指定使用的模型
            messages=[    # 对话消息列表，符合 OpenAI 格式规范
                {"role": "user", "content": text}
            ],
            temperature=0.7,  # 生成温度，控制回复的随机性
            max_tokens=1024   # 最大生成令牌数
        )
        # 提取并返回模型的回复内容
        content = response.choices[0].message.content
        if content is None:
            return 'NONE CONTENT'
        return content.strip()
    except Exception as e:
        # 捕获异常并返回错误信息，避免单个任务失败导致整体崩溃
        return f"调用模型失败: {str(e)}"


async def main():
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    texts = [
        '你好，请问有什么可以帮助您？',
        'こんにちは！何かお役に立てることはありますか？',
        'Hello! Do you have any questions for me?',
    ]
    tasks = [chat(client, text) for text in texts]
    results = await asyncio.gather(*tasks)
    print(results)
    

if __name__ == '__main__':
    asyncio.run(main())
