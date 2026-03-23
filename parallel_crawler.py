import asyncio
import logging
import os
from typing import List, Dict, Any, Type, Optional
from base_scraper import AsyncBaseScraper
from models import SocialMediaRecord

logger = logging.getLogger(__name__)

class ParallelCrawler:
    """Manages parallel execution of multiple async scrapers with a timeout."""

    def __init__(self, 
                 scraper_classes: List[Type[AsyncBaseScraper]], 
                 keywords: List[str], 
                 timeout_minutes: int = 10,
                 sessions_base_dir: Optional[str] = ".sessions"):
        self.scraper_classes = scraper_classes
        self.keywords = keywords
        self.timeout_seconds = timeout_minutes * 60
        self.sessions_base_dir = sessions_base_dir
        self.all_records: List[SocialMediaRecord] = []
        self.is_running = False

    async def run_scrapers(self, headless: bool = True):
        """Run all scrapers for all keywords."""
        self.is_running = True
        
        # Create scraper instances
        scrapers = []
        for cls in self.scraper_classes:
            platform_name = cls.__name__.replace("Scraper", "").lower()
            session_dir = None
            if self.sessions_base_dir:
                session_dir = os.path.join(self.sessions_base_dir, platform_name)
            
            scrapers.append(cls(headless=headless, session_dir=session_dir))
        
        # Start all browsers
        await asyncio.gather(*(s.start() for s in scrapers))
        
        try:
            # For each platform, run keywords sequentially to avoid session conflicts
            # but run platforms in parallel
            platform_tasks = [self._run_platform_sequence(s) for s in scrapers]
            
            try:
                if platform_tasks:
                    await asyncio.wait_for(asyncio.gather(*platform_tasks), timeout=self.timeout_seconds)
            except asyncio.TimeoutError:
                logger.warning(f"Crawling timed out after {self.timeout_seconds} seconds")
            
        finally:
            # Stop all browsers
            await asyncio.gather(*(s.stop() for s in scrapers))
            self.is_running = False
            logger.info(f"Crawling completed. Total records collected: {len(self.all_records)}")

    async def _run_platform_sequence(self, scraper: AsyncBaseScraper):
        """Run all keywords for a single platform sequentially."""
        for keyword in self.keywords:
            try:
                logger.info(f"Starting {scraper.__class__.__name__} for keyword: {keyword}")
                records = await scraper.run(keyword)
                if records:
                    self.all_records.extend(records)
                    logger.info(f"{scraper.__class__.__name__} found {len(records)} records for keyword: {keyword}")
            except Exception as e:
                logger.error(f"Error in {scraper.__class__.__name__} with keyword {keyword}: {e}")
            
            # Optional: small delay between keywords on same platform
            await asyncio.sleep(2)

    def get_results(self) -> List[SocialMediaRecord]:
        """Return all collected records."""
        return self.all_records
