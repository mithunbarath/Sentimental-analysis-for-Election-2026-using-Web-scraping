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
            
            # Check for redirect to login
            if "login" in str(page.url).lower() and not self.session_dir:
                logger.warning(f"Instagram redirected to login for '{keyword}'. Please use --login instagram first.")
                await self.save_debug_screenshot(f"instagram_login_{keyword}")
                return []

            await self.scroll_to_bottom(page, max_scrolls=3, delay=2.0)
            
            # Refresh response from updated page content
            content = await page.content()
            from scrapling import Selector
            response = Selector(content, url=page.url)
            
            # Instagram selectors for posts in the grid
            # Post links: /p/XXXXX/ or /reels/XXXXX/
            # We look for <a> tags with these patterns
            post_links = response.css('a[href*="/p/"]::attr(href)').getall()
            post_links += response.css('a[href*="/reels/"]::attr(href)').getall()
            
            # Remove duplicates and clean
            post_links = list(set([l for l in post_links if l.startswith(('/p/', '/reels/'))]))
            
            logger.info(f"Found {len(post_links)} posts for keyword: {keyword}")
            
            if not post_links:
                await self.save_debug_screenshot(f"instagram_no_results_{keyword}")

            for link_suffix in post_links[:20]: # Limit to top 20
                try:
                    full_link = f"https://www.instagram.com{link_suffix}"
                    # post_id is between slashes
                    parts = [p for p in link_suffix.split('/') if p]
                    post_id = parts[-1] if parts else f"inst_{hash(link_suffix)}"
                    
                    record = SocialMediaRecord(
                        platform="instagram",
                        type="post",
                        id=post_id,
                        url=full_link,
                        text=f"Instagram post about {keyword}", # Content usually requires individual post fetching
                        timestamp=datetime.now(),
                        source="scrapling_instagram",
                        parties_mentioned=self.party_classifier.classify_parties(keyword),
                        is_kongu_related=self.region_classifier.is_kongu_related(text=keyword)
                    )
                    records.append(record)
                except Exception as e:
                    logger.warning(f"Error parsing post {link_suffix}: {e}")
                    
        except Exception as e:
            logger.error(f"Instagram search failed for {keyword}: {e}")
            await self.save_debug_screenshot(f"instagram_error_{keyword}")
            
        return records

    async def scrape_profile(self, profile_url: str, post_limit: int = 20) -> List[SocialMediaRecord]:
        """Navigate to an Instagram profile, collect posts and comments natively."""
        logger.info(f"Navigating to Profile: {profile_url}")
        records = []
        
        try:
            response = await self.fetch(profile_url)
            page = await self.get_page()
            
            if "login" in str(page.url).lower() and not self.session_dir:
                logger.warning(f"Profile {profile_url} redirected to login. You MUST establish a session.")
                return []
                
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
                
            # Scroll the grid ensuring enough posts render
            await self.scroll_to_bottom(page, max_scrolls=(post_limit // 6) + 2, delay=2.0)
            content = await page.content()
            from scrapling import Selector
            response = Selector(content, url=page.url)
            
            # Extract all links and filter for actual posts/reels
            all_links = response.css('a::attr(href)').getall()
            
            unique_links = []
            for l in all_links:
                # Skip the user's primary "Reels" or "Tagged" tab navigations
                clean_l = l.strip('/')
                if clean_l.endswith('reels') or clean_l == 'reels' or clean_l.endswith('tagged'):
                    continue
                    
                # Accept individual posts or reels
                if ('/p/' in l or '/reel/' in l) and l not in unique_links:
                    unique_links.append(l)
                    
            logger.info(f"Found {len(unique_links)} post links on profile {profile_url}")
            unique_links = unique_links[:post_limit]
            
            for link_suffix in unique_links:
                try:
                    full_link = f"https://www.instagram.com{link_suffix}"
                    post_id = [p for p in link_suffix.split('/') if p][-1]
                    
                    logger.info(f"Deep Scraping Post: {full_link}")
                    await page.goto(full_link, wait_until="domcontentloaded")
                    await asyncio.sleep(2.5)  # Required to render DOM comments
                    
                    post_content = await page.content()
                    post_selector = Selector(post_content, url=page.url)
                    
                    # Extract robust metadata
                    caption = post_selector.css('meta[property="og:title"]::attr(content)').get() or ""
                    desc = post_selector.css('meta[property="og:description"]::attr(content)').get() or ""
                    
                    # Look for span lists carrying conversational strings (comments)
                    comments = post_selector.css('ul li > div > div > div > span::text').getall()
                    if not comments:
                        comments = post_selector.css('span[dir="auto"]::text').getall()
                    
                    # Clean up descriptions
                    caption_text = desc.split(":", 1)[1].strip() if ":" in desc else desc
                    author_name = profile_url.rstrip("/").split("/")[-1]
                    
                    post_record = SocialMediaRecord(
                        platform="instagram",
                        type="post",
                        id=post_id,
                        url=full_link,
                        text=caption_text,
                        author=author_name,
                        timestamp=datetime.now(),
                        source="scrapling_instagram_profile"
                    )
                    records.append(post_record)
                    
                    # Register nested comments safely targeting real length phrases
                    valid_comments = [c for c in set(comments) if c and len(c.strip()) > 3 and c != caption_text and c != author_name]
                    for idx, c in enumerate(valid_comments[:50]): 
                        comment_rec = SocialMediaRecord(
                            platform="instagram",
                            type="comment",
                            id=f"{post_id}_c{idx}",
                            parent_id=post_id,
                            url=full_link,
                            text=c,
                            author="unknown",
                            timestamp=datetime.now(),
                            source="scrapling_instagram_profile"
                        )
                        records.append(comment_rec)
                        
                except Exception as e:
                    logger.warning(f"Error scraping post {link_suffix}: {e}")
                    
        except Exception as e:
            logger.error(f"Profile extraction failed for {profile_url}: {e}")
            await self.save_debug_screenshot("instagram_error_profile")
            
        return records