"""
Scrapy middlewares for Palladam Politics Scraper.

  BrightDataProxyMiddleware : injects BrightData residential proxy from env vars
  RandomUserAgentMiddleware : rotates User-Agent from settings.USER_AGENT_LIST
"""

import os
import random
import logging

from scrapy import signals
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


class BrightDataProxyMiddleware:
    """
    Injects BrightData residential proxy into every request.
    Disabled automatically when env vars are not set.
    """

    def __init__(self, proxy_url: str):
        self.proxy_url = proxy_url

    @classmethod
    def from_crawler(cls, crawler):
        host = os.getenv("BRIGHT_DATA_PROXY_HOST", "")
        port = os.getenv("BRIGHT_DATA_PROXY_PORT", "33335")
        user = os.getenv("BRIGHT_DATA_USERNAME", "")
        pwd = os.getenv("BRIGHT_DATA_PASSWORD", "")

        if not all([host, user, pwd]):
            raise NotConfigured("BrightData proxy credentials not set — middleware disabled.")

        proxy_url = f"http://{user}:{pwd}@{host}:{port}"
        logger.info(f"BrightData proxy middleware enabled: {host}:{port}")
        return cls(proxy_url)

    def process_request(self, request, spider):
        request.meta["proxy"] = self.proxy_url


class RandomUserAgentMiddleware:
    """Rotates User-Agent from USER_AGENT_LIST defined in settings."""

    def __init__(self, user_agents):
        self.user_agents = user_agents

    @classmethod
    def from_crawler(cls, crawler):
        ua_list = crawler.settings.getlist("USER_AGENT_LIST", [])
        if not ua_list:
            raise NotConfigured("USER_AGENT_LIST not set in settings.")
        return cls(ua_list)

    def process_request(self, request, spider):
        request.headers["User-Agent"] = random.choice(self.user_agents)
