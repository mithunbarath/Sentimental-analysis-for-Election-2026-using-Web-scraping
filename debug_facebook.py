import asyncio
from playwright.async_api import async_playwright
import os
from urllib.parse import quote_plus

async def main():
    print("Starting Playwright Facebook debug...")
    async with async_playwright() as p:
        user_data_dir = os.path.join(os.getcwd(), ".sessions", "facebook")
        print(f"Loading session from: {user_data_dir}")
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,  # Run headless so it works in the background
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # A persistent context automatically provides a default page, but we can open a new one
        if len(browser.pages) > 0:
            page = browser.pages[0]
        else:
            page = await browser.new_page()
            
        keyword = "palladam"
        url = f"https://www.facebook.com/search/posts/?q={quote_plus(keyword)}"
        
        print(f"Navigating to {url}")
        await page.goto(url)
        
        print("Waiting for page to naturally render (sleeping 5 seconds)...")
        await page.wait_for_timeout(5000)
        
        print("Scrolling down to trigger lazy loading...")
        await page.evaluate("window.scrollBy(0, 3000)")
        await page.wait_for_timeout(3000)
        
        print("Taking screenshot to 'facebook_debug.png'")
        await page.screenshot(path="facebook_debug.png", full_page=True)
        
        print("Saving raw HTML to 'facebook_debug.html' to analyze valid CSS selectors...")
        html = await page.content()
        with open("facebook_debug.html", "w", encoding="utf-8") as f:
            f.write(html)

        # Print some summary extracted text to see if we see "Palladam" or search results
        text_content = await page.evaluate("() => document.body.innerText")
        print("\n--- Snippet of visible text on page ---")
        print(text_content[:1500])
        print("---------------------------------------\n")
            
        await browser.close()
        print("Debug script completed!")

if __name__ == "__main__":
    asyncio.run(main())
