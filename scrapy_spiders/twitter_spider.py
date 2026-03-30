"""
Scrapy spider for Twitter/X search using native Playwright session injection.
This completely bypasses rate-limits and blocks by using the authenticated browser context.
"""

import hashlib
import logging
from datetime import datetime
from typing import List
from urllib.parse import quote_plus

import scrapy
from scrapy_playwright.page import PageMethod

from scrapy_spiders.items import SocialPostItem

logger = logging.getLogger(__name__)

_PARTY_KEYWORDS = {
    "dmk": ["dmk", "டிஎம்கே", "stalin"],
    "admk": ["admk", "aiadmk", "அதிமுக", "eps"],
    "tvk": ["tvk", "டி.வி.கே", "vijay"],
}
_REGION_KEYWORDS = ["palladam", "பல்லடம்", "tiruppur", "திருப்பூர்"]


def _classify(text: str):
    tl = (text or "").lower()
    parties = [p for p, kws in _PARTY_KEYWORDS.items() if any(k in tl for k in kws)]
    is_palladam = any(k in tl for k in _REGION_KEYWORDS)
    return parties, is_palladam


class TwitterSpider(scrapy.Spider):
    name = "twitter"
    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 90_000,
    }

    def __init__(self, keywords: List[str] = None, max_tweets: int = 100, **kwargs):
        super().__init__(**kwargs)
        self.keywords = keywords or ["palladam"]
        self.max_tweets = max_tweets
        self.results = []

    def start_requests(self):
        for kw in self.keywords:
            url = f"https://twitter.com/search?q={quote_plus(kw)}&src=typed_query&f=live"
            yield scrapy.Request(
                url,
                callback=self.parse_twitter,
                meta={
                    "playwright": True,
                    "playwright_context": "twitter",
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 5000),
                        PageMethod("evaluate", "window.scrollBy(0, 3000)"),
                        PageMethod("wait_for_timeout", 3000),
                    ],
                    "keyword": kw,
                },
                errback=self.handle_error,
            )

    async def parse_twitter(self, response):
        page = response.meta.get("playwright_page")
        keyword = response.meta.get("keyword", "")

        try:
            tweets = response.css('article[data-testid="tweet"]')
            count = 0
            
            for tweet in tweets:
                if count >= self.max_tweets:
                    break
                    
                text_fragments = tweet.css('div[data-testid="tweetText"] ::text').getall()
                text = " ".join(text_fragments).strip()
                if not text:
                    continue
                    
                author_fragments = tweet.css('div[data-testid="User-Name"] ::text').getall()
                author = " ".join(author_fragments).replace("@", "").strip()
                
                links = tweet.css('a[href*="/status/"]::attr(href)').getall()
                tweet_link = links[0] if links else ""
                
                tweet_id = tweet_link.rstrip("/").split("/")[-1] if tweet_link else hashlib.md5(text.encode()).hexdigest()[:16]
                tweet_url = f"https://twitter.com{tweet_link}" if tweet_link.startswith("/") else tweet_link
                
                parties, is_palladam = _classify(text + " " + keyword)

                yield SocialPostItem(
                    platform="twitter",
                    type="post",
                    id=tweet_id,
                    url=tweet_url,
                    author=author or None,
                    text=text,
                    source="scrapy_twitter_auth",
                    timestamp=datetime.utcnow(),
                    parties_mentioned=parties,
                    is_palladam_related=is_palladam,
                )
                count += 1
                
            logger.info(f"Twitter [{keyword}]: extracted {count} tweets via authenticated session")
        finally:
            if page:
                await page.close()

    def handle_error(self, failure):
        logger.error(f"Twitter spider error: {failure.value}")
