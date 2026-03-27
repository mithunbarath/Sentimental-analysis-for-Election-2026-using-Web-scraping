"""
Scrapy spider for Facebook — public pages and groups.

Uses Playwright because Facebook's feed is dynamically loaded.
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


class FacebookSpider(scrapy.Spider):
    name = "facebook"
    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 90_000,
    }

    def __init__(self, keywords: List[str] = None, page_urls: List[str] = None, max_posts: int = 50, **kwargs):
        super().__init__(**kwargs)
        self.keywords = keywords or ["palladam"]
        self.page_urls = page_urls or []
        self.max_posts = max_posts
        self.results = []

    def start_requests(self):
        # Search Facebook for each keyword (public search, no login needed)
        for kw in self.keywords:
            search_url = f"https://www.facebook.com/search/posts?q={quote_plus(kw)}"
            yield scrapy.Request(
                search_url,
                callback=self.parse_search,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 4000),
                        PageMethod("evaluate", "window.scrollBy(0, 3000)"),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                    "keyword": kw,
                },
                errback=self.handle_error,
            )

        # Also crawl explicit page URLs
        for page_url in self.page_urls:
            yield scrapy.Request(
                page_url,
                callback=self.parse_page,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 3000),
                        PageMethod("evaluate", "window.scrollBy(0, 3000)"),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                },
                errback=self.handle_error,
            )

    async def parse_search(self, response):
        page = response.meta.get("playwright_page")
        keyword = response.meta.get("keyword", "")

        try:
            # Extract post text blocks
            post_texts = response.css('div[data-ad-comet-preview="message"] span::text').getall()
            if not post_texts:
                post_texts = response.css('div[role="feed"] div[dir="auto"] span::text').getall()

            count = 0
            for text in post_texts:
                if count >= self.max_posts:
                    break
                text = text.strip()
                if len(text) < 20:
                    continue

                parties, is_palladam = _classify(text + " " + keyword)
                post_id = hashlib.md5(text.encode()).hexdigest()[:16]

                yield SocialPostItem(
                    platform="facebook",
                    type="post",
                    id=post_id,
                    url=response.url,
                    text=text,
                    source="scrapy_facebook_search",
                    timestamp=datetime.utcnow(),
                    parties_mentioned=parties,
                    is_palladam_related=is_palladam,
                )
                count += 1

            logger.info(f"Facebook [{keyword}]: extracted {count} posts")
        finally:
            if page:
                await page.close()

    async def parse_page(self, response):
        page = response.meta.get("playwright_page")
        try:
            posts = response.css('div[role="article"]')
            count = 0
            for post in posts:
                if count >= self.max_posts:
                    break
                text = " ".join(post.css("div[dir='auto'] span::text").getall()).strip()
                if len(text) < 20:
                    continue
                post_id = hashlib.md5(text.encode()).hexdigest()[:16]
                parties, is_palladam = _classify(text)
                yield SocialPostItem(
                    platform="facebook",
                    type="post",
                    id=post_id,
                    url=response.url,
                    text=text,
                    source="scrapy_facebook_page",
                    timestamp=datetime.utcnow(),
                    parties_mentioned=parties,
                    is_palladam_related=is_palladam,
                )
                count += 1
        finally:
            if page:
                await page.close()

    def handle_error(self, failure):
        logger.error(f"Facebook spider error: {failure.value}")
