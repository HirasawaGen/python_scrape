from pathlib import Path
import json
import asyncio
from asyncio import Semaphore

from playwright.async_api import async_playwright, Browser, Page


ROOT = Path(__file__).parent
TIMEOUT = 1000000  # ms
SEM = Semaphore(20)


async def get_catg(link: str, browser: Browser) -> str:
    mapping = {
        '新闻': '新闻公告',
        '技术': '材料研究',
        '分析': '行业研究',
    }
    async with SEM:
        page = await browser.new_page()
        try:
            await page.goto(link, timeout=TIMEOUT, wait_until='domcontentloaded')
            await page.wait_for_selector('#article', timeout=TIMEOUT)
        except Exception as e:
            print(f'Failed to extract data from {link}: {e}')
            await page.close()
            return 'unknown'
        catehead = page.locator('div.catehead')
        catehead_span = catehead.locator('span')
        span_inner_text = await catehead_span.inner_text()
        await page.close()
    splited_span_inner_text = span_inner_text.split('|')
    splited_span_inner_text = [s.strip() for s in splited_span_inner_text]
    catg = [s for s in splited_span_inner_text if s.startswith('分类')][0]
    catg = catg.split('：')[1].strip()
    catg = mapping.get(catg, 'unknown')
    print(f'Got category {catg} from {link}')
    return catg
    
async def main():
    results = []
    for file in (ROOT / 'results').glob("锂电网_*.json"):
        with file.open(encoding='utf-8') as f:
            data = json.load(f)
            results.extend(data)
    # results = results[:20]  # for testing
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        tasks = [get_catg(result['url'], browser) for result in results]
        categories = await asyncio.gather(*tasks)
        await browser.close()
    new_results = []
    id_ = 30003402
    for result, catg in zip(results, categories):
        if catg == 'unknown':
            continue
        result['id'] = id_
        result['catg'] = catg
        id_ += 1
        new_results.append(result)
    with (ROOT / 'results' / 'all_data.json').open('w', encoding='utf-8') as f:
        json.dump(new_results, f, ensure_ascii=False, indent=4)
        
        
if __name__ == '__main__':
    asyncio.run(main())
