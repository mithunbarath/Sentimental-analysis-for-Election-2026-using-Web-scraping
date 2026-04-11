import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from base_scraper import AsyncBaseScraper
from models import SocialMediaRecord
from filters import PartyClassifier, RegionClassifier

logger = logging.getLogger(__name__)

class TwitterScraper(AsyncBaseScraper):
    """Scraper for Twitter/X using Scrapling."""

    def __init__(self, headless: bool = True, session_dir: Optional[str] = None):
        super().__init__(headless=headless, session_dir=session_dir)
        self.party_classifier = PartyClassifier()
        self.region_classifier = RegionClassifier()

    async def run(self, keyword: str) -> List[SocialMediaRecord]:
        """Search for a keyword on Twitter and collect tweets."""
        logger.info(f"Searching Twitter for: {keyword}")
        records = []
        
        try:
            # Twitter search URL
            search_url = f"https://x.com/search?q={keyword}&src=typed_query&f=live"
            response = await self.fetch(search_url)
            
            # Scrapling response object allows us to run JS if needed, but we used base_scraper's fetch
            # which just returns the StaticResponse. To scroll, we need the page.
            page = await self.get_page()
            
            # Check for login wall or rate limiting
            if "login" in str(page.url).lower() and not self.session_dir:
                logger.warning(f"Twitter redirected to login for '{keyword}'. Please use --login twitter first.")
                await self.save_debug_screenshot(f"twitter_login_{keyword}")
                return []

            await self.scroll_to_bottom(page, max_scrolls=2, delay=2.0)
            
            # Refresh response from updated page content to catch newly loaded tweets
            content = await page.content()
            from scrapling import Selector
            response = Selector(content, url=page.url)
            
            # Twitter uses [data-testid="tweet"] for tweet containers
            tweet_elements = response.css('[data-testid="tweet"]')
            logger.info(f"Found {len(tweet_elements)} tweets for keyword: {keyword}")
            
            if not tweet_elements:
                await self.save_debug_screenshot(f"twitter_no_results_{keyword}")

            for tweet in tweet_elements[:30]:
                try:
                    # Extract text safely
                    text_nodes = tweet.css('[data-testid="tweetText"]')
                    text = text_nodes[0].text if text_nodes else None
                    if not text:
                        text = tweet.css('[data-testid="tweetText"]::text').get()
                    
                    if not text:
                        continue
                        
                    # Extract unique ID if possible
                    # Links often contain the tweet ID: /status/12345
                    time_link = tweet.css('time').parent().css('a::attr(href)').get()
                    tweet_url = f"https://twitter.com{time_link}" if time_link else ""
                    
                    tweet_id = tweet_url.split('/')[-1] if tweet_url and '/' in tweet_url else f"tw_{hash(text)}"
                    
                    record = SocialMediaRecord(
                        platform="twitter",
                        type="post",
                        id=tweet_id,
                        url=tweet_url,
                        text=text,
                        timestamp=datetime.now(),
                        source="scrapling_twitter",
                        parties_mentioned=self.party_classifier.classify_parties(text),
                        is_kongu_related=self.region_classifier.is_kongu_related(text=text)
                    )
                    records.append(record)
                except Exception as e:
                    logger.warning(f"Error parsing tweet: {e}")
                    
        except Exception as e:
            logger.error(f"Twitter search failed for {keyword}: {e}")
            await self.save_debug_screenshot(f"twitter_error_{keyword}")
            
        return records

    async def scrape_profile(self, profile_url: str, post_limit: int = 20) -> List[SocialMediaRecord]:
        """Navigate to a Twitter profile and collect tweets."""
        logger.info(f"Navigating to Twitter Profile: {profile_url}")
        records = []
        
        try:
            response = await self.fetch(profile_url)
            page = await self.get_page()
            
            if "login" in str(page.url).lower() and not self.session_dir:
                logger.warning(f"Profile {profile_url} redirected to login. Consider establishing a session.")
                # We can still try sometimes Twitter lets you see the first few tweets
                
            try:
                await page.wait_for_selector('[data-testid="tweet"]', timeout=5000)
            except Exception:
                pass # Might not exist if blocked
                
            await self.scroll_to_bottom(page, max_scrolls=(post_limit // 5) + 1, delay=2.0)
            
            content = await page.content()
            from scrapling import Selector
            response = Selector(content, url=page.url)
            
            tweet_elements = response.css('[data-testid="tweet"]')
            logger.info(f"Found {len(tweet_elements)} tweets on profile {profile_url}")
            
            author_name = profile_url.rstrip("/").split("/")[-1]
            
            for tweet in tweet_elements[:post_limit]:
                try:
                    text_nodes = tweet.css('[data-testid="tweetText"]')
                    text = text_nodes[0].text if text_nodes else None
                    if not text:
                        text = tweet.css('[data-testid="tweetText"]::text').get()
                    
                    if not text:
                        continue
                        
                    time_link = tweet.css('time').parent().css('a::attr(href)').get()
                    tweet_url = f"https://twitter.com{time_link}" if time_link else ""
                    
                    tweet_id = tweet_url.split('/')[-1] if tweet_url and '/' in tweet_url else f"tw_{hash(text)}"
                    
                    record = SocialMediaRecord(
                        platform="twitter",
                        type="post",
                        id=tweet_id,
                        url=tweet_url,
                        text=text,
                        author=author_name,
                        timestamp=datetime.now(),
                        source="scrapling_twitter_profile"
                    )
                    records.append(record)
                except Exception as e:
                    pass
        except Exception as e:
            logger.error(f"Twitter profile extraction failed for {profile_url}: {e}")
            
        return records