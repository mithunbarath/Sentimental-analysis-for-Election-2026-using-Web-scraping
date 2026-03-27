"""
Scrapy Runner — asyncio bridge for running Scrapy spiders from main.py.

Scrapy uses Twisted's reactor internally. To run it from asyncio (used by
Playwright/Scrapling elsewhere in this project), we launch Scrapy in a
dedicated thread with its own Twisted reactor, collect results via a shared
list, and return them to the asyncio caller when the crawl finishes.

Usage:
    from scrapy_runner import run_scrapy_spiders
    records = await run_scrapy_spiders(
        platforms=["instagram", "facebook", "youtube", "twitter"],
        keywords=["palladam", "dmk"],
        config=cfg,
    )
"""

import asyncio
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from models import SocialMediaRecord

logger = logging.getLogger(__name__)

# Maps platform names → spider classes
_SPIDER_MAP = {
    "instagram": "scrapy_spiders.instagram_spider.InstagramSpider",
    "facebook":  "scrapy_spiders.facebook_spider.FacebookSpider",
    "youtube":   "scrapy_spiders.youtube_spider.YouTubeSpider",
    "twitter":   "scrapy_spiders.twitter_spider.TwitterSpider",
}


def _run_crawl_sync(platforms: List[str], keywords: List[str], config) -> List[SocialMediaRecord]:
    """
    Synchronous crawl — runs inside a worker thread (not the asyncio thread).

    Scrapy's CrawlerProcess manages its own Twisted reactor, so it must be
    isolated from asyncio's reactor running in the main thread.
    """
    try:
        from scrapy.crawler import CrawlerProcess
        from scrapy.utils.project import get_project_settings
        import scrapy_spiders.settings as spider_settings_module
    except ImportError as e:
        logger.error(f"Scrapy not installed: {e}. Run: pip install Scrapy>=2.11.0")
        return []

    # Build Scrapy settings from our settings module
    settings_dict = {
        k: getattr(spider_settings_module, k)
        for k in dir(spider_settings_module)
        if k.isupper()
    }

    # Override proxy / UA from environment (already loaded by dotenv in main.py)
    all_results: List[SocialMediaRecord] = []

    try:
        process = CrawlerProcess(settings=settings_dict)

        spider_import_map = {
            "instagram": ("scrapy_spiders.instagram_spider", "InstagramSpider"),
            "facebook":  ("scrapy_spiders.facebook_spider",  "FacebookSpider"),
            "youtube":   ("scrapy_spiders.youtube_spider",   "YouTubeSpider"),
            "twitter":   ("scrapy_spiders.twitter_spider",   "TwitterSpider"),
        }

        crawlers = {}
        for platform in platforms:
            if platform not in spider_import_map:
                continue
            module_path, class_name = spider_import_map[platform]
            try:
                import importlib
                mod = importlib.import_module(module_path)
                spider_cls = getattr(mod, class_name)
            except Exception as e:
                logger.error(f"Cannot import spider for {platform}: {e}")
                continue

            # Spider-specific kwargs
            kwargs: dict = {"keywords": keywords}
            if platform == "facebook" and hasattr(config, "facebook"):
                kwargs["page_urls"] = getattr(config.facebook, "page_urls", [])

            crawler = process.create_crawler(spider_cls)
            crawlers[platform] = crawler
            process.crawl(crawler, **kwargs)

        # Run all crawlers (blocks until done)
        process.start(stop_after_crawl=True)

        # Collect results from each crawled spider
        for platform, crawler in crawlers.items():
            spider = crawler.spider
            if spider and hasattr(spider, "results"):
                batch = spider.results
                logger.info(f"Scrapy [{platform}]: collected {len(batch)} records")
                all_results.extend(batch)

    except Exception as e:
        logger.error(f"Scrapy crawl error: {e}")

    return all_results


async def run_scrapy_spiders(
    platforms: List[str],
    keywords: List[str],
    config=None,
    timeout_minutes: int = 10,
) -> List[SocialMediaRecord]:
    """
    Async wrapper — runs the Scrapy crawl in a thread pool and awaits it.

    Args:
        platforms       : List of platform names to crawl.
        keywords        : Search keywords.
        config          : Config object (for platform-specific settings).
        timeout_minutes : Max minutes to wait before giving up.

    Returns:
        List of SocialMediaRecord objects.
    """
    loop = asyncio.get_event_loop()
    logger.info(f"Starting Scrapy crawl: platforms={platforms}, keywords={keywords}")

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = loop.run_in_executor(
                executor,
                _run_crawl_sync,
                platforms,
                keywords,
                config,
            )
            records = await asyncio.wait_for(
                future, timeout=timeout_minutes * 60
            )
        logger.info(f"Scrapy crawl complete: {len(records)} total records")
        return records
    except asyncio.TimeoutError:
        logger.warning(f"Scrapy crawl timed out after {timeout_minutes} minutes")
        return []
    except Exception as e:
        logger.error(f"Scrapy runner error: {e}")
        return []
