import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from base_scraper import AsyncBaseScraper
from models import SocialMediaRecord
from filters import PartyClassifier, RegionClassifier

logger = logging.getLogger(__name__)

class FacebookScraper(AsyncBaseScraper):
    """Scraper for Facebook using Scrapling."""

    def __init__(self, headless: bool = True, session_dir: Optional[str] = None):
        super().__init__(headless=headless, session_dir=session_dir)
        self.party_classifier = PartyClassifier()
        self.region_classifier = RegionClassifier()

    async def run(self, keyword: str) -> List[SocialMediaRecord]:
        """Search for a keyword on Facebook and collect posts."""
        logger.info(f"Searching Facebook for: {keyword}")
        records = []
        
        try:
            # Facebook search URL (posts results are better for authenticated)
            search_url = f"https://www.facebook.com/search/posts/?q={keyword}"
            response = await self.fetch(search_url)
            
            # Add scrolling to ensure dynamic content loads
            page = await self.get_page()
            
            # Check for login wall
            if ("login" in str(page.url).lower() or "checkpoint" in str(page.url).lower()) and not self.session_dir:
                logger.warning(f"Facebook redirected to login/checkpoint for '{keyword}'. Please use --login facebook first.")
                await self.save_debug_screenshot(f"facebook_login_{keyword}")
                return []

            await self.scroll_to_bottom(page, max_scrolls=3, delay=2.0)
            
            # Refresh response from updated page content
            content = await page.content()
            from scrapling import Selector
            response = Selector(content, url=page.url)
            
            # Facebook selectors are dynamic, but we can look for specific patterns
            # Posts are often in [role="article"]
            post_elements = response.css('[role="article"]')
            logger.info(f"Found {len(post_elements)} potential post elements for keyword: {keyword}")
            
            if not post_elements:
                await self.save_debug_screenshot(f"facebook_no_results_{keyword}")

            for post in post_elements[:20]:
                try:
                    # Extract text content from common post body selectors
                    text_parts = post.css('[dir="auto"]::text').getall()
                    text = " ".join(text_parts).strip()
                    if not text:
                        # Try fallback for text
                        text = post.css('div[style*="webkit-line-clamp"]::text').get()
                    
                    if not text:
                        continue
                        
                    # Extract link - Facebook hides these in many ways
                    link = post.css('a[href*="/posts/"]::attr(href)').get()
                    if not link:
                        link = post.css('a[href*="/permalink/"]::attr(href)').get()
                    if not link:
                        link = post.css('a[href*="/videos/"]::attr(href)').get()
                    
                    full_link = link if link and link.startswith('http') else f"https://www.facebook.com{link}" if link else ""
                    
                    # Generate a unique ID
                    post_id = full_link.split('/')[-1] if full_link and '/' in full_link else f"fb_{hash(text)}"
                    
                    record = SocialMediaRecord(
                        platform="facebook",
                        type="post",
                        id=post_id,
                        url=full_link,
                        text=text,
                        timestamp=datetime.now(),
                        source="scrapling_facebook",
                        parties_mentioned=self.party_classifier.classify_parties(text),
                        is_kongu_related=self.region_classifier.is_kongu_related(text=text)
                    )
                    records.append(record)
                except Exception as e:
                    logger.warning(f"Error parsing post: {e}")
                    
        except Exception as e:
            logger.error(f"Facebook search failed for {keyword}: {e}")
            await self.save_debug_screenshot(f"facebook_error_{keyword}")
            
        return records