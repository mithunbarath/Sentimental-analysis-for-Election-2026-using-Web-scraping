"""
Deduplication module for preventing duplicate records.
"""

import json
import hashlib
import logging
from pathlib import Path
from typing import Set, Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

from models import SocialMediaRecord

logger = logging.getLogger(__name__)


@dataclass
class DeduplicationStats:
    """Statistics for deduplication operations."""
    total_records: int = 0
    duplicates_found: int = 0
    unique_records: int = 0
    records_by_platform: Dict[str, int] = field(default_factory=dict)
    records_by_type: Dict[str, int] = field(default_factory=dict)

    def add_record(self, record: SocialMediaRecord):
        """Add a record to statistics."""
        self.total_records += 1
        self.records_by_platform[record.platform] = (
            self.records_by_platform.get(record.platform, 0) + 1
        )
        self.records_by_type[record.type] = (
            self.records_by_type.get(record.type, 0) + 1
        )

    def add_duplicate(self, record: SocialMediaRecord):
        """Register a duplicate record."""
        self.duplicates_found += 1

    def add_unique(self, record: SocialMediaRecord):
        """Register a unique record."""
        self.unique_records += 1

    def to_dict(self) -> Dict:
        """Convert stats to dictionary."""
        return {
            "total_records": self.total_records,
            "duplicates_found": self.duplicates_found,
            "unique_records": self.unique_records,
            "records_by_platform": self.records_by_platform,
            "records_by_type": self.records_by_type
        }


