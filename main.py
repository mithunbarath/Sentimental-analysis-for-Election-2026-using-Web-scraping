import sys
import asyncio

# Windows-specific event loop policy for Playwright/Scrapling
# This MUST be set before any other imports that might use asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import argparse
import logging
import os
from pathlib import Path
from typing import List, Optional, Type, Dict

from config import Config, load_config
from models import SocialMediaRecord
from filters import apply_filters
from instagram_scraper import InstagramScraper
from facebook_scraper import FacebookScraper
from youtube_scraper import YouTubeScraper
from twitter_scraper import TwitterScraper
from parallel_crawler import ParallelCrawler
from exporter import export_all, generate_summary_stats, export_to_sheets_if_configured

# Fix Windows console encoding for Tamil characters
if sys.platform == "win32":
    # Python 3.7+ approach is more stable than codecs.getwriter
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

# Set logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraper.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Parallel Social Media Scrapper for TN Politics (Palladam Focused)"
    )
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--platforms", type=str, nargs="+", choices=["instagram", "facebook", "youtube", "twitter", "all"])
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--no-filter", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Enable strict filtering (exclude non-explicit matches)")
    parser.add_argument("--broad-search", action="store_true", help="Use broad TN political keywords")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout in minutes")
    parser.add_argument("--keywords", type=str, nargs="+", help="Override keywords from config")
    parser.add_argument("--login", type=str, choices=["instagram", "facebook", "youtube", "twitter"], help="Login to a specific platform manually")
    parser.add_argument("--sessions-dir", type=str, default=".sessions", help="Directory to store session data")
    return parser.parse_args()

async def run_login_mode(platform: str, sessions_dir: str):
    """Run a visible browser for manual login to a platform."""
    logger.info(f"Starting login mode for {platform}...")
    
    platform_map = {
        "instagram": (InstagramScraper, "https://www.instagram.com/accounts/login/"),
        "twitter": (TwitterScraper, "https://x.com/i/flow/login"),
        "facebook": (FacebookScraper, "https://www.facebook.com/login"),
        "youtube": (YouTubeScraper, "https://accounts.google.com/ServiceLogin?service=youtube")
    }
    
    if platform not in platform_map:
        logger.error(f"Platform {platform} not supported for login")
        return

    scraper_cls, login_url = platform_map[platform]
    session_path = os.path.join(os.getcwd(), sessions_dir, platform)
    
    scraper = scraper_cls(headless=False, session_dir=session_path)
    await scraper.start()
    
    page = await scraper.get_page()
    await page.goto(login_url)
    
    logger.info("=" * 70)
    logger.info(f"PLEASE LOG IN TO {platform.upper()} IN THE BROWSER WINDOW.")
    logger.info("After you have successfully logged in, come back here and press ENTER.")
    logger.info("=" * 70)
    
    # Wait for user to press ENTER in the terminal
    await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
    
    await scraper.stop()
    logger.info(f"Login session saved for {platform} at {session_path}")

