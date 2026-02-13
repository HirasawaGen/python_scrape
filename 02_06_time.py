import asyncio
from datetime import datetime
from pathlib import Path
import json

import aiofiles
from aiosqlite import connect, Connection

from database import ZenianTable


async def set_publish_time(conn: Connection, json_file: Path):
    async with aiofiles.open(json_file, mode='r', encoding='utf-8') as f:
        data = json.loads(await f.read())
    for item in data:
        if not str(item.get('dateTimestamp', '')).isdigit():
            continue
        timestamp = int(item['dateTimestamp'])
        publish_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        url = f'https://cn.investing.com{item["link"]}'
        print(f'{item["link"]}\t{publish_time}')
        curr = await conn.execute('UPDATE zenian SET publish_time =? WHERE url =?', (publish_time, url))
        success = curr.rowcount == 1
        print('success' if success else 'failed')
        await conn.commit()


async def main():
    # async with connect('zenian.db') as conn:
    #     for json_file in Path().glob('*.json'):
    #         await set_publish_time(conn, json_file)
    async with ZenianTable() as table:
        await table.export('英为财情', min_length=50)

if __name__ == '__main__':
    asyncio.run(main())
