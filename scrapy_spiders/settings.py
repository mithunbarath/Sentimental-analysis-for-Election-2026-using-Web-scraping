"""
Scrapy settings for Palladam Politics Scraper spiders.

Key settings:
  - AutoThrottle    : respects rate limits automatically
  - Random UA       : rotates user-agents to reduce bot fingerprinting
  - Playwright      : enables JS rendering via scrapy-playwright
  - BrightData proxy: injected via DOWNLOADER_MIDDLEWARES
"""

import os

BOT_NAME = "palladam_scraper"
SPIDER_MODULES = ["scrapy_spiders"]
NEWSPIDER_MODULE = "scrapy_spiders"

# ── Crawl politeness ──────────────────────────────────────────────────────────
ROBOTSTXT_OBEY = False         # Social platforms block scrapers via robots.txt anyway
DOWNLOAD_DELAY = 2             # Base delay in seconds between requests
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# ── AutoThrottle (dynamic rate limiting) ─────────────────────────────────────
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 30
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

# ── Retry ─────────────────────────────────────────────────────────────────────
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [403, 429, 500, 502, 503, 504]

# ── Playwright (JS rendering) ─────────────────────────────────────────────────
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ],
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60_000

# ── Middlewares ───────────────────────────────────────────────────────────────
DOWNLOADER_MIDDLEWARES = {
    # BrightData residential proxy (optional — only if BRIGHT_DATA_* env vars set)
    "scrapy_spiders.middlewares.BrightDataProxyMiddleware": 100,
    # Random user-agent rotation
    "scrapy_spiders.middlewares.RandomUserAgentMiddleware": 200,
    # Built-in retry (keep enabled)
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": 550,
}

# ── Item pipelines ────────────────────────────────────────────────────────────
ITEM_PIPELINES = {
    "scrapy_spiders.pipelines.SocialRecordPipeline": 300,
}

# ── Output ────────────────────────────────────────────────────────────────────
# We collect results in memory via the pipeline (no FEEDS needed)
FEEDS = {}

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"

# ── User-agent pool ───────────────────────────────────────────────────────────
USER_AGENT_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]
