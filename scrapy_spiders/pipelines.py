"""
Scrapy item pipeline: converts SocialPostItem → SocialMediaRecord
and collects results in memory for retrieval by scrapy_runner.py.
"""

import logging
from typing import List

from scrapy_spiders.items import SocialPostItem
from models import SocialMediaRecord
from filters import apply_filters

logger = logging.getLogger(__name__)


def _safe_int(val) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


class SocialRecordPipeline:
    """
    Converts each scraped SocialPostItem into a SocialMediaRecord
    and stores it in the spider's `results` list (set by scrapy_runner.py).
    """

    def open_spider(self, spider):
        # The runner injects a shared list via spider.results
        if not hasattr(spider, "results"):
            spider.results = []

    def process_item(self, item: SocialPostItem, spider):
        try:
            record = SocialMediaRecord(
                platform=item.get("platform", "unknown"),
                type=item.get("type", "post"),
                id=item.get("id", ""),
                parent_id=item.get("parent_id"),
                url=item.get("url"),
                author=item.get("author"),
                text=item.get("text"),
                title=item.get("title"),
                like_count=_safe_int(item.get("like_count")),
                reaction_count=_safe_int(item.get("reaction_count")),
                view_count=_safe_int(item.get("view_count")),
                retweet_count=_safe_int(item.get("retweet_count")),
                reply_count=_safe_int(item.get("reply_count")),
                comment_count=_safe_int(item.get("comment_count")),
                source=item.get("source", "scrapy"),
                timestamp=item.get("timestamp"),
                parties_mentioned=item.get("parties_mentioned", []),
                is_palladam_related=bool(item.get("is_palladam_related", False)),
                raw_data=item.get("raw_data"),
            )
            spider.results.append(record)
        except Exception as e:
            logger.warning(f"Pipeline conversion error for item: {e}")
        return item
