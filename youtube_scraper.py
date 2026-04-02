import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from base_scraper import AsyncBaseScraper
from models import SocialMediaRecord
from filters import PartyClassifier, RegionClassifier

logger = logging.getLogger(__name__)

class YouTubeScraper(AsyncBaseScraper):
    """Scraper for YouTube using Scrapling."""

    def __init__(self, headless: bool = True, session_dir: Optional[str] = None):
        super().__init__(headless=headless, session_dir=session_dir)
        self.party_classifier = PartyClassifier()
        self.region_classifier = RegionClassifier()

    async def run(self, keyword: str) -> List[SocialMediaRecord]:
        """Search for a keyword on YouTube and collect video metadata."""
        logger.info(f"Searching YouTube for: {keyword}")
        records = []
        
        try:
            # YouTube search URL
            search_url = f"https://www.youtube.com/results?search_query={keyword}&sp=CAISAggB" # Sorted by upload date
            response = await self.fetch(search_url)
            await self.human_delay(3, 5)
            
            # Scrapling selects video renderers
            video_elements = response.css('ytd-video-renderer')
            logger.info(f"Found {len(video_elements)} videos for keyword: {keyword}")
            
            for video in video_elements:
                try:
                    # Title
                    title = video.css('#video-title::attr(title)').get() or video.css('#video-title::text').get()
                    if not title:
                        continue
                        
                    # Link
                    link = video.css('#video-title::attr(href)').get()
                    full_link = f"https://www.youtube.com{link}" if link else ""
                    
                    # Channel
                    channel = video.css('#channel-info a::text').get()
                    
                    video_id = link.split('=')[-1] if link and '=' in link else f"yt_{hash(title)}"
                    
                    record = SocialMediaRecord(
                        platform="youtube",
                        type="video",
                        id=video_id,
                        url=full_link,
                        title=title,
                        text=f"Title: {title}\nChannel: {channel}",
                        timestamp=datetime.now(),
                        source="scrapling_youtube",
                        parties_mentioned=self.party_classifier.classify_parties(title),
                        is_kongu_related=self.region_classifier.is_kongu_related(text=title)
                    )
                    records.append(record)
                except Exception as e:
                    logger.warning(f"Error parsing video: {e}")
                    
        except Exception as e:
            logger.error(f"YouTube search failed for {keyword}: {e}")
            
        return records