"""
Configuration module for the Palladam Politics Scraper.

This module handles loading configuration from YAML files and environment variables.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ScraperApiConfig:
    """Configuration for Bright Data Scraper API settings."""

    api_token: str = field(default_factory=lambda: os.getenv("BRIGHT_DATA_API_TOKEN", ""))
    
    # Default collector IDs (can be overridden in config.yaml)
    instagram_collector: str = "c_instagram_posts"
    facebook_collector: str = "c_facebook_posts"
    youtube_collector: str = "c_youtube_videos"
    twitter_collector: str = "c_twitter_posts"
    
    # Whether to use Scraper API instead of manual scraping
    use_scraper_api: bool = True

    @property
    def is_configured(self) -> bool:
        """Check if Scraper API is properly configured."""
        return bool(self.api_token)


@dataclass
class BrightDataConfig:
    """Configuration for Bright Data proxy settings."""


    proxy_host: str = field(default_factory=lambda: os.getenv("BRIGHT_DATA_PROXY_HOST", ""))
    proxy_port: int = field(default_factory=lambda: int(os.getenv("BRIGHT_DATA_PROXY_PORT", "33335")))
    username: str = field(default_factory=lambda: os.getenv("BRIGHT_DATA_USERNAME", ""))
    password: str = field(default_factory=lambda: os.getenv("BRIGHT_DATA_PASSWORD", ""))

    @property
    def proxy_url(self) -> Optional[str]:
        """Return the formatted proxy URL if credentials are configured."""
        if not all([self.proxy_host, self.username, self.password]):
            return None
        return f"http://{self.username}:{self.password}@{self.proxy_host}:{self.proxy_port}"

    @property
    def is_configured(self) -> bool:
        """Check if Bright Data proxy is properly configured."""
        return bool(self.proxy_url)


@dataclass
class InstagramConfig:
    """Instagram scraper configuration."""

    hashtag_urls: List[str] = field(default_factory=list)
    profile_urls: List[str] = field(default_factory=list)
    max_posts_per_source: int = 50
    max_comments_per_post: int = 20
    min_delay: float = 1.0
    max_delay: float = 3.0


@dataclass
class FacebookConfig:
    """Facebook scraper configuration."""

    page_urls: List[str] = field(default_factory=list)
    group_urls: List[str] = field(default_factory=list)
    max_posts_per_source: int = 50
    max_comments_per_post: int = 20
    min_delay: float = 2.0
    max_delay: float = 5.0


@dataclass
class YouTubeConfig:
    """YouTube scraper configuration."""

    api_key: str = field(default_factory=lambda: os.getenv("YOUTUBE_API_KEY", ""))
    channel_urls: List[str] = field(default_factory=list)
    video_urls: List[str] = field(default_factory=list)
    max_videos_per_channel: int = 30
    max_comments_per_video: int = 50
    min_delay: float = 1.0
    max_delay: float = 3.0

    @property
    def use_api(self) -> bool:
        """Whether to use YouTube API instead of scraping."""
        return bool(self.api_key)


@dataclass
class TwitterConfig:
    """Twitter/X API configuration."""

    bearer_token: str = field(default_factory=lambda: os.getenv("TWITTER_BEARER_TOKEN", ""))
    api_key: str = field(default_factory=lambda: os.getenv("TWITTER_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("TWITTER_API_SECRET", ""))
    access_token: str = field(default_factory=lambda: os.getenv("TWITTER_ACCESS_TOKEN", ""))
    access_token_secret: str = field(default_factory=lambda: os.getenv("TWITTER_ACCESS_TOKEN_SECRET", ""))

    search_queries: List[str] = field(default_factory=list)
    max_tweets_per_query: int = 100
    max_replies_per_tweet: int = 20

    @property
    def is_configured(self) -> bool:
        """Check if Twitter API is properly configured."""
        return bool(self.bearer_token or (self.api_key and self.api_secret))


@dataclass
class FilterConfig:
    """Keyword and region filter configuration."""

    dmk_keywords: List[str] = field(default_factory=lambda: ["dmk", "டிஎம்கே"])
    admk_keywords: List[str] = field(default_factory=lambda: ["admk", "aiadmk", "அதிமுக"])
    tvk_keywords: List[str] = field(default_factory=lambda: ["tvk", "டி.வி.கே"])
    region_keywords: List[str] = field(default_factory=lambda: [
        "palladam", "பல்லடம்", "tiruppur", "திருப்பூர்"
    ])

    @property
    def all_party_keywords(self) -> Dict[str, List[str]]:
        """Return all party keywords organized by party."""
        return {
            "dmk": self.dmk_keywords,
            "admk": self.admk_keywords,
            "tvk": self.tvk_keywords
        }


@dataclass
class ExportConfig:
    """Data export configuration."""

    output_dir: str = "output"
    csv_filename: str = "palladam_politics_data.csv"
    jsonl_filename: str = "palladam_politics_data.jsonl"

    @property
    def csv_path(self) -> Path:
        """Full path for CSV output."""
        return Path(self.output_dir) / self.csv_filename

    @property
    def jsonl_path(self) -> Path:
        """Full path for JSONL output."""
        return Path(self.output_dir) / self.jsonl_filename


@dataclass
class DeduplicationConfig:
    """Deduplication configuration."""

    enable: bool = True
    enable_cross_platform: bool = True
    enable_hash_dedup: bool = False
    storage_path: str = ".dedup_cache.json"
    hash_threshold: int = 3
    clear_cache_on_start: bool = False


@dataclass
class GoogleSheetsConfig:
    """Google Sheets export configuration."""

    enabled: bool = False
    spreadsheet_id: str = field(
        default_factory=lambda: os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
    )
    sheet_name: str = "RawData"
    summary_tab_name: str = "Summary"
    credentials_path: str = field(
        default_factory=lambda: os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    )
    append_mode: bool = False

    @property
    def is_configured(self) -> bool:
        """True when the config has enough info to attempt a Sheets export."""
        return bool(self.enabled and self.spreadsheet_id)


@dataclass
class ApifyConfig:
    """Apify API configuration."""
    enabled: bool = False
    api_token: str = field(default_factory=lambda: os.getenv("APIFY_API_TOKEN", ""))
    instagram_actor: str = "apify/instagram-scraper"
    facebook_actor: str = "apify/facebook-pages-scraper"
    twitter_actor: str = "apify/twitter-scraper"
    youtube_actor: str = "apify/youtube-scraper"
    max_items_per_run: int = 50
    comments_per_post: int = 20


@dataclass
class FirecrawlConfig:
    """Firecrawl API configuration."""
    enabled: bool = False
    api_key: str = field(default_factory=lambda: os.getenv("FIRECRAWL_API_KEY", ""))
    urls_to_scrape: List[str] = field(default_factory=list)


@dataclass
class AccountCredential:
    """Single account credential."""
    username: str = ""
    password: str = ""


@dataclass
class AccountsConfig:
    """Multi-account credentials for Playwright fallback."""
    instagram: List[AccountCredential] = field(default_factory=list)
    facebook: List[AccountCredential] = field(default_factory=list)
    twitter: List[AccountCredential] = field(default_factory=list)
    youtube: List[AccountCredential] = field(default_factory=list)


@dataclass
class InfiniteConfig:
    """Infinite / continuous scraping mode settings."""
    delay_minutes: int = 30
    max_runs: int = 0   # 0 = run forever


@dataclass
class Config:
    """Main configuration class containing all settings."""

    scraper_api: ScraperApiConfig = field(default_factory=ScraperApiConfig)
    instagram: InstagramConfig = field(default_factory=InstagramConfig)
    facebook: FacebookConfig = field(default_factory=FacebookConfig)
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)
    twitter: TwitterConfig = field(default_factory=TwitterConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    bright_data: BrightDataConfig = field(default_factory=BrightDataConfig)
    deduplication: DeduplicationConfig = field(default_factory=DeduplicationConfig)
    google_sheets: GoogleSheetsConfig = field(default_factory=GoogleSheetsConfig)
    apify: ApifyConfig = field(default_factory=ApifyConfig)
    firecrawl: FirecrawlConfig = field(default_factory=FirecrawlConfig)
    accounts: AccountsConfig = field(default_factory=AccountsConfig)
    infinite_mode: InfiniteConfig = field(default_factory=InfiniteConfig)

    log_level: str = "INFO"
    enable_which_platforms: List[str] = field(default_factory=lambda: [
        "instagram", "facebook", "youtube", "twitter"
    ])

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "Config":
        """Load configuration from a YAML file."""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        config = cls()

        if "scraper_api" in data:
            config.scraper_api = ScraperApiConfig(**data["scraper_api"])
        if "instagram" in data:
            config.instagram = InstagramConfig(**data["instagram"])
        if "facebook" in data:
            config.facebook = FacebookConfig(**data["facebook"])
        if "youtube" in data:
            config.youtube = YouTubeConfig(**data["youtube"])
        if "twitter" in data:
            config.twitter = TwitterConfig(**data["twitter"])
        if "twitter_collector" in data.get("scraper_api", {}):
            config.scraper_api.twitter_collector = data["scraper_api"]["twitter_collector"]
        if "filters" in data:
            config.filters = FilterConfig(**data["filters"])
        if "export" in data:
            config.export = ExportConfig(**data["export"])
        if "deduplication" in data:
            config.deduplication = DeduplicationConfig(**data["deduplication"])
        if "google_sheets" in data:
            config.google_sheets = GoogleSheetsConfig(**data["google_sheets"])
        if "apify" in data:
            config.apify = ApifyConfig(**data["apify"])
        if "firecrawl" in data:
            fc = data["firecrawl"]
            config.firecrawl = FirecrawlConfig(
                enabled=fc.get("enabled", False),
                api_key=fc.get("api_key", ""),
                urls_to_scrape=fc.get("urls_to_scrape", []),
            )
        if "accounts" in data:
            accs = data["accounts"]
            config.accounts = AccountsConfig(
                instagram=[AccountCredential(**a) for a in accs.get("instagram", [])],
                facebook=[AccountCredential(**a) for a in accs.get("facebook", [])],
                twitter=[AccountCredential(**a) for a in accs.get("twitter", [])],
                youtube=[AccountCredential(**a) for a in accs.get("youtube", [])],
            )
        if "infinite_mode" in data:
            config.infinite_mode = InfiniteConfig(**data["infinite_mode"])
        if "general" in data:
            config.log_level = data["general"].get("log_level", "INFO")
            config.enable_which_platforms = data["general"].get("enable_which_platforms", config.enable_which_platforms)

        return config

    def validate(self) -> bool:
        """Validate that required configuration is present."""
        enabled_platforms = [p for p in self.enable_which_platforms if p != "twitter"]
        
        # If scraper API is enabled, we need the token
        if self.scraper_api.use_scraper_api:
            if not self.scraper_api.is_configured:
                raise ValueError(
                    "Bright Data Scraper API Token not configured. "
                    "Set BRIGHT_DATA_API_TOKEN or configure it in config.yaml."
                )
        # Otherwise, if proxy is needed for manual scraping
        elif enabled_platforms:
            if not self.bright_data.is_configured:
                raise ValueError(
                    "Bright Data proxy credentials not configured. "
                    "Set BRIGHT_DATA_PROXY_HOST, BRIGHT_DATA_USERNAME, and BRIGHT_DATA_PASSWORD."
                )

        if "twitter" in self.enable_which_platforms and not self.twitter.is_configured:
            # If Twitter API is not configured, but Scraper API is used, we can proceed
            if not self.scraper_api.use_scraper_api:
                raise ValueError(
                    "Twitter API credentials not configured. "
                    "Set TWITTER_BEARER_TOKEN or TWITTER_API_KEY and TWITTER_API_SECRET."
                )

        return True



def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from file or create default config."""
    if config_path and Path(config_path).exists():
        return Config.from_yaml(config_path)
    return Config()