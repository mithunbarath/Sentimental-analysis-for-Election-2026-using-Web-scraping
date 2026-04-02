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
        description="Parallel Social Media Scrapper for TN Politics (Kongu Focused)"
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
    # ── Infinite / continuous mode ──
    parser.add_argument("--infinite", action="store_true", help="Run scraper in infinite loop")
    parser.add_argument("--delay", type=int, default=None, help="Minutes between runs in infinite mode (overrides config)")
    # ── API integrations ──
    parser.add_argument("--apify", action="store_true", help="Enable Apify API scraping")
    parser.add_argument("--firecrawl", action="store_true", help="Enable Firecrawl URL scraping")
    parser.add_argument("--cascade", action="store_true", help="Use cascading fallback scraper (Apify→Firecrawl→BrightData→Playwright)")
    parser.add_argument("--scrapy", action="store_true", help="Enable Scrapy spider layer (supplemental deep crawl)")
    parser.add_argument("--tn-wide", action="store_true", help="Enable TN-wide scraping (disable Kongu-only filter)")
    parser.add_argument("--store-all", action="store_true", help="Store all records, ignoring region filters")
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
    logger.info("Kongu Region Politics Scraper - Starting")
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
            # Filter down to Kongu specific if not in broad search mode
            keywords = [k for k in keywords if "kongu" in k.lower() or "கொங்கு" in k or "coimbatore" in k.lower() or "tirup" in k.lower() or "salem" in k.lower() or "erode" in k.lower()]
            
            keywords = ["kongu", "dmk", "admk", "tvk", "coimbatore", "tiruppur"] if args.broad_search else ["kongu", "coimbatore", "tiruppur", "erode", "salem"]
    
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
                require_kongu_related=True,
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
            logger.info(f"  Kongu-related: {stats['kongu_related_count']}")
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
    return all_records


async def run_one_cycle(args, config) -> List[SocialMediaRecord]:
    """
    Run a single full scrape cycle:
     1. Playwright / existing scrapers (parallel crawler)
     2. Cascade (Apify → Firecrawl → BrightData → Playwright) if --cascade
     3. Firecrawl supplemental URLs if --firecrawl
    Exports results to CSV/JSONL and Google Sheets.
    Returns the list of all records collected this cycle.
    """
    import time
    from scraper_cascade import CascadeScraper
    from account_manager import AccountManager

    # ---- resolve config ----
    cfg = config
    keywords = args.keywords or None

    # Enable Apify / Firecrawl via CLI override
    if args.apify and hasattr(cfg, "apify"):
        cfg.apify.enabled = True
    if args.firecrawl and hasattr(cfg, "firecrawl"):
        cfg.firecrawl.enabled = True

    account_mgr = AccountManager(getattr(cfg, "accounts", None))

    all_records: List[SocialMediaRecord] = []

    # ---- Step 1: existing parallel crawler ----
    platforms = cfg.enable_which_platforms
    scraper_map = {
        "instagram": InstagramScraper,
        "facebook": FacebookScraper,
        "youtube": YouTubeScraper,
        "twitter": TwitterScraper,
    }
    scraper_classes = [scraper_map[p] for p in platforms if p in scraper_map]

    # Build keywords the same way main_async does
    if not keywords:
        kw_list = []
        if "instagram" in platforms:
            kw_list.extend([
                url.split('/')[-2].replace('tags/', '')
                for url in cfg.instagram.hashtag_urls if '/explore/' in url
            ])
        if "twitter" in platforms:
            kw_list.extend(cfg.twitter.search_queries)
        if not args.broad_search:
            kw_list = [k for k in kw_list if "kongu" in k.lower() or "coimbatore" in k.lower() or "tirup" in k.lower() or "erode" in k.lower()]
        if not kw_list:
            kw_list = (
                ["kongu", "dmk", "admk", "tvk", "eps", "vijay", "stalin", "coimbatore", "tiruppur", "erode"]
                if args.broad_search else ["kongu", "coimbatore", "tiruppur"]
            )
        keywords = list(set(kw_list))

    sessions_base = os.path.join(os.getcwd(), args.sessions_dir)

    if scraper_classes:
        crawler = ParallelCrawler(
            scraper_classes=scraper_classes,
            keywords=keywords,
            timeout_minutes=args.timeout,
            sessions_base_dir=sessions_base,
        )
        await crawler.run_scrapers()
        all_records.extend(crawler.get_results())


    # ---- Step 2: cascade per platform ----
    if args.cascade or (args.apify and hasattr(cfg, "apify") and cfg.apify.enabled):
        cascade = CascadeScraper(cfg, account_mgr)
        kws = keywords or (["kongu", "dmk", "admk", "tvk"] if not args.broad_search else
                           ["kongu", "dmk", "admk", "tvk", "eps", "vijay", "stalin", "coimbatore", "tiruppur", "erode"])
        for platform in platforms:
            try:
                batch = await cascade.scrape(platform, kws, args.sessions_dir)
                all_records.extend(batch)
                logger.info(f"Cascade [{platform}]: {len(batch)} records")
            except Exception as e:
                logger.error(f"Cascade error [{platform}]: {e}")

    # ---- Step 3: Firecrawl supplemental ----
    if args.firecrawl and hasattr(cfg, "firecrawl") and cfg.firecrawl.enabled:
        try:
            from firecrawl_scraper import scrape_urls_with_firecrawl
            fc_records = scrape_urls_with_firecrawl(cfg.firecrawl)
            all_records.extend(fc_records)
            logger.info(f"Firecrawl supplemental: {len(fc_records)} records")
        except Exception as e:
            logger.error(f"Firecrawl error: {e}")

    # ---- Step 4: Scrapy spider layer (supplemental deep crawl) ----
    if getattr(args, "scrapy", False):
        try:
            from scrapy_runner import run_scrapy_spiders
            scrapy_timeout = max(args.timeout - 2, 3)
            scrapy_records = await run_scrapy_spiders(
                platforms=platforms,
                keywords=keywords,
                config=cfg,
                timeout_minutes=scrapy_timeout,
            )
            all_records.extend(scrapy_records)
            logger.info(f"Scrapy layer: {len(scrapy_records)} records")
        except Exception as e:
            logger.error(f"Scrapy runner error: {e}")

    if not all_records:
        logger.info("No records collected this cycle.")
        return []

    # ---- NLP Enrichment ----
    try:
        from nlp_pipeline import enrich_if_configured
        all_records = enrich_if_configured(all_records, cfg.nlp, rolling_window=None)
    except Exception as e:
        logger.error(f"NLP enrichment error: {e}")

    # ---- Region Tagging ----
    try:
        from filters import tag_regions
        logger.info("Tagging regions...")
        all_records = tag_regions(all_records)
    except Exception as e:
        logger.error(f"Region tagging error: {e}")

    # ---- Filter ----
    if not args.no_filter:
        logger.info("Applying filters...")
        all_records = apply_filters(
            all_records,
            require_party_mention=True,
            require_kongu_related=not args.tn_wide,
            tn_wide_mode=args.tn_wide,
            store_all=args.store_all,
            strict_mode=args.strict
        )
        logger.info(f"Records after filtering: {len(all_records)}")

    all_records.sort(key=lambda x: (x.platform, x.timestamp or ""), reverse=True)

    # ---- Export CSV/JSONL ----
    try:
        export_all(all_records, str(cfg.export.csv_path), str(cfg.export.jsonl_path))
        logger.info(f"Exported {len(all_records)} records to {cfg.export.csv_path}")
        
        if getattr(cfg.export, "per_region_csv", False):
            from exporter import export_by_region
            export_by_region(all_records, getattr(cfg.export, "output_dir", "output"))
    except Exception as e:
        logger.error(f"CSV/JSONL export error: {e}")

    # ---- Stats ----
    try:
        stats = generate_summary_stats(all_records)
        logger.info(f"Summary — Total: {stats['total_records']}  Kongu-related: {stats['kongu_related_count']}")
    except Exception as e:
        logger.error(f"Stats error: {e}")

    # ---- Google Sheets ----
    try:
        sheets_result = export_to_sheets_if_configured(all_records, cfg.google_sheets)
        if sheets_result is not None:
            logger.info(f"Google Sheets: {sheets_result} rows written.")
    except Exception as e:
        logger.error(f"Google Sheets error: {e}")

    # ---- MongoDB Upsert ----
    try:
        from mongo_exporter import export_to_mongo_if_configured
        mongo_result = await export_to_mongo_if_configured(all_records, cfg.mongodb)
        if mongo_result is not None:
            logger.info(f"MongoDB: {mongo_result} new records upserted.")
        else:
            logger.info(
                "MongoDB export skipped. "
                "Set mongodb.enabled: true and MONGODB_URI in .env to enable."
            )
    except Exception as e:
        logger.error(f"MongoDB export error: {e}")

    # ---- Firebase Export ----
    try:
        if hasattr(cfg, "firebase"):
            from exporter import export_to_firestore_if_configured
            firebase_result = export_to_firestore_if_configured(all_records, cfg.firebase)
            if firebase_result is not None:
                logger.info(f"Firebase: {firebase_result} new records exported.")
    except Exception as e:
        logger.error(f"Firebase export error: {e}")

    return all_records

