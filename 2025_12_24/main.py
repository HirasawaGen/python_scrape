import json
from collections import OrderedDict
from pathlib import Path

from playwright.sync_api import sync_playwright


URL = 'https://s.chinabgao.com/?w=%E9%94%82&r=6'
HEADLESS = False
ROOT = Path(__file__).parent
START_ID = 30003167


def main():
    results: list[OrderedDict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=2000)
        main_page = browser.new_page()
        
        main_page.goto(URL)
        main_page.pause()  # 可能有人机验证
        # page.screenshot(path="current_view.png", full_page=False)
        
        page_index = 1
        while True:
            try:
                next_button = main_page.wait_for_selector('text="下一页"', timeout=3000)
            except:
                break
            # if page_index >= 2:  # for testing
            #     break
            a_tags = main_page.locator('div.listtitle a')
            print(f'第 {page_index} 页一共有 {a_tags.count()} 条新闻')
            for i in range(a_tags.count()):
                result = OrderedDict()
                a_tag = a_tags.nth(i)
                title = a_tag.inner_text()
                url = a_tag.get_attribute('href')
                print(f"正在打开第{page_index} 页第 {i+1} 个链接: {url}")
                with main_page.context.expect_page() as new_page_info:
                    a_tag.click()  # 点击链接
                # 获取新打开的页面
                new_page = new_page_info.value
                div_tag = new_page.locator('div.arccon')
                if div_tag.count() == 0:  # 可能是视频
                    print(f"第{page_index} 页第 {i+1} 个链接无正文，跳过")
                    new_page.close()  # 关闭新页面
                    continue
                content = div_tag.inner_text()
                publish_time = new_page.locator('span.pubTime').inner_text()
                
                
                # new_page.pause()
                new_page.close()  # 关闭新页面
                
                result['title'] = title
                result['publish_time'] = publish_time
                result['source'] = '报告大厅'
                result['url'] = f'https:{url}'
                result['content'] = content
                result['catg'] = '行业研究'
                    
                results.append(result)
            
            next_button.click()
            # main_page.screenshot(path=f"page_{page_index}.png", full_page=True)
            page_index += 1
            # 每隔一页就保存一次，防止突发情况导致数据丢失
            with (ROOT / 'results.json').open('w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=4)


def process_results(start_id):
    results_: list[OrderedDict] = []
    with (ROOT /'results.json').open('r', encoding='utf-8') as f:
        results = json.load(f)
    id_ = start_id
    id_ += 1
    for result in results:
        publish_time = result['publish_time']
        if publish_time[:4] < '2010':
            continue
        content = result['content'].strip()
        result_ = OrderedDict()
        result_['id'] = id_
        result_['title'] = result['title']
        result_['publish_time'] = publish_time
        result_['source'] = result['source']
        result_['url'] = result['url']
        result_['content'] = content
        result_['catg'] = result['catg']
        results_.append(result_)
        id_ += 1
    with (ROOT / 'processed_results.json').open('w', encoding='utf-8') as f:
        json.dump(results_, f, ensure_ascii=False, indent=4)
        


if __name__ == '__main__':
    # main()
    process_results(START_ID)
