"""
Account manager for multi-account credential rotation.

Stores platform credentials and cycles through them round-robin.
Marks accounts as rate-limited and backs off automatically.

Usage:
  from account_manager import AccountManager
  mgr = AccountManager(config.accounts)
  account = mgr.get_next("instagram")   # {"username": ..., "password": ...}
  mgr.mark_limited("instagram", account["username"])  # back off this account
"""

import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# How long to back off a rate-limited account (seconds)
_BACKOFF_SECONDS = 3600  # 1 hour


class AccountManager:
    """Round-robin credential manager with per-account rate-limit tracking."""

    def __init__(self, accounts_config):
        """
        Args:
            accounts_config: AccountsConfig dataclass with per-platform lists.
        """
        # {platform: [{"username": ..., "password": ...}, ...]}
        self._accounts: Dict[str, List[dict]] = {}
        self._index: Dict[str, int] = defaultdict(int)
        self._limited_until: Dict[str, float] = {}  # "platform:username" → timestamp

        if accounts_config:
            for platform in ["instagram", "facebook", "twitter", "youtube"]:
                accs = getattr(accounts_config, platform, []) or []
                self._accounts[platform] = [
                    {"username": a.username, "password": a.password}
                    for a in accs
                ]

    def get_next(self, platform: str) -> Optional[dict]:
        """
        Return the next available account for platform (round-robin).
        Returns None if no accounts configured or all are rate-limited.
        """
        accs = self._accounts.get(platform, [])
        if not accs:
            return None

        now = time.time()
        # Try each account starting from current index
        for _ in range(len(accs)):
            idx = self._index[platform] % len(accs)
            self._index[platform] = idx + 1
            acc = accs[idx]
            key = f"{platform}:{acc['username']}"
            if self._limited_until.get(key, 0) <= now:
                return acc

        logger.warning(f"AccountManager: all {platform} accounts are rate-limited.")
        return None

    def mark_limited(self, platform: str, username: str, backoff_seconds: int = _BACKOFF_SECONDS):
        """Mark an account as rate-limited for backoff_seconds."""
        key = f"{platform}:{username}"
        self._limited_until[key] = time.time() + backoff_seconds
        logger.warning(
            f"AccountManager: {platform} account '{username}' rate-limited "
            f"for {backoff_seconds // 60} minutes."
        )

    def has_accounts(self, platform: str) -> bool:
        """Return True if any accounts are configured for platform."""
        return bool(self._accounts.get(platform))

    def available_count(self, platform: str) -> int:
        """Return number of currently available (non-limited) accounts."""
        accs = self._accounts.get(platform, [])
        now = time.time()
        return sum(
            1 for a in accs
            if self._limited_until.get(f"{platform}:{a['username']}", 0) <= now
        )
