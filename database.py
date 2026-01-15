from typing import TypedDict, Required, Self, TypeGuard, overload
from collections import OrderedDict
from pathlib import Path
import sqlite3
import json
import re
from urllib.parse import urlparse
import asyncio

import aiosqlite
from aiosqlite import Connection, Cursor
import aiofiles


# use TypedDict rather than BaseModel to avoid extra dependency
# and you don't need to import ZenianData in other files


class ZenianData(TypedDict, total=False):
    id: Required[str | int]
    title: str
    publish_time: str
    source: str
    url: Required[str]
    content: str
    catg: str
    section: str


def valid_data(data: ZenianData) -> TypeGuard[ZenianData]:
    '''
    automatically check if data is valid
    '''
    if not isinstance(data, dict):
        return False
    if 'id' in data:
        data['id'] = str(data['id'])
    if 'url' not in data:
        print(f'no url found in data')
        return False
    url = data['url']
    if not isinstance(url, str):
        return False
    parsed_url = urlparse(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        print(f'invalid url: {url}')
        return False
    if 'content' in data:
        content = data['content']
        if not isinstance(content, str):
            return False
        content = content.strip()
        content = content.replace(' ', '')
        content = content.replace('\t', '')
        content = content.replace('\r', '\n')
        content = re.sub(r'\n{2,}', '\n', content)
        data['content'] = content
    if 'publish_time' in data:
        publish_time = data['publish_time']
        if not isinstance(publish_time, str):
            return False
        if len(publish_time) == 16:
            publish_time = publish_time + ':00'
        pattern = r'''
            ^\d{4}-                                 # 年份
            (0[1-9]|1[0-2])-                       # 月份：01-12
            (0[1-9]|[12]\d|3[01])\s                # 日期：01-31
            ([01]\d|2[0-3]):                        # 小时：00-23
            ([0-5]\d):                             # 分钟：00-59
            ([0-5]\d)$                             # 秒钟：00-59
        '''
        regex = re.compile(pattern, re.VERBOSE)
        if not regex.match(publish_time):
            print(f'invalid publish_time: {publish_time}')
            return False
    catg = data.get('catg', '')
    if not isinstance(catg, str):
        print(f'invalid catg: {catg}')
        return False
    section = data.get('section', '')
    if not isinstance(section, str):
        print(f'invalid section: {section}')
        return False
    title = data.get('title', '')
    if not isinstance(title, str):
        print(f'invalid title: {title}')
        return False
    return True


def process_content(content: str) -> str:
    content = content.strip()
    content = content.replace(' ', '')
    content = content.replace('\t', '')
    content = content.replace('\r', '\n')
    content = re.sub(r'\n{2,}', '\n', content)
    return content
    


class ZenianTable:
    def __init__(self, db_path: str = 'zenian.db', table_name: str = 'zenian') -> None:
        self._db_path = db_path
        self._name = table_name
        self._sync_conn: sqlite3.Connection | None = sqlite3.connect(self._db_path)
        self._sync_conn.execute(f"""--sql
        CREATE TABLE IF NOT EXISTS {self._name} (
            id INTEGER PRIMARY KEY,
            title TEXT,
            publish_time DATETIME,
            source TEXT,
            url TEXT UNIQUE NOT NULL,
            content TEXT,
            catg TEXT,
            section TEXT
        )""")
        self._sync_conn.commit()
        self._sync_conn.close()
        self._sync_conn = None
        self._conn: Connection | None
        self._total_changed = 0
        
    async def __aenter__(self) -> Self:
        self._conn = await aiosqlite.connect(self._db_path)
        self._total_changed = 0
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self._conn.rollback()
        if self._total_changed > 0:
            await self._conn.commit()
        await self._conn.close()
        if self._sync_conn is not None:
            self._sync_conn.close()
        self._conn = None
        self._sync_conn = None
        self._total_changed = 0
    
    async def import_(
        self,
        data_path: Path | str,
        section: str,
        force: bool = False,
        source: str = '',
        catg: str = '',
    ) -> int:
        '''
        import a json file to datatable
        :param data: path to json file you want to import to datatable
        :param force: if True, replace existing data with new data, otherwise ignore existing data
        :return: number of modified rows
        '''
        # TODO:
        async with aiofiles.open(data_path, 'r', encoding='utf-8') as f:
            data = json.loads(await f.read())
        for i in range(len(data)):
            if not 'source' in data[i]:
                data[i]['source'] = source
            if not 'catg' in data[i]:
                data[i]['catg'] = catg
            data[i]['section'] = section
        return await self.save(data, force)
    
    async def save(self, data: list[ZenianData], strict: bool = False) -> int:
        '''
        :param data: list of ZenianData
        :param force: if True, replace existing data with new data, otherwise ignore existing data
        :return: number of modified rows
        '''
        sql = f"""--sql
        INSERT OR {'REPLACE' if strict else 'IGNORE'} INTO {self._name} 
        (title, publish_time, source, url, content, catg, section)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        modify_count = 0
        
        for datum in data:
            if not valid_data(datum):
                if strict:
                    raise ValueError(f'Invalid data: url {datum["url"]}')
                continue
            url = datum['url']
            url_select_sql = f"""--sql
            SELECT id FROM {self._name} WHERE url = ?
            """
            cursor = await self._conn.execute(url_select_sql, (url,))
            row = await cursor.fetchone()
            if row is not None:
                continue
            params = (
                datum.get('title'),
                datum.get('publish_time'),
                datum.get('source'),
                url,  # url 是 Required，无值时抛 KeyError 符合预期
                datum.get('content'),
                datum.get('catg'),
                datum.get('section')
            )
            # 修复 async with 用法错误
            cursor = await self._conn.execute(sql, params)
            await self._conn.commit()
            row_count = cursor.rowcount
            if row_count > 0:
                modify_count += row_count
                self._total_changed += row_count
        return modify_count

    async def fill_content(self, url: str, content: str):
        '''
        :param url: url of zenian data
        :param content: content of zenian data
        '''
        content = process_content(content)
        sql = f"""--sql
        UPDATE {self._name} SET content = ? WHERE url = ?
        """
        cursor = await self._conn.execute(sql, (content, url))
        await self._conn.commit()
        row_count = cursor.rowcount
        if row_count > 0:
            self._total_changed += 1
        
        
    async def load(self, source: str, catg: str = '', section: str = '') -> list[ZenianData]:
        '''
        :param source: source of zenian data
        :param catg: category of zenian data
        :param section: section of zenian data
        :return: list of ZenianData
        '''
        # TODO:
        conditions = ["source = ?"]
        params = [source]
        if len(catg):
            conditions.append("catg = ?")
            params.append(catg)
        if len(section):
            conditions.append("section = ?")
            params.append(section)
        sql = f"""--sql
        SELECT id, title, publish_time, source, url, content, catg, section
        FROM {self._name}
        WHERE {' AND '.join(conditions)}
        """
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        result = []
        columns = ['id', 'title', 'publish_time', 'source', 'url', 'content', 'catg']
        for row in rows:
            datum = OrderedDict()
            for i, col in enumerate(columns):
                if col is None:
                    continue
                datum[col] = str(row[i])
            result.append(datum)
        return result
        

    async def export(self, source: str, catg: str = '', section: str = '', min_length: int = -1) -> Path:
        '''
        :param source: source of zenian data
        :param catg: category of zenian data
        :param section: section of zenian data
        :return: json file path of exported data
        '''
        file_name = source
        if len(catg):
            file_name += f'_{catg}'
        if len(section):
            file_name += f'_{section}'
        data = await self.load(source, catg, section)
        if min_length > 0:
            data = [datum for datum in data if len(datum.get('content', '')) > min_length]
        file_name += f'_{len(data)}.json'
        file_path = Path(file_name)
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=4))
        return file_path
    
    async def process_all_content(self) -> None:
        '''
        process all content in table
        '''
        sql = f"""--sql
        SELECT id, content FROM {self._name}
        """
        cursor = await self._conn.execute(sql)
        rows = await cursor.fetchall()
        for row in rows:
            id_ = row[0]
            content = row[1]
            if content is None:
                continue
            content = process_content(content)
            update_sql = f"""--sql
            UPDATE {self._name} SET content = ? WHERE id = ?
            """
            await self._conn.execute(update_sql, (content, id_))
            self._total_changed += 1
            await self._conn.commit()
    
    @overload
    def __getitem__(self, key: int | str) -> ZenianData: pass
    
    @overload
    def __getitem__(self, key: slice) -> dict[int, ZenianData]: pass
    
    def __getitem__(self, key: int | str | slice) -> ZenianData | dict[int, ZenianData]:
        '''
        :param key: url or id
        :return: ZenianData or dict[int, ZenianData]
        '''
        id_: str | None = None
        url: str | None = None
        if isinstance(key, int):
            id_ = str(key)
        else:
            if key.isdigit():
                id_ = key
            else:
                url = key
        if id_ is None and url is None:
            raise KeyError(key)
        if id_ is not None:
            condition = f'id={id_}'
        else:
            condition = f'url={url}'
        sql = f"""--sql
        SELECT id, title, publish_time, source, url, content, catg, section
        FROM {self._name}
        WHERE {condition}
        """
        if self._sync_conn is None:
            self._sync_conn = sqlite3.connect(self._db_path)
        cursor = self._sync_conn.execute(sql)
        row = cursor.fetchone()
        if row is None:
            raise KeyError(key)
        if self._conn is None:
            self._sync_conn.close()
            self._sync_conn = None
        return {
            'id': row[0],
            'title': row[1],
            'publish_time': row[2],
            'source': row[3],
            'url': row[4],
            'content': row[5],
            'catg': row[6],
            'section': row[7]
        }
                
                
    
    def __setitem__(self, key: int | str, value: ZenianData) -> None:
        '''
        :param key: url or id
        :param value: ZenianData
        '''
        id_: str | None = None
        url: str | None = None
        if isinstance(key, int):
            id_ = str(key)
        else:
            if key.isdigit():
                id_ = key
            else:
                url = key
        if id_ is not None:
            value['id'] = id_
        if url is not None:
            value['url'] = url
        assert valid_data(value)
        sql = f"""--sql
        INSERT OR REPLACE INTO {self._name} 
        (id, title, publish_time, source, url, content, catg, section)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            value['id'],
            value.get('title'),
            value.get('publish_time'),
            value.get('source'),
            value['url'],  # url 是 Required，无值时抛 KeyError 符合预期
            value.get('content'),
            value.get('catg'),
            value.get('section')
        )
        if self._sync_conn is None:
            self._sync_conn = sqlite3.connect(self._db_path)
        # 修复 async with 用法错误
        self._sync_conn.execute(sql, params)
        self._sync_conn.commit()
        if self._conn is None:
            self._sync_conn.close()
            self._sync_conn = None
        self._total_changed += 1

    
    def __delitem__(self, key: int | str) -> None:
        '''
        :param key: url or id
        '''
        id_: str | None = None
        url: str | None = None
        if isinstance(key, int):
            id_ = str(key)
        else:
            if key.isdigit():
                id_ = key
            else:
                url = key
        if id_ is None and url is None:
            raise KeyError(key)
        if id_ is not None:
            condition = f'id={id_}'
        else:
            condition = f'url={url}'
        sql = f"""--sql
        DELETE FROM {self._name} WHERE {condition}
        """
        if self._sync_conn is None:
            self._sync_conn = sqlite3.connect(self._db_path)
        self._sync_conn.execute(sql)
        self._sync_conn.commit()
        if self._conn is None:
            self._sync_conn.close()
            self._sync_conn = None
        self._total_changed += 1
    
    def __len__(self) -> int:
        sql = """--sql
        SELECT COUNT(*) FROM zenian
        """
        if self._sync_conn is None:
            self._sync_conn = sqlite3.connect(self._db_path)
        sync_cursor = self._sync_conn.execute(sql)
        count = sync_cursor.fetchone()[0]
        if self._conn is None:
            self._sync_conn.close()
            self._sync_conn = None
        return count
        
    
    def __in__(self, key: int | str) -> bool:
        '''
        check if table contains data with given url or id
        :param key: url or id
        :return: bool
        '''
        # TODO:
        pass


async def main():
    # only use async context manager can you use async methods
    # if you you only need sync methods, use context manager will deep the frequency
    # of connect and close
    async with ZenianTable() as table:
        print(len(table))
        await table.export('中国金属网', '新闻公告', '稀土')
    print(len(table))


if __name__ == '__main__':
    asyncio.run(main())