if __name__ == "__main__":
    import time

    async def run():
        args = parse_arguments()
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        if args.login:
            await run_login_mode(args.login, args.sessions_dir)
            return

        logger.info("=" * 70)
        logger.info("Kongu Region Politics Scraper - Starting")
        logger.info("=" * 70)

        try:
            config_path = Path(args.config)
            config = load_config(str(config_path)) if config_path.exists() else Config()
        except Exception as e:
            logger.critical(f"Failed to load config: {e}")
            return

        if args.platforms:
            config.enable_which_platforms = (
                ["instagram", "facebook", "youtube", "twitter"]
                if "all" in args.platforms else args.platforms
            )
        if args.output_dir:
            config.export.output_dir = args.output_dir

        # Determine delay for infinite mode
        inf_cfg = getattr(config, "infinite_mode", None)
        delay_minutes = args.delay if args.delay is not None else (
            getattr(inf_cfg, "delay_minutes", 30) if inf_cfg else 30
        )
        max_runs = getattr(inf_cfg, "max_runs", 0) if inf_cfg else 0

        run_count = 0
        while True:
            run_count += 1
            cycle_label = f"Run #{run_count}" if args.infinite else "Single run"
            logger.info(f"\n{'='*70}\n{cycle_label} starting at {time.strftime('%Y-%m-%d %H:%M:%S')}\n{'='*70}")

            try:
                await run_one_cycle(args, config)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"{cycle_label} error: {e}")

            if not args.infinite:
                break
            if max_runs and run_count >= max_runs:
                logger.info(f"Reached max_runs={max_runs}. Stopping.")
                break

            logger.info(f"Next run in {delay_minutes} minutes. Press Ctrl+C to stop.")
            await asyncio.sleep(delay_minutes * 60)

        logger.info("All scraping runs completed.")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting cleanly.")
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        loop.close()