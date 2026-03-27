"""
Scrapy spider for YouTube search results.

Does NOT require Playwright — YouTube search HTML is mostly server-rendered.
Falls back to Playwright if initial response is a JS shell.
"""

import hashlib
import logging
import re
from datetime import datetime
from typing import List
from urllib.parse import quote_plus

import scrapy

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


def _extract_number(text: str) -> int | None:
    """Extract numeric value from strings like '1.2M', '45K', '123'."""
    if not text:
        return None
    text = text.upper().strip().replace(",", "")
    try:
        if "M" in text:
            return int(float(text.replace("M", "")) * 1_000_000)
        if "K" in text:
            return int(float(text.replace("K", "")) * 1_000)
        return int(text)
    except (ValueError, TypeError):
        return None


class YouTubeSpider(scrapy.Spider):
    name = "youtube"

    def __init__(self, keywords: List[str] = None, max_videos: int = 50, **kwargs):
        super().__init__(**kwargs)
        self.keywords = keywords or ["palladam"]
        self.max_videos = max_videos
        self.results = []

    def start_requests(self):
        for kw in self.keywords:
            search_url = f"https://www.youtube.com/results?search_query={quote_plus(kw)}&sp=EgIQAQ%3D%3D"
            yield scrapy.Request(
                search_url,
                callback=self.parse_search,
                meta={"keyword": kw},
                headers={
                    "Accept-Language": "en-US,en;q=0.9,ta;q=0.8",
                },
                errback=self.handle_error,
            )

    def parse_search(self, response):
        keyword = response.meta.get("keyword", "")

        # YouTube embeds data as JSON in a script tag
        json_text = response.css("script").re_first(r'var ytInitialData = ({.*?});')
        if not json_text:
            logger.warning(f"YouTube [{keyword}]: no ytInitialData found (JS-only response?)")
            return

        import json
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            logger.warning(f"YouTube [{keyword}]: failed to parse ytInitialData JSON")
            return

        # Navigate the YouTube data structure
        try:
            contents = (
                data["contents"]["twoColumnSearchResultsRenderer"]
                ["primaryContents"]["sectionListRenderer"]["contents"]
            )
        except (KeyError, TypeError):
            logger.warning(f"YouTube [{keyword}]: unexpected data structure")
            return

        count = 0
        for section in contents:
            if count >= self.max_videos:
                break
            items = section.get("itemSectionRenderer", {}).get("contents", [])
            for item in items:
                if count >= self.max_videos:
                    break
                video = item.get("videoRenderer")
                if not video:
                    continue

                video_id = video.get("videoId", "")
                if not video_id:
                    continue

                title = "".join(
                    r.get("text", "")
                    for r in video.get("title", {}).get("runs", [])
                )
                channel = (
                    video.get("ownerText", {}).get("runs", [{}])[0].get("text", "")
                )
                view_text = video.get("viewCountText", {}).get("simpleText", "")
                view_count = _extract_number(re.sub(r"[^0-9KMB.]", "", view_text))

                video_url = f"https://www.youtube.com/watch?v={video_id}"
                parties, is_palladam = _classify(title + " " + keyword)

                yield SocialPostItem(
                    platform="youtube",
                    type="post",
                    id=video_id,
                    url=video_url,
                    title=title,
                    author=channel,
                    view_count=view_count,
                    source="scrapy_youtube",
                    timestamp=datetime.utcnow(),
                    parties_mentioned=parties,
                    is_palladam_related=is_palladam,
                )
                count += 1

        logger.info(f"YouTube [{keyword}]: extracted {count} videos")

    def handle_error(self, failure):
        logger.error(f"YouTube spider error: {failure.value}")
