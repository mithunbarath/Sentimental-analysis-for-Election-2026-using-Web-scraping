import asyncio
from scrapling import Selector
from instagram_scraper import InstagramScraper

async def test():
    scraper = InstagramScraper(headless=True, session_dir=".sessions")
    await scraper.start()
    page = await scraper.get_page()
    await page.goto("https://www.instagram.com/jayaramakrishnan.r/p/DW7A-tZDk5s/", wait_until="networkidle")
    await asyncio.sleep(3)
    
    content = await page.content()
    sel = Selector(content)
    
    print("Time tag datetime:", sel.css('time::attr(datetime)').get())
    print("Meta tag published_time:", sel.css('meta[property="article:published_time"]::attr(content)').get())
    
    import re
    print("datetime regex:", re.search(r'datetime="([^"]+)"', content))
    print("uploadDate regex:", re.search(r'"uploadDate":"([^"]+)"', content))
    print("dateCreated regex:", re.search(r'"dateCreated":"([^"]+)"', content))
    print("taken_at regex:", re.search(r'"taken_at":(\d+)', content))
    
    with open("page_dump.html", "w", encoding="utf-8") as f:
        f.write(content)
        
    await scraper.stop()

if __name__ == "__main__":
    asyncio.run(test())