async def main_async():
    """Asynchronous main function."""
    args = parse_arguments()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.login:
        await run_login_mode(args.login, args.sessions_dir)
        return

    logger.info("=" * 70)
    logger.info("Tamil Nadu & Palladam Politics Scraper - Starting")
    logger.info("=" * 70)

    try:
        config_path = Path(args.config)
        config = load_config(str(config_path)) if config_path.exists() else Config()
        if args.platforms:
            if "all" in args.platforms:
                config.enable_which_platforms = ["instagram", "facebook", "youtube", "twitter"]
            else:
                config.enable_which_platforms = args.platforms
        if args.output_dir:
            config.export.output_dir = args.output_dir
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        sys.exit(1)

    # Keywords to search
    keywords = args.keywords or []
    if not keywords:
        # Collect broad or specific keywords based on settings
        if "instagram" in config.enable_which_platforms:
            keywords.extend([url.split('/')[-2].replace('tags/', '') for url in config.instagram.hashtag_urls if '/explore/' in url])
        if "twitter" in config.enable_which_platforms:
            keywords.extend(config.twitter.search_queries)
            
        if not args.broad_search:
            # Filter down to Palladam specific if not in broad search mode
            keywords = [k for k in keywords if "palladam" in k.lower() or "பல்லடம்" in k]
            
        if not keywords:
            keywords = ["palladam", "dmk", "admk", "tvk"] if args.broad_search else ["palladam"]
    
    keywords = list(set(keywords))
    logger.info(f"Target keywords ({'Broad' if args.broad_search else 'Specific'}): {', '.join(keywords)}")

    def refine_keywords_for_platform(platform: str, original_keywords: List[str]) -> List[str]:
        """Split keywords with 'OR' for platforms that don't support boolean logic."""
        if platform in ["youtube", "twitter"]:
            return original_keywords
            
        refined = []
        for k in original_keywords:
            if " OR " in k:
                # Split by ' OR ' and add individual terms
                parts = [p.strip() for p in k.split(" OR ") if p.strip()]
                refined.extend(parts)
            else:
                refined.append(k)
        return list(set(refined))

    # Check for sessions
    enabled_platforms = config.enable_which_platforms
    for platform in enabled_platforms:
        session_path = os.path.join(args.sessions_dir, platform)
        if not os.path.exists(session_path):
            if platform in ["instagram", "facebook", "twitter"]:
                logger.warning(f"No saved session found for {platform} at {session_path}. "
                             f"Manual scraping may fail or be restricted. "
                             f"Consider running: python main.py --login {platform}")
        else:
            logger.info(f"Using saved session for {platform} from {session_path}")

    platform_map = {
        "instagram": InstagramScraper,
        "facebook": FacebookScraper,
        "youtube": YouTubeScraper,
        "twitter": TwitterScraper
    }
    
    scraper_classes = [platform_map[p] for p in config.enable_which_platforms if p in platform_map]
    
    crawler = ParallelCrawler(
        scraper_classes=scraper_classes,
        keywords=keywords,
        timeout_minutes=args.timeout,
        sessions_base_dir=args.sessions_dir
    )
    
    logger.info(f"Starting parallel crawl with {len(scraper_classes)} platforms.")
    await crawler.run_scrapers()
    all_records = crawler.get_results()

    if all_records:
        if not args.no_filter:
            logger.info("Applying keyword and region filters...")
            all_records = apply_filters(
                all_records, 
                require_party_mention=True, 
                require_palladam_related=True,
                strict_mode=args.strict
            )
            logger.info(f"Records after filtering: {len(all_records)}")

        # Group and Sort
        all_records.sort(key=lambda x: (x.platform, x.timestamp), reverse=True)

        try:
            csv_path = config.export.csv_path
            jsonl_path = config.export.jsonl_path
            export_all(all_records, str(csv_path), str(jsonl_path))
            logger.info(f"Data exported to {csv_path}")
        except Exception as e:
            logger.error(f"Error exporting data: {e}")

        try:
            stats = generate_summary_stats(all_records)
            logger.info("Summary Statistics:")
            logger.info(f"  Total: {stats['total_records']}")
            logger.info(f"  Palladam-related: {stats['palladam_related_count']}")
        except Exception as e:
            logger.error(f"Error generating statistics: {e}")

        # ── Google Sheets export (optional) ────────────────────────────────
        try:
            sheets_result = export_to_sheets_if_configured(all_records, config.google_sheets)
            if sheets_result is not None:
                logger.info(f"Google Sheets export: {sheets_result} rows written.")
            else:
                logger.info(
                    "Google Sheets export skipped. "
                    "Set google_sheets.enabled: true in config.yaml to enable."
                )
        except Exception as e:
            logger.error(f"Google Sheets export error: {e}")

    logger.info("Scraping process finished.")

if __name__ == "__main__":
    # Explicit loop management for Windows stability
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main_async())
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting...")
    finally:
        try:
            # Cleanup pending tasks
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        loop.close()