class DeduplicationManager:
    """Manager for deduplicating social media records."""

    def __init__(
        self,
        storage_path: Optional[str] = None,
        use_id_deduplication: bool = True,
        use_url_deduplication: bool = True,
        use_hash_deduplication: bool = False,
        hash_threshold: int = 3
    ):
        """Initialize the deduplication manager."""
        self.storage_path = Path(storage_path) if storage_path else None
        self.use_id_deduplication = use_id_deduplication
        self.use_url_deduplication = use_url_deduplication
        self.use_hash_deduplication = use_hash_deduplication
        self.hash_threshold = hash_threshold

        self.seen_ids: Set[str] = set()
        self.seen_urls: Set[str] = set()
        self.seen_hashes: Set[str] = set()
        self.seen_composite_keys: Set[str] = set()

        self.stats = DeduplicationStats()

        if self.storage_path:
            self.load()

    def is_duplicate(
        self,
        record: SocialMediaRecord,
        check_all: bool = False
    ) -> bool:
        """Check if a record is a duplicate."""
        self.stats.add_record(record)

        if self.use_id_deduplication and record.id:
            if record.id in self.seen_ids:
                logger.debug(f"Duplicate found by ID: {record.id}")
                self.stats.add_duplicate(record)
                return True

            if not check_all:
                return self._check_remaining(record, skip_id=True)

        if self.use_url_deduplication and record.url:
            normalized_url = self._normalize_url(record.url)
            if normalized_url in self.seen_urls:
                logger.debug(f"Duplicate found by URL: {normalized_url}")
                self.stats.add_duplicate(record)
                return True

            if not check_all:
                return self._check_remaining(record, skip_id=True, skip_url=True)

        if self.use_hash_deduplication and record.text:
            if len(record.text.strip()) >= self.hash_threshold:
                content_hash = self._generate_content_hash(record)
                if content_hash in self.seen_hashes:
                    logger.debug(f"Duplicate found by hash: {content_hash[:16]}...")
                    self.stats.add_duplicate(record)
                    return True

        composite_key = self._generate_composite_key(record)
        if composite_key in self.seen_composite_keys:
            logger.debug(f"Duplicate found by composite key: {composite_key}")
            self.stats.add_duplicate(record)
            return True

        self.stats.add_unique(record)
        return False

    def _check_remaining(
        self,
        record: SocialMediaRecord,
        skip_id: bool = False,
        skip_url: bool = False
    ) -> bool:
        """Check remaining deduplication methods."""
        if not skip_url and self.use_url_deduplication and record.url:
            normalized_url = self._normalize_url(record.url)
            if normalized_url in self.seen_urls:
                self.stats.add_duplicate(record)
                return True

        if self.use_hash_deduplication and record.text:
            if len(record.text.strip()) >= self.hash_threshold:
                content_hash = self._generate_content_hash(record)
                if content_hash in self.seen_hashes:
                    self.stats.add_duplicate(record)
                    return True

        composite_key = self._generate_composite_key(record)
        if composite_key in self.seen_composite_keys:
            self.stats.add_duplicate(record)
            return True

        self.stats.add_unique(record)
        return False

    def add_record(self, record: SocialMediaRecord):
        """Add a record to the deduplication database."""
        if self.use_id_deduplication and record.id:
            self.seen_ids.add(record.id)

        if self.use_url_deduplication and record.url:
            normalized_url = self._normalize_url(record.url)
            self.seen_urls.add(normalized_url)

        if self.use_hash_deduplication and record.text:
            if len(record.text.strip()) >= self.hash_threshold:
                content_hash = self._generate_content_hash(record)
                self.seen_hashes.add(content_hash)

        composite_key = self._generate_composite_key(record)
        self.seen_composite_keys.add(composite_key)

    def deduplicate_records(
        self,
        records: List[SocialMediaRecord],
        remove_duplicates: bool = True
    ) -> List[SocialMediaRecord]:
        """Deduplicate a list of records."""
        unique_records = []
        duplicate_indices = set()

        for i, record in enumerate(records):
            if self.is_duplicate(record):
                duplicate_indices.add(i)
            else:
                self.add_record(record)
                unique_records.append(record)

        logger.info(
            f"Deduplication: {len(records)} input, "
            f"{len(duplicate_indices)} duplicates, "
            f"{len(unique_records)} unique"
        )

        if remove_duplicates:
            return unique_records
        else:
            marked_records = []
            for i, record in enumerate(records):
                record_dict = record.to_dict()
                record_dict["_is_duplicate"] = i in duplicate_indices
                marked_records.append(SocialMediaRecord.from_dict(record_dict))
            return marked_records

    def deduplicate_across_platforms(
        self,
        records: List[SocialMediaRecord],
        enable_cross_platform: bool = True
    ) -> List[SocialMediaRecord]:
        """Deduplicate records across different platforms."""
        if not enable_cross_platform:
            return self.deduplicate_records(records)

        logger.info("Performing cross-platform deduplication")

        content_map: Dict[str, List[SocialMediaRecord]] = {}

        for record in records:
            if record.text and len(record.text.strip()) >= self.hash_threshold:
                content_hash = self._generate_content_hash(record, include_platform=False)
                if content_hash not in content_map:
                    content_map[content_hash] = []
                content_map[content_hash].append(record)

        cross_platform_duplicates = set()
        for content_hash, matching_records in content_map.items():
            if len(matching_records) > 1:
                platforms = {r.platform for r in matching_records}
                if len(platforms) > 1:
                    for record in matching_records[1:]:
                        cross_platform_duplicates.add(record)
                    logger.info(
                        f"Found cross-platform duplicate: {content_hash[:16]}... "
                        f"across platforms {platforms}"
                    )

        unique_records = [
            r for r in records
            if r not in cross_platform_duplicates
        ]

        logger.info(
            f"Cross-platform deduplication: {len(records)} input, "
            f"{len(cross_platform_duplicates)} cross-platform duplicates, "
            f"{len(unique_records)} remaining"
        )

        return self.deduplicate_records(unique_records)

    def save(self):
        """Save deduplication state to storage."""
        if not self.storage_path:
            logger.debug("No storage path, skipping save")
            return

        try:
            data = {
                "seen_ids": list(self.seen_ids),
                "seen_urls": list(self.seen_urls),
                "seen_hashes": list(self.seen_hashes),
                "seen_composite_keys": list(self.seen_composite_keys),
                "stats": self.stats.to_dict(),
                "timestamp": datetime.now().isoformat()
            }

            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved deduplication state to {self.storage_path}")

        except Exception as e:
            logger.error(f"Error saving deduplication state: {e}")

    def load(self):
        """Load deduplication state from storage."""
        if not self.storage_path or not self.storage_path.exists():
            logger.debug("No existing deduplication state to load")
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.seen_ids = set(data.get("seen_ids", []))
            self.seen_urls = set(data.get("seen_urls", []))
            self.seen_hashes = set(data.get("seen_hashes", []))
            self.seen_composite_keys = set(data.get("seen_composite_keys", []))

            stats_data = data.get("stats", {})
            self.stats = DeduplicationStats(
                total_records=stats_data.get("total_records", 0),
                duplicates_found=stats_data.get("duplicates_found", 0),
                unique_records=stats_data.get("unique_records", 0),
                records_by_platform=stats_data.get("records_by_platform", {}),
                records_by_type=stats_data.get("records_by_type", {})
            )

            timestamp = data.get("timestamp")
            if timestamp:
                logger.info(
                    f"Loaded deduplication state from {self.storage_path} "
                    f"(saved: {timestamp})"
                )

        except Exception as e:
            logger.error(f"Error loading deduplication state: {e}")

    def clear(self):
        """Clear all deduplication state."""
        self.seen_ids.clear()
        self.seen_urls.clear()
        self.seen_hashes.clear()
        self.seen_composite_keys.clear()
        self.stats = DeduplicationStats()
        logger.info("Cleared deduplication state")

    def get_stats(self) -> DeduplicationStats:
        """Get deduplication statistics."""
        return self.stats

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        if not url:
            return ""

        tracking_params = [
            "fbclid", "igshid", "si", "utm_source", "utm_medium",
            "utm_campaign", "ref", "feature", "t", "s"
        ]

        parts = url.split("?", 1)
        base = parts[0]

        if len(parts) > 1:
            query_parts = parts[1].split("&")
            filtered_query = []

            for param in query_parts:
                if "=" not in param:
                    continue
                key, _ = param.split("=", 1)
                if key not in tracking_params:
                    filtered_query.append(param)

            if filtered_query:
                base += "?" + "&".join(filtered_query)

        base = base.split("#")[0]
        return base.lower()

    def _generate_content_hash(
        self,
        record: SocialMediaRecord,
        include_platform: bool = False
    ) -> str:
        """Generate content hash for deduplication."""
        content_parts = []

        if include_platform:
            content_parts.append(record.platform)

        if record.text:
            content_parts.append(record.text.strip().lower())

        if record.author:
            content_parts.append(record.author.lower())

        if record.type == "post" and record.title:
            content_parts.append(record.title.strip().lower())

        content = "|||".join(content_parts)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _generate_composite_key(self, record: SocialMediaRecord) -> str:
        """Generate a composite key for the record."""
        id_or_url = record.id or record.url or "unknown"
        return f"{record.platform}:{record.type}:{id_or_url}"


