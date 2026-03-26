"""
Firecrawl-based supplemental scraper.

Scrapes a list of configured URLs (party websites, news pages, social embeds)
using the Firecrawl API and converts results to SocialMediaRecord objects.

Usage:
  from firecrawl_scraper import scrape_urls_with_firecrawl
  records = scrape_urls_with_firecrawl(config.firecrawl)
"""

import logging
import os
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

from models import SocialMediaRecord

logger = logging.getLogger(__name__)


def _get_app(api_key: Optional[str] = None):
    """Build FirecrawlApp, raising ImportError if package missing."""
    try:
        from firecrawl import FirecrawlApp
    except ImportError:
        raise ImportError(
            "firecrawl-py not installed. Run: pip install firecrawl-py"
        )
    key = api_key or os.getenv("FIRECRAWL_API_KEY", "")
    if not key:
        raise ValueError(
            "No Firecrawl API key. Set FIRECRAWL_API_KEY env var or firecrawl.api_key in config."
        )
    return FirecrawlApp(api_key=key)


def _guess_platform(url: str) -> str:
    """Guess platform name from URL domain."""
    domain = urlparse(url).netloc.lower()
    if "instagram" in domain:
        return "instagram"
    if "facebook" in domain or "fb.com" in domain:
        return "facebook"
    if "twitter" in domain or "x.com" in domain:
        return "twitter"
    if "youtube" in domain or "youtu.be" in domain:
        return "youtube"
    return "news"


def _scrape_one(app, url: str, firecrawl_config) -> Optional[SocialMediaRecord]:
    """Scrape a single URL and return a SocialMediaRecord or None."""
    try:
        result = app.scrape_url(
            url,
            params={
                "formats": ["markdown"],
                "onlyMainContent": True,
                "timeout": 30000,
            }
        )
        markdown = result.get("markdown") or result.get("content") or ""
        metadata = result.get("metadata") or {}
        title = metadata.get("title") or ""

        if not markdown.strip():
            logger.debug(f"Firecrawl: empty content for {url}")
            return None

        platform = _guess_platform(url)
        record = SocialMediaRecord(
            platform=platform,
            type="post",
            id=f"firecrawl_{abs(hash(url))}",
            url=url,
            title=title,
            text=markdown[:5000],   # cap at 5000 chars
            timestamp=datetime.utcnow(),
            source=f"firecrawl_{platform}",
            parties_mentioned=[],
            is_palladam_related="palladam" in markdown.lower()
        )
        return record

    except Exception as e:
        logger.error(f"Firecrawl error for {url}: {e}")
        return None


def scrape_urls_with_firecrawl(
    firecrawl_config,
    extra_urls: Optional[List[str]] = None,
) -> List[SocialMediaRecord]:
    """
    Scrape all URLs in firecrawl_config.urls_to_scrape using Firecrawl API.

    Args:
        firecrawl_config:  FirecrawlConfig dataclass
        extra_urls:        Additional URLs to scrape (merged with config list)

    Returns:
        List of SocialMediaRecord
    """
    if not firecrawl_config.enabled:
        return []

    try:
        app = _get_app(firecrawl_config.api_key)
    except (ImportError, ValueError) as e:
        logger.warning(f"Firecrawl unavailable: {e}")
        return []

    urls = list(firecrawl_config.urls_to_scrape or [])
    if extra_urls:
        urls.extend(extra_urls)

    if not urls:
        logger.info("Firecrawl: no URLs configured.")
        return []

    records: List[SocialMediaRecord] = []
    for url in urls:
        logger.info(f"Firecrawl: scraping {url}")
        rec = _scrape_one(app, url, firecrawl_config)
        if rec:
            records.append(rec)

    logger.info(f"Firecrawl: scraped {len(records)}/{len(urls)} URLs successfully.")
    return records
