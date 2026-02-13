from pathlib import Path
from datetime import datetime

import cv2
from captcha_recognizer.slider import Slider
from playwright.async_api import Page
from bs4 import BeautifulSoup
from loguru import logger as LOGGER


SLIDER = Slider()
CAPTCHA_ROOT = Path() / 'captcha'


async def slider_captcha(page: Page) -> bool:
    title = await page.title()
    if '人机验证' not in title:
        LOGGER.warning('不是验证码')
        return False
    locator = page.locator('#tcaptcha_wrapper_transform_dy')
    await locator.wait_for(state='visible')
    html_content = await page.content()
    with (Path() / 'content.html').open('w', encoding='utf-8') as f:
        f.write(html_content)
    soup = BeautifulSoup(html_content, 'lxml')
    slide_background = soup.select_one('#slideBg')
    if slide_background is None:
        LOGGER.warning('滑块背景图片未找到')
        return False
    style = slide_background.get('style')
    if style is None:
        LOGGER.warning('滑块背景图片样式未找到')
        return False
    LOGGER.info(f'滑块背景图片样式: {style}')
    return True


# offset, confidence = Slider().identify_offset(source='example.png')
# print(f'偏移量: {offset}')
# print('置信度', confidence)
# offset = int(offset)


# image = cv2.imread('example.png')
# assert image is not None, '读取图片失败'

# image[:, offset:offset+10, :] = 0
# cv2.imwrite('result.png', image)


async def main():
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
    stealth = Stealth()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await stealth.apply_stealth_async(page)
        await page.goto('https://www.cnfeol.com/xitu/n-8-1.aspx', wait_until='load')
        await slider_captcha(page)
        await browser.close()


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())

