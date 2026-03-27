"""
Scrapy spider for Twitter/X search via Nitter (public mirror) and
the official search page (Playwright).

Prefers Nitter instances (no login needed) with Twitter direct as fallback.
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

# Public Nitter instances (no login required)
_NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.1d4.us",
]

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


def _extract_count(text: str) -> int | None:
    """Parse '1,234' or '5.6K' into int."""
    if not text:
        return None
    text = text.strip().upper().replace(",", "")
    try:
        if "K" in text:
            return int(float(text.replace("K", "")) * 1000)
        if "M" in text:
            return int(float(text.replace("M", "")) * 1_000_000)
        return int(text)
    except (ValueError, TypeError):
        return None


class TwitterSpider(scrapy.Spider):
    name = "twitter"
    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60_000,
    }

    def __init__(self, keywords: List[str] = None, max_tweets: int = 100, **kwargs):
        super().__init__(**kwargs)
        self.keywords = keywords or ["palladam"]
        self.max_tweets = max_tweets
        self.results = []
        self._nitter_idx = 0

    def _next_nitter(self) -> str:
        base = _NITTER_INSTANCES[self._nitter_idx % len(_NITTER_INSTANCES)]
        self._nitter_idx += 1
        return base

    def start_requests(self):
        for kw in self.keywords:
            nitter = self._next_nitter()
            url = f"{nitter}/search?q={quote_plus(kw)}&f=tweets"
            yield scrapy.Request(
                url,
                callback=self.parse_nitter,
                meta={"keyword": kw, "nitter_base": nitter},
                errback=self.handle_error,
            )

    def parse_nitter(self, response):
        keyword = response.meta.get("keyword", "")

        tweets = response.css("div.timeline-item")
        count = 0
        for tweet in tweets:
            if count >= self.max_tweets:
                break

            text = " ".join(tweet.css("div.tweet-content::text").getall()).strip()
            if not text:
                continue

            author = tweet.css("a.username::text").get("").lstrip("@").strip()
            tweet_link = tweet.css("a.tweet-link::attr(href)").get("")
            tweet_id = tweet_link.rstrip("/").split("/")[-1] if tweet_link else hashlib.md5(text.encode()).hexdigest()[:16]

            like_text = tweet.css("div.icon-heart + span::text, span.icon-heart::text").get("")
            retweet_text = tweet.css("div.icon-retweet + span::text, span.icon-retweet::text").get("")
            reply_text = tweet.css("div.icon-comment + span::text, span.icon-comment::text").get("")

            parties, is_palladam = _classify(text + " " + keyword)

            nitter_base = response.meta.get("nitter_base", _NITTER_INSTANCES[0])
            tweet_url = (
                f"https://twitter.com{tweet_link}"
                if tweet_link.startswith("/")
                else tweet_link
            )

            yield SocialPostItem(
                platform="twitter",
                type="post",
                id=tweet_id,
                url=tweet_url,
                author=author or None,
                text=text,
                like_count=_extract_count(like_text),
                retweet_count=_extract_count(retweet_text),
                reply_count=_extract_count(reply_text),
                source="scrapy_nitter",
                timestamp=datetime.utcnow(),
                parties_mentioned=parties,
                is_palladam_related=is_palladam,
            )
            count += 1

        logger.info(f"Twitter/Nitter [{keyword}]: extracted {count} tweets")

        # Follow "next page" cursor if under limit
        if count < self.max_tweets:
            next_url = response.css("div.show-more a::attr(href)").get()
            if next_url:
                nitter_base = response.meta.get("nitter_base", _NITTER_INSTANCES[0])
                full_next = nitter_base + next_url if next_url.startswith("/") else next_url
                yield scrapy.Request(
                    full_next,
                    callback=self.parse_nitter,
                    meta=response.meta,
                    errback=self.handle_error,
                )

    def handle_error(self, failure):
        logger.error(f"Twitter spider error: {failure.value}")
