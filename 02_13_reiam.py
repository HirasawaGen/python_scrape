import asyncio
from itertools import count

from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from loguru import logger as LOGGER
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright.async_api import Request

from database import ZenianData, ZenianTable


LIMITER = AsyncLimiter(1, 1)


async def extract_token_and_cookies(url: str) -> tuple[str, dict[str, str]]:
    """
    访问指定 URL，拦截 statisticsInfo 请求，提取 Token 和 Cookies
    
    Args:
        url: 目标网页地址
    
    Returns:
        (token, cookies_dict) 如果未找到 token 则返回 (None, cookies)
    """
    token_value: str | None = None
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        async def handle_route(route, request: Request):
            nonlocal token_value
            
            request_url = request.url
            if request_url.startswith("https://www.reianm.cn/api/statistics/statisticsInfo"):
                headers = request.headers
                
                token = (
                    headers.get('token') or 
                    headers.get('Token') or
                    headers.get('X-Token') or
                    headers.get('x-token')
                )
                
                if token:
                    token_value = token
                    print(f"✅ 捕获到 Token: {token[:20]}..." if len(token) > 20 else f"✅ 捕获到 Token: {token}")
                
            await route.continue_()
        
        await page.route("**/*", handle_route)
        
        print(f"🚀 正在访问: {url}")
        await page.goto(url, wait_until="networkidle")
        while token_value is None:
            await asyncio.sleep(0.5)

        cookies = await context.cookies()
        cookies_dict: dict[str, str] = {
            cookie['name']: cookie['value']
            for cookie in cookies
            if 'name' in cookie and 'value' in cookie
        }
        
        print(f"🍪 获取到 {len(cookies_dict)} 个 Cookies")
        
        await browser.close()
        
        if token_value is None:
            print("⚠️ 未找到 Token，请检查页面是否需要交互才能触发请求")
        
        return token_value, cookies_dict


DOMAIN = 'https://www.reianm.cn'


async def get_info(
    session: ClientSession,
    id_: str,
) -> tuple[str, str]:
    info_get = f'{DOMAIN}/api/webserver/cate/info?id={id_}'
    async with (
        LIMITER,
        session.get(info_get) as resp,
    ):
        if resp.status != 200:
            LOGGER.error(f"获取 {id_} 信息失败: {resp.status}")
            return '', ''
        info = await resp.json()
    LOGGER.info(f"获取 {id_} 信息成功")
    try:
        info_data = info['data']
        cate_id = info_data['navSystemModule']
        section = info_data['navName']
    except KeyError:
        LOGGER.error(f"获取 {id_} 信息失败: 未找到导航信息")
        return '', ''
    return cate_id, section
        


async def search(
    session: ClientSession,
    table: ZenianTable,
    cate_id: str,
    section: str,
) -> list[ZenianData]:
    all_ans: list[ZenianData] = []
    for i in count(1):
        info_list_get = (
            f'{DOMAIN}/api/association/nuxt/info/v2/infoList'
            f'?cateId={cate_id}'
            '&size=10'
            f'&page={i}'
        )
        async with (
            LIMITER,
            session.get(info_list_get) as resp,
        ):
            if resp.status != 200:
                LOGGER.error(f"获取 {cate_id} - {section} 第 {i} 页列表失败: {resp.status}")
                return []
            info_list = await resp.json()
        try:
            info_list_data = info_list['data']
            info_list = info_list_data['list']
            is_last_page = info_list_data['isLastPage']
        except KeyError:
            LOGGER.error(f"获取 {cate_id} - {section} 第 {i} 页列表失败: 未找到列表信息")
            return []
        if not isinstance(info_list, list):
            LOGGER.error(f"获取 {cate_id} - {section} 第 {i} 页列表失败: 列表信息不是列表")
            return []
        ans: list[ZenianData] = []
        for info in info_list:
            try:
                article_id = info['id']
                title = info['title']
                publish_time = info['publishTime']
                ans.append({
                    'url': f'https://www.reianm.cn/page/new/{article_id}',
                    'title': title,
                    'publish_time': publish_time,
                    'source': '内蒙古自治区稀土行业协会',
                    'catg': '行业研究',
                    'section': section,
                }) 
            except KeyError:
                continue
        LOGGER.info(f"获取 {cate_id} - {section} 第 {i} 页列表成功: {len(ans)} 篇文章")
        if len(ans) == 0:
            break
        saved_count = await table.save(ans)
        LOGGER.info(f"保存 {saved_count} 篇文章到数据库")
        all_ans += ans
        if is_last_page:
            break
    LOGGER.info(f"获取 {cate_id} - {section} 全部数据成功")
    return all_ans


async def fetch_content(
    session: ClientSession,
    table: ZenianTable,
    data: ZenianData,
) -> str:
    url = data['url']
    if not 'title' in data:
        return ''
    title = data['title']
    async with (
        LIMITER,
        session.get(url) as resp,
    ):
        if resp.status != 200:
            LOGGER.error(f"获取 {title} 内容失败: {resp.status}")
            return ''
        html_content = await resp.text()
    soup = BeautifulSoup(html_content, 'lxml')
    new_box = soup.select_one('div.new-box')
    if new_box is None:
        LOGGER.error(f"获取 {title} 内容失败: 未找到div.new-box")
        return ''
    content = new_box.get_text(strip=True)
    LOGGER.info(f"获取 {title} 内容成功: {content[:100]}")
    if '稀土' in title or '稀土' in content:
        await table.fill_content(url, content)
        LOGGER.info(f"保存 {title} 内容到数据库")
    else:
        LOGGER.warning(f'{title} 不是稀土文章，不保存内容')
    return content


async def main():
    
    id_ = '8480307206081425408'
    
    url = f'https://www.reianm.cn/page/{id_}'
    token, cookies = await extract_token_and_cookies(url)
    LOGGER.info(f"Token: {token}")    
    LOGGER.info(f"Cookies: {cookies}")
    async with (
        ClientSession(
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
                'Referer': 'https://www.reianm.cn/',
                'Authorization': f'Bearer {token}',
                'Token': token,
            },
            cookies=cookies,
        ) as session,
        ZenianTable() as table,
    ):
        '''
        协会新闻，内容带稀土，做好去重
团体标准，内容带稀土，做好去重
标准新闻，内容带稀土，做好去重
科技资讯，内容带稀土，做好去重
专题研究，内容带稀土，做好去重
技术创新，内容带稀土，做好去重
政策法规，内容带稀土，做好去重
行业动态，内容带稀土，做好去重
        '''
        sections = [
            '协会新闻', '团体标准', '标准新闻', '科技资讯', '专题研究', '技术创新', '政策法规', '行业动态'
        ]
        
        for section in sections:
            await table.export('内蒙古自治区稀土行业协会', '行业研究', section)

        cate_id, section = await get_info(session, id_)

        # task1
        if not len(cate_id) or not len(section):
            LOGGER.error(f"获取 {id_} 信息失败: 未找到导航信息")
            return
        LOGGER.info(f"导航信息: {cate_id} - {section}")
        await search(session, table, cate_id, section)

        # task2
        all_data = await table.load('内蒙古自治区稀土行业协会', '行业研究', section)
        all_data = [
            data
            for data in all_data
            if data.get('content', 'None') == 'None'
        ]
        LOGGER.info(f"需要获取 {len(all_data)} 篇文章内容")
        tasks = [
            fetch_content(session, table, data)
            for data in all_data
        ]
        await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
