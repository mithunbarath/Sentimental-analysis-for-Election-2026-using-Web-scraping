
import asyncio
import sys
import os

# Prioritize local scrapling_lib
scrapling_path = os.path.join(os.getcwd(), 'scrapling_lib')
if os.path.exists(scrapling_path):
    sys.path.insert(0, scrapling_path)

from scrapling.fetchers import AsyncStealthySession

async def main():
    print(f"Terminal encoding: {sys.stdout.encoding}")
    
    # Try a known Tamil YouTube video or search
    async with AsyncStealthySession(headless=True) as session:
        # Search for "palladam" which should have Tamil results
        url = "https://www.youtube.com/results?search_query=palladam&sp=CAISAggB"
        print(f"Fetching {url}...")
        response = session.fetch(url) # Fetch is sync in AsyncStealthySession? No, wait.
        # Actually in AsyncStealthySession, fetch is a coroutine but it returns a Response.
        # Wait, let me check base_scraper.py.
        
        response = await session.fetch(url)
        
        # Check raw content hex
        content_sample = response.body[:500]
        print(f"Raw content sample (hex): {content_sample.hex()[:100]}...")
        
        # Try to find a title
        video_titles = response.css('#video-title::attr(title)').getall()
        print(f"Found {len(video_titles)} titles.")
        
        for i, title in enumerate(video_titles[:5]):
            print(f"Title {i}: {title}")
            # Print hex of the title string to see if it's '?' (0x3F) or actual Unicode
            title_hex = title.encode('utf-8', errors='replace').hex()
            print(f"Title {i} Hex: {title_hex[:100]}...")

if __name__ == "__main__":
    asyncio.run(main())
