import time
import json

from playwright.sync_api import sync_playwright
import requests


SEARCH_TEXT = '%E9%94%8C'


def main():
    url = (
        'https://cn.investing.com/search/'
        f'?q={SEARCH_TEXT}'
        '&tab=news'
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # 必须用无头，不然cookies不完整
            args=[
                '--disable-gpu'
            ]
        )
        page = browser.new_page()
        page.goto(url, wait_until='domcontentloaded', timeout=100000)
        # stealth = Stealth()
        # stealth.apply_stealth_sync(page)
        # selector = 'div.searchSection:not(.displayNoneImp) div.resultsSum span'
        # page.wait_for_selector(selector)
        # results_sum = page.query_selector(selector)
        # if results_sum is None:
        #     print('No results found.')
        #     return
        # count = int(results_sum.inner_text().replace(',', ''))
        # print(f'Found {count} results.')
        time.sleep(10)
        count = 3351  # 我发现用脚本获取完全没有手动查看方便
        cookies = {
            c['name']: c['value']
            for c in page.context.cookies()
            if 'name' in c and 'value' in c
        }
        user_agent = page.evaluate('() => navigator.userAgent')
    print('已从playwright获取到cookie和user-agent')
    session = requests.Session()
    session.headers.update({
        'User-Agent': user_agent,
        'Accept': '*/*',
        'X-Requested-With': 'XMLHttpRequest',  # 关键
    })
    session.cookies.update(cookies)  # 注入初始 cookie
    
    api_url = 'https://cn.investing.com/search/service/SearchInnerPage'  # 无空格
    
    all_results = []
    
    for i in range(0, count, 270):
        data = {
            'search_text': SEARCH_TEXT,
            'tab': 'news',
            'offset': str(i),           # 必须是字符串
            'limit': str(min(270, count - i)),
        }
        
        # 第一次请求特殊参数
        if i == 0:
            data['isFilter'] = 'true'
        try:
            resp = session.post(
                api_url,
                data=data,
                timeout=60,
            )
            resp.raise_for_status()
            
            # 检查返回类型
            content_type = resp.headers.get('Content-Type', '')
            if 'json' in content_type:
                batch = resp.json()
            else:
                try:
                    batch = json.loads(resp.text)
                except json.JSONDecodeError:
                    print(f'Offset {i}: 返回数据格式不正确，结束')
                    continue
            batch = batch.get('news', [])
            if not len(batch):
                print(f'Offset {i}: 返回空数据，结束')
                break
            
            with open(f'news_{i}.json', 'w', encoding='utf-8') as f:
                json.dump(batch, f, ensure_ascii=False, indent=4)

            all_results.extend(batch)
            print(f'Offset {i}: 获取 {len(batch)} 条，累计 {len(all_results)}')
            
            # 延时防封
            time.sleep(1)
            
        except requests.exceptions.RequestException as e:
            print(f'请求失败 offset={i}: {e}')
            break





if __name__ == '__main__':
    main()
        
