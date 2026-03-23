import asyncio
import logging
import random
import os
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from scrapling import Selector
from scrapling.fetchers import AsyncStealthySession
from scrapling.engines.toolbelt.custom import Response

logger = logging.getLogger(__name__)

class AsyncBaseScraper:
    """Base class for asynchronous scrapers using Scrapling."""

    def __init__(self, headless: bool = True, session_dir: Optional[str] = None):
        import platform
        # On Windows, persistent contexts often crash in headless mode (exitCode 21)
        # We force headless=False if a session_dir is provided on Windows.
        if platform.system() == "Windows" and session_dir:
            self.headless = False
        else:
            self.headless = headless
            
        self.session_dir = session_dir
        self.session: Optional[AsyncStealthySession] = None
        self._start_lock = asyncio.Lock()

    async def start(self):
        """Initialize the Scrapling session with a lock for concurrency safety."""
        async with self._start_lock:
            if self.session:
                return
                
            if self.session_dir:
                os.makedirs(self.session_dir, exist_ok=True)
                
            # Enhanced stealth configuration
            # If we have a session_dir, we already logged in manually, so we don't 
            # want scrapling's aggressive cloudflare solver to potentially break the session.
            self.session = AsyncStealthySession(
                headless=self.headless,
                user_data_dir=self.session_dir,
                solve_cloudflare=not bool(self.session_dir), # Disable if session exists
                network_idle=False, # Disable to speed up and avoid hangs
                timeout=90000, 
                extra_args=[
                    "--disable-gpu", 
                    "--disable-software-rasterizer", 
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            # Session is an async context manager, but we want to keep it open
            # We must use start() manually since we don't use 'async with' here
            await self.session.start()
            logger.debug(f"Scrapling session started (headless={self.headless}, persistent={bool(self.session_dir)})")

    async def save_debug_screenshot(self, name: str):
        """Save a screenshot and page info for debugging purposes."""
        if not self.session:
            return
            
        try:
            page = await self.get_page()
            title = await page.title()
            url = page.url
            logger.info(f"Debug Info for {name}: URL={url}, Title='{title}'")
            
            content = await page.content()
            content_lower = content.lower()
            logger.info(f"Page content snippet (first 500 chars): {content[:500]}...")
            
            if "login" in content_lower or "signin" in content_lower:
                logger.warning(f"Likely login wall detected on {url}")
            elif "captcha" in content_lower or "robot" in content_lower:
                logger.warning(f"Likely captcha/bot detection on {url}")
            
            # Save screenshot
            debug_dir = os.path.join(os.getcwd(), "debug_screenshots")
            os.makedirs(debug_dir, exist_ok=True)
            path = os.path.join(debug_dir, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            await page.screenshot(path=path)
            logger.debug(f"Debug screenshot saved to {path}")
        except Exception as e:
            logger.warning(f"Failed to save debug info: {e}")

    async def stop(self):
        """Close the Scrapling session."""
        if self.session:
            await self.session.__aexit__(None, None, None)
        logger.debug("Scrapling session stopped")

    async def fetch(self, url: str, wait_selector: Optional[str] = None) -> Selector:
        """Fetch a URL using the browser page directly for better rendering."""
        if not self.session:
            await self.start()
            
        try:
            page = await self.get_page()
            logger.debug(f"Navigating browser to: {url}")
            
            # Using page.goto directly to ensure SPA rendering
            await page.goto(url, wait_until="load", timeout=60000)
            
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    logger.warning(f"Timeout waiting for selector: {wait_selector} on {url}")
            
            # Allow some extra time for dynamic content
            await asyncio.sleep(2)
            
            content = await page.content()
            return Selector(content)
        except Exception as e:
            logger.error(f"Browser navigation failed for {url}: {e}")
            # Fallback to scrapling fetch if browser navigation fails
            logger.info(f"Falling back to scrapling internal fetch for {url}...")
            try:
                response = await self.session.fetch(url, timeout=60000)
                # Ensure the fallback also returns a Selector object
                return Selector(response.content)
            except Exception as fallback_e:
                logger.error(f"Fallback scrapling fetch also failed for {url}: {fallback_e}")
                raise fallback_e

    async def get_page(self):
        """Get the internal Playwright page object (for manual login)."""
        if not self.session:
            await self.start()
            
        # Scrapling's AsyncStealthySession has a 'context' attribute which is a Playwright BrowserContext
        # Persistent contexts usually have one default page open.
        pages = self.session.context.pages
        if pages:
            return pages[0]
        return await self.session.context.new_page()

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
