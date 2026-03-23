"""
HTTP client module for making requests through Bright Data proxies.
"""

import os
import time
import random
import logging
from typing import Optional, Dict, Any, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import BrightDataConfig

logger = logging.getLogger(__name__)


class BrightDataScraperClient:
    """Client for interacting with the Bright Data Social Media Scraper API."""

    def __init__(self, api_token: Optional[str] = None, base_url: str = "https://api.brightdata.com"):
        """Initialize the scraper client."""
        self.api_token = api_token or os.environ.get("BRIGHT_DATA_API_TOKEN", "")
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    @property
    def is_configured(self) -> bool:
        """Check if the client is configured with an API token."""
        return bool(self.api_token)

    def trigger_collection(self, collector_id: str, urls: List[str]) -> Optional[str]:
        """
        Trigger a collection job on Bright Data.
        Returns the collection_id (or snapshot_id) if successful.
        """
        if not self.is_configured:
            logger.error("Bright Data Scraper API Token not configured")
            return None

        # Standard DCA Trigger endpoint
        endpoint = f"{self.base_url}/dca/trigger?collector={collector_id}"
        payload = [{"url": url} for url in urls]
        
        logger.info(f"Triggering Bright Data collection for {len(urls)} URLs on collector '{collector_id}'")
        response = post_with_retry(endpoint, json=payload, headers=self.headers)
        
        if response:
            data = response.json()
            # Handle different response formats
            collection_id = data.get("collection_id") or data.get("snapshot_id")
            if collection_id:
                logger.debug(f"Triggered collection ID: {collection_id}")
                return collection_id
            
            logger.error(f"Failed to get collection ID from response: {data}")
        
        return None

    def get_collection_results(self, collection_id: str, timeout: int = 300, poll_interval: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Poll for and retrieve results of a collection job.
        """
        if not self.is_configured:
            return None

        endpoint = f"{self.base_url}/dca/get_result?collection_id={collection_id}"
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            logger.info(f"Polling for Bright Data results (ID: {collection_id})...")
            response = get_with_retry(endpoint, headers=self.headers)
            
            if response:
                if response.status_code == 200:
                    data = response.json()
                    # Some APIs return an empty list or a list with a wait status
                    if data and isinstance(data, list):
                        logger.info(f"Successfully retrieved {len(data)} records from Bright Data")
                        return data
                elif response.status_code == 202:
                    # Job still processing
                    logger.debug("Job still processing...")
                else:
                    logger.warning(f"Unexpected status code while polling: {response.status_code}")
            
            time.sleep(poll_interval)
        
        logger.error(f"Timed out waiting for collection results (ID: {collection_id})")
        return None



USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


def get_random_user_agent() -> str:
    """Get a random user agent from the list."""
    return random.choice(USER_AGENTS)


def get_session(
    bright_data_config: Optional[BrightDataConfig] = None,
    retry_config: Optional[Dict[str, Any]] = None,
    timeout: int = 30
) -> requests.Session:
    """Create a configured requests session with Bright Data proxy and retry logic."""
    if bright_data_config is None:
        bright_data_config = BrightDataConfig()

    session = requests.Session()
    session.timeout = timeout

    session.headers.update({
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    })

    if bright_data_config.is_configured:
        session.proxies = {
            "http": bright_data_config.proxy_url,
            "https": bright_data_config.proxy_url,
        }
        logger.info(f"Configured Bright Data proxy: {bright_data_config.proxy_host}:{bright_data_config.proxy_port}")
    else:
        logger.warning("No Bright Data proxy configured - requests will be direct")

    if retry_config is None:
        retry_config = {
            "total": 3,
            "backoff_factor": 1,
            "status_forcelist": [500, 502, 503, 504, 429],
            "allowed_methods": ["GET", "HEAD", "OPTIONS"]
        }

    retry_strategy = Retry(**retry_config)
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0):
    """Sleep for a random amount of time to avoid rate limiting."""
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug(f"Sleeping for {delay:.2f} seconds")
    time.sleep(delay)


def get_with_retry(
    url: str,
    session: Optional[requests.Session] = None,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    max_retries: int = 3,
    delay_between_retries: float = 2.0,
    **kwargs
) -> Optional[requests.Response]:
    """Make a GET request with retry logic."""
    should_close_session = False

    if session is None:
        session = get_session()
        should_close_session = True

    for attempt in range(max_retries):
        try:
            request_headers = headers.copy() if headers else {}
            request_headers["User-Agent"] = get_random_user_agent()

            response = session.get(url, params=params, headers=request_headers, **kwargs)
            response.raise_for_status()

            if should_close_session:
                session.close()

            return response

        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                delay = delay_between_retries * (1 + random.random() * 0.5)
                time.sleep(delay)

    if should_close_session:
        session.close()

    logger.error(f"All {max_retries} retry attempts failed for {url}")
    return None


def post_with_retry(
    url: str,
    session: Optional[requests.Session] = None,
    data: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    max_retries: int = 3,
    delay_between_retries: float = 2.0,
    **kwargs
) -> Optional[requests.Response]:
    """Make a POST request with retry logic."""
    should_close_session = False

    if session is None:
        session = get_session()
        should_close_session = True

    for attempt in range(max_retries):
        try:
            request_headers = headers.copy() if headers else {}
            request_headers["User-Agent"] = get_random_user_agent()

            response = session.post(
                url,
                data=data,
                json=json,
                headers=request_headers,
                **kwargs
            )
            response.raise_for_status()

            if should_close_session:
                session.close()

            return response

        except requests.exceptions.RequestException as e:
            logger.warning(f"POST request failed (attempt {attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                delay = delay_between_retries * (1 + random.random() * 0.5)
                time.sleep(delay)

    if should_close_session:
        session.close()

    logger.error(f"All {max_retries} retry attempts failed for POST to {url}")
    return None