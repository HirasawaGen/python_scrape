from playwright.sync_api import sync_playwright


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    page.goto("https://playwright.dev")
    initial_title = page.title()
    
    page.click('button.DocSearch-Button')
    search_input = page.wait_for_selector('input.DocSearch-Input')
    
    search_input.type('hello world', delay=100)
    search_input.press('Enter')
    
    page.wait_for_load_state('networkidle')
    page.screenshot(path="current_view.png", full_page=False)
    
    print(page.title())
    browser.close()
