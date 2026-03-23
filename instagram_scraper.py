import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from base_scraper import AsyncBaseScraper
from models import SocialMediaRecord
from filters import PartyClassifier, RegionClassifier

logger = logging.getLogger(__name__)

class InstagramScraper(AsyncBaseScraper):
    """Scraper for Instagram using Scrapling."""

    def __init__(self, headless: bool = True, session_dir: Optional[str] = None):
        super().__init__(headless=headless, session_dir=session_dir)
        self.party_classifier = PartyClassifier()
        self.region_classifier = RegionClassifier()

    async def run(self, keyword: str) -> List[SocialMediaRecord]:
        """Search for a keyword on Instagram and collect posts."""
        logger.info(f"Searching Instagram for: {keyword}")
        records = []
        
        try:
            # Instagram often uses hashtags or keyword search
            if ' ' in keyword:
                search_url = f"https://www.instagram.com/explore/search/keyword/?q={keyword}"
            else:
                search_url = f"https://www.instagram.com/explore/tags/{keyword.replace(' ', '')}/"
                
            # Scrapling fetch
            response = await self.fetch(search_url)
            
            # For Instagram, we almost always need to scroll to trigger the grid to load
            page = await self.get_page()
            await self.scroll_to_bottom(page, max_scrolls=3, delay=1.5)
            
            # Refresh response from updated page content
            content = await page.content()
            from scrapling import Selector
            response = Selector(content, url=page.url)
            
            # Check for redirect to login
            if "login" in str(response.url).lower() and not self.session_dir:
                logger.warning("Instagram redirected to login. Please use --login instagram first.")
                return []

            # Scrapling has built-in css selection
            # We can find post links specifically
            post_links = response.css('a[href*="/p/"]::attr(href)').getall()
            post_links += response.css('a[href*="/reels/"]::attr(href)').getall()
            
            post_links = list(set(post_links))[:20]
            logger.info(f"Found {len(post_links)} posts for keyword: {keyword}")
            
            for link_suffix in post_links:
                try:
                    full_link = f"https://www.instagram.com{link_suffix}"
                    post_id = link_suffix.split('/')[-2]
                    
                    record = SocialMediaRecord(
                        platform="instagram",
                        type="post",
                        id=post_id,
                        url=full_link,
                        text=f"Instagram post about {keyword}",
                        timestamp=datetime.now(),
                        source="scrapling_instagram",
                        parties_mentioned=self.party_classifier.classify_parties(keyword),
                        is_palladam_related=self.region_classifier.is_palladam_related(text=keyword)
                    )
                    records.append(record)
                except Exception as e:
                    logger.warning(f"Error parsing post {link_suffix}: {e}")
                    
        except Exception as e:
            logger.error(f"Instagram search failed for {keyword}: {e}")
            
        return records