class StreamingDeduplicator:
    """Streaming deduplicator for processing records as they arrive."""

    def __init__(self, manager: DeduplicationManager):
        """Initialize streaming deduplicator."""
        self.manager = manager
        self.buffer: List[SocialMediaRecord] = []
        self.buffer_size = 100

    def add_record(self, record: SocialMediaRecord) -> bool:
        """Add a record to the stream."""
        is_dup = self.manager.is_duplicate(record)

        if not is_dup:
            self.manager.add_record(record)
            self.buffer.append(record)

            if len(self.buffer) >= self.buffer_size:
                self.flush()

        return not is_dup

    def flush(self) -> List[SocialMediaRecord]:
        """Flush buffered records."""
        flushed = self.buffer.copy()
        self.buffer.clear()
        return flushed

    def get_buffer(self) -> List[SocialMediaRecord]:
        """Get current buffer without flushing."""
        return self.buffer.copy()


def quick_deduplicate(
    records: List[SocialMediaRecord],
    storage_path: Optional[str] = None
) -> List[SocialMediaRecord]:
    """Convenience function to quickly deduplicate records."""
    manager = DeduplicationManager(storage_path=storage_path)
    return manager.deduplicate_records(records)


def merge_deduplicated_datasets(
    datasets: List[List[SocialMediaRecord]],
    storage_path: Optional[str] = None
) -> List[SocialMediaRecord]:
    """Merge multiple datasets while maintaining uniqueness."""
    manager = DeduplicationManager(storage_path=storage_path)
    merged = []
    for dataset in datasets:
        unique_in_dataset = manager.deduplicate_records(dataset)
        merged.extend(unique_in_dataset)
    return merged