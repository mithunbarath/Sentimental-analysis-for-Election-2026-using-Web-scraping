"""
Scraper cascade orchestrator.

Tries each scraping method in priority order for a given platform:
  1. Apify actor (API, no login needed)
  2. Firecrawl API (URL-based supplemental)
  3. BrightData Scraper API (existing implementation)
  4. Playwright-stealth with account credentials (last resort)

Usage:
  from scraper_cascade import CascadeScraper
  cascade = CascadeScraper(config, account_manager)
  records = await cascade.scrape(platform, keywords)
"""

import asyncio
import logging
from typing import List, Optional

from models import SocialMediaRecord

logger = logging.getLogger(__name__)


class CascadeScraper:
    """
    Orchestrates scraping across multiple methods with automatic fallback.
    """

    def __init__(self, config, account_manager=None):
        self._config = config
        self._account_manager = account_manager

    async def scrape(
        self,
        platform: str,
        keywords: List[str],
        sessions_base_dir: str = ".sessions",
    ) -> List[SocialMediaRecord]:
        """
        Scrape platform for keywords using the best available method.
        Falls back through the chain if a method fails or hits limits.

        Returns:
            List[SocialMediaRecord] (posts + comments)
        """
        methods = [
            ("Apify",      self._try_apify),
            ("Firecrawl",  self._try_firecrawl),
            ("BrightData", self._try_brightdata),
            ("Playwright", lambda p, k: self._try_playwright(p, k, sessions_base_dir)),
        ]

        for method_name, method_fn in methods:
            try:
                logger.info(f"[Cascade:{platform}] Trying {method_name}...")
                if asyncio.iscoroutinefunction(method_fn):
                    records = await method_fn(platform, keywords)
                else:
                    records = method_fn(platform, keywords)

                if records:
                    logger.info(
                        f"[Cascade:{platform}] {method_name} succeeded: "
                        f"{len(records)} records."
                    )
                    return records
                else:
                    logger.info(f"[Cascade:{platform}] {method_name} returned 0 results, trying next.")

            except Exception as e:
                err_msg = str(e).lower()
                if any(w in err_msg for w in ["limit", "quota", "rate", "403", "429", "credit"]):
                    logger.warning(
                        f"[Cascade:{platform}] {method_name} hit API limit: {e}. "
                        f"Falling back to next method."
                    )
                else:
                    logger.error(
                        f"[Cascade:{platform}] {method_name} error: {e}. "
                        f"Falling back to next method."
                    )

        logger.warning(f"[Cascade:{platform}] All methods exhausted, returning empty.")
        return []

    # ── Method implementations ────────────────────────────────────────────────

    def _try_apify(self, platform: str, keywords: List[str]) -> List[SocialMediaRecord]:
        """Method 1: Apify API."""
        apify_cfg = getattr(self._config, "apify", None)
        if not apify_cfg or not apify_cfg.enabled:
            return []
        from apify_scraper import scrape_with_apify
        return scrape_with_apify(platform, keywords, apify_cfg)

    def _try_firecrawl(self, platform: str, keywords: List[str]) -> List[SocialMediaRecord]:
        """Method 2: Firecrawl — build URLs from keywords + platform, then scrape."""
        fc_cfg = getattr(self._config, "firecrawl", None)
        if not fc_cfg or not fc_cfg.enabled:
            return []
        from firecrawl_scraper import scrape_urls_with_firecrawl

        # Build search URLs for the platform + keyword combo
        keyword_urls = []
        for kw in keywords:
            encoded = kw.replace(" ", "+")
            if platform == "twitter":
                keyword_urls.append(f"https://nitter.poast.org/search?q={encoded}&f=tweets")
            elif platform == "youtube":
                keyword_urls.append(f"https://www.youtube.com/results?search_query={encoded}")
            # Instagram/Facebook don't have crawlable public search pages
        return scrape_urls_with_firecrawl(fc_cfg, extra_urls=keyword_urls)

    def _try_brightdata(self, platform: str, keywords: List[str]) -> List[SocialMediaRecord]:
        """Method 3: BrightData Scraper API (existing http_client.py logic)."""
        scraper_cfg = getattr(self._config, "scraper_api", None)
        if not scraper_cfg or not scraper_cfg.is_configured:
            return []

        try:
            from http_client import BrightDataClient
            client = BrightDataClient(scraper_cfg)
            records = []
            for keyword in keywords:
                result = client.scrape_platform(platform, keyword)
                if result:
                    records.extend(result)
            return records
        except Exception as e:
            raise  # Let cascade handle it

    async def _try_playwright(
        self,
        platform: str,
        keywords: List[str],
        sessions_base_dir: str,
    ) -> List[SocialMediaRecord]:
        """Method 4: Playwright-stealth with account credential login."""
        from instagram_scraper import InstagramScraper
        from facebook_scraper import FacebookScraper
        from youtube_scraper import YouTubeScraper
        from twitter_scraper import TwitterScraper
        import os

        scraper_map = {
            "instagram": InstagramScraper,
            "facebook": FacebookScraper,
            "youtube": YouTubeScraper,
            "twitter": TwitterScraper,
        }

        scraper_cls = scraper_map.get(platform)
        if not scraper_cls:
            return []

        session_path = os.path.join(sessions_base_dir, platform)
        scraper = scraper_cls(headless=True, session_dir=session_path)

        # Auto-login with account credentials if no session saved
        account = None
        if self._account_manager and not os.path.exists(session_path):
            account = self._account_manager.get_next(platform)

        try:
            await scraper.start()

            # Login with supplied account if needed
            if account:
                await self._auto_login(scraper, platform, account)

            records = []
            for keyword in keywords:
                batch = await scraper.search(keyword)
                records.extend(batch)
            return records

        except Exception as e:
            if account and self._account_manager:
                err_str = str(e).lower()
                if any(w in err_str for w in ["login", "rate", "restricted", "blocked"]):
                    self._account_manager.mark_limited(platform, account["username"])
            raise
        finally:
            try:
                await scraper.stop()
            except Exception:
                pass

    async def _auto_login(self, scraper, platform: str, account: dict):
        """Attempt automatic login using supplied credentials."""
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        login_urls = {
            "instagram": "https://www.instagram.com/accounts/login/",
            "facebook": "https://www.facebook.com/login",
            "twitter": "https://x.com/i/flow/login",
        }
        url = login_urls.get(platform)
        if not url:
            return

        try:
            page = await scraper.get_page()
            await page.goto(url)
            await page.wait_for_timeout(2000)

            if platform == "instagram":
                await page.fill('input[name="username"]', account["username"])
                await page.fill('input[name="password"]', account["password"])
                await page.click('button[type="submit"]')
            elif platform == "facebook":
                await page.fill('#email', account["username"])
                await page.fill('#pass', account["password"])
                await page.click('[name="login"]')
            elif platform == "twitter":
                await page.fill('input[autocomplete="username"]', account["username"])
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1500)
                await page.fill('input[name="password"]', account["password"])
                await page.click('[data-testid="LoginForm_Login_Button"]')

            await page.wait_for_timeout(3000)
            logger.info(f"Auto-login attempted for {platform} account {account['username']}")

        except PlaywrightTimeout:
            logger.warning(f"Auto-login timed out for {platform}")
        except Exception as e:
            logger.warning(f"Auto-login failed for {platform}: {e}")
