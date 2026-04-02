"""
Scrapy spider for Instagram — hashtag and profile pages.

Uses Playwright for JS rendering (Instagram is React-based).
Scrapes public hashtag pages and extracts post metadata.
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
    "dmk": ["dmk", "டிஎம்கே", "stalin", "ஸ்டாலின்"],
    "admk": ["admk", "aiadmk", "அதிமுக", "eps", "edappadi"],
    "tvk": ["tvk", "டி.வி.கே", "vijay", "விஜய்"],
}
_REGION_KEYWORDS = ["palladam", "பல்லடம்", "tiruppur", "திருப்பூர்"]


def _classify(text: str):
    tl = (text or "").lower()
    parties = [p for p, kws in _PARTY_KEYWORDS.items() if any(k in tl for k in kws)]
    is_palladam = any(k in tl for k in _REGION_KEYWORDS)
    return parties, is_palladam


class InstagramSpider(scrapy.Spider):
    name = "instagram"
    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60_000,
    }

    def __init__(self, keywords: List[str] = None, max_posts: int = 100, **kwargs):
        super().__init__(**kwargs)
        self.keywords = keywords or ["palladam"]
        self.max_posts = max_posts
        self.results = []  # filled by pipeline

    def start_requests(self):
        for kw in self.keywords:
            tag = kw.lstrip("#").replace(" ", "")
            url = f"https://www.instagram.com/explore/tags/{quote_plus(tag)}/"
            yield scrapy.Request(
                url,
                callback=self.parse_hashtag,
                meta={
                    "playwright": True,
                    "playwright_context": "instagram",
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 3000),
                        PageMethod("evaluate", "window.scrollBy(0, 2000)"),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                    "keyword": kw,
                },
                errback=self.handle_error,
            )

    async def parse_hashtag(self, response):
        page = response.meta.get("playwright_page")
        keyword = response.meta.get("keyword", "")

        try:
            # Extract post links from the page
            links = response.css("article a[href*='/p/']::attr(href)").getall()
            if not links:
                # Try alternate selectors
                links = response.css("a[href*='/p/']::attr(href)").getall()

            seen = set()
            count = 0
            for href in links:
                if count >= self.max_posts:
                    break
                if href in seen:
                    continue
                seen.add(href)
                post_url = f"https://www.instagram.com{href}" if href.startswith("/") else href
                yield scrapy.Request(
                    post_url,
                    callback=self.parse_post,
                    meta={
                        "playwright": True,
                        "playwright_context": "instagram",
                        "playwright_page_methods": [
                            PageMethod("wait_for_timeout", 2000),
                        ],
                        "keyword": keyword,
                    },
                    errback=self.handle_error,
                )
                count += 1

            logger.info(f"Instagram [{keyword}]: found {count} post links")
        finally:
            if page:
                await page.close()

    def parse_post(self, response):
        keyword = response.meta.get("keyword", "")
        url = response.url

        # Extract text from post
        text = (
            response.css('meta[name="description"]::attr(content)').get("")
            or response.css('div[class*="caption"] span::text').getall()
        )
        if isinstance(text, list):
            text = " ".join(text)

        author = response.css('header a[href*="/"]::text').get("")
        post_id = url.rstrip("/").split("/p/")[-1].split("/")[0] if "/p/" in url else hashlib.md5(url.encode()).hexdigest()[:16]

        parties, is_palladam = _classify(text + " " + keyword)

        item = SocialPostItem(
            platform="instagram",
            type="post",
            id=post_id,
            url=url,
            author=author.strip() if author else None,
            text=text.strip() if text else None,
            source="scrapy_instagram",
            timestamp=datetime.utcnow(),
            parties_mentioned=parties,
            is_kongu_related=is_palladam,
        )
        yield item

    def handle_error(self, failure):
        logger.error(f"Instagram spider request failed: {failure.value}")
