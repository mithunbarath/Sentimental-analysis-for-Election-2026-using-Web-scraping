import asyncio
import logging
import random
import os
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from scrapling.fetchers import AsyncStealthySession
from scrapling.engines.toolbelt.custom import Response

logger = logging.getLogger(__name__)

class AsyncBaseScraper:
    """Base class for asynchronous scrapers using Scrapling."""

    def __init__(self, headless: bool = True, session_dir: Optional[str] = None):
        self.headless = headless
        self.session_dir = session_dir
        self.session: Optional[AsyncStealthySession] = None

    async def start(self):
        """Initialize the Scrapling session."""
        if self.session_dir:
            os.makedirs(self.session_dir, exist_ok=True)
            
        self.session = AsyncStealthySession(
            headless=self.headless,
            user_data_dir=self.session_dir,
            solve_cloudflare=True,
            network_idle=True,
            timeout=60000
        )
        # Session is an async context manager, but we want to keep it open
        await self.session.__aenter__()
        logger.debug(f"Scrapling session started (headless={self.headless}, persistent={bool(self.session_dir)})")

    async def stop(self):
        """Close the Scrapling session."""
        if self.session:
            await self.session.__aexit__(None, None, None)
        logger.debug("Scrapling session stopped")

    async def fetch(self, url: str, wait_selector: Optional[str] = None) -> Response:
        """Fetch a URL using the active session."""
        if not self.session:
            await self.start()
            
        kwargs = {}
        if wait_selector:
            kwargs["wait_selector"] = wait_selector
            
        logger.debug(f"Fetching URL: {url}")
        return await self.session.fetch(url, **kwargs)

    async def get_page(self):
        """Get the internal Playwright page object (for manual login)."""
        if not self.session:
            await self.start()
        # In Scrapling 0.4.x, AsyncStealthySession has an 'engine' which has a 'page'
        return self.session.engine.page

    async def scroll_to_bottom(self, page_action_context, max_scrolls: int = 10, delay: float = 1.5):
        """
        Scroll to the bottom. 
        Note: Scrapling handles most scrolling via its internal engines, 
        but we can provide a page_action if needed.
        """
        # Scrapling's AsyncStealthySession.fetch returns a Response which has a Selector.
        # For actual scrolling, we usually use page_action in fetch().
        pass

    async def human_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Simulate human-like delay."""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    async def run(self, keyword: str):
        """Main scraping logic for a specific keyword. To be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement run()")
