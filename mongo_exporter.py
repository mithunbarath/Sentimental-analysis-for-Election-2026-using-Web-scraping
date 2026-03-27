"""
MongoDB async exporter for Palladam Politics Scraper.

Uses `motor` (async PyMongo driver) for non-blocking upserts.
Each record is deduplicated by (platform, id) — replacing the file-based
JSON cache used by deduplication.py for persistence.

Usage:
    from mongo_exporter import export_to_mongo_if_configured
    inserted = await export_to_mongo_if_configured(records, cfg.mongodb)
"""

import logging
from typing import List, Optional

from models import SocialMediaRecord

logger = logging.getLogger(__name__)


class MongoExporter:
    """Async MongoDB exporter with upsert-based deduplication."""

    def __init__(self, uri: str, db_name: str, collection: str):
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            self._client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
            self._col = self._client[db_name][collection]
            self._uri = uri
            self._db_name = db_name
            self._col_name = collection
        except ImportError:
            raise ImportError(
                "motor is required for MongoDB export. "
                "Install it with: pip install motor>=3.4.0"
            )

    async def ensure_indexes(self):
        """Create compound index for efficient dedup lookups."""
        try:
            await self._col.create_index(
                [("platform", 1), ("id", 1)],
                unique=True,
                name="platform_id_unique",
                background=True,
            )
            logger.debug("MongoDB index ensured on (platform, id)")
        except Exception as e:
            logger.warning(f"MongoDB index creation warning: {e}")

    async def upsert_records(self, records: List[SocialMediaRecord]) -> int:
        """
        Upsert records into MongoDB.
        Returns the count of newly inserted (not updated) records.
        """
        from pymongo import UpdateOne
        from pymongo.errors import BulkWriteError

        if not records:
            return 0

        await self.ensure_indexes()

        ops = []
        for rec in records:
            doc = rec.to_dict()
            # Remove raw_data to keep Mongo documents lean
            doc.pop("raw_data", None)
            ops.append(
                UpdateOne(
                    {"platform": rec.platform, "id": rec.id},
                    {"$set": doc},
                    upsert=True,
                )
            )

        try:
            result = await self._col.bulk_write(ops, ordered=False)
            inserted = result.upserted_count
            modified = result.modified_count
            logger.info(
                f"MongoDB: {inserted} new records inserted, "
                f"{modified} existing records updated "
                f"(collection: {self._db_name}.{self._col_name})"
            )
            return inserted
        except BulkWriteError as bwe:
            logger.warning(
                f"MongoDB bulk write partial error "
                f"({bwe.details.get('nInserted', 0)} inserted before error): {bwe}"
            )
            return bwe.details.get("nInserted", 0)
        except Exception as e:
            logger.error(f"MongoDB upsert error: {e}")
            return 0

    async def write_nlp_enrichment(self, records: List[SocialMediaRecord]) -> int:
        """
        Update existing Mongo documents with NLP fields after enrichment.
        """
        from pymongo import UpdateOne

        ops = []
        for rec in records:
            if rec.nlp_sentiment is not None:
                ops.append(
                    UpdateOne(
                        {"platform": rec.platform, "id": rec.id},
                        {
                            "$set": {
                                "nlp_sentiment": rec.nlp_sentiment,
                                "nlp_sentiment_score": rec.nlp_sentiment_score,
                                "nlp_trend_score": rec.nlp_trend_score,
                            }
                        },
                    )
                )
        if not ops:
            return 0
        try:
            result = await self._col.bulk_write(ops, ordered=False)
            return result.modified_count
        except Exception as e:
            logger.error(f"MongoDB NLP update error: {e}")
            return 0

    async def close(self):
        """Close the motor client connection."""
        try:
            self._client.close()
        except Exception:
            pass


async def export_to_mongo_if_configured(
    records: List[SocialMediaRecord], mongo_cfg
) -> Optional[int]:
    """
    Convenience wrapper — mirrors `export_to_sheets_if_configured`.

    Returns:
        int  — number of newly inserted records
        None — if MongoDB is not configured / disabled
    """
    if not getattr(mongo_cfg, "is_configured", False):
        return None

    exporter = MongoExporter(
        uri=mongo_cfg.uri,
        db_name=mongo_cfg.db_name,
        collection=mongo_cfg.collection,
    )
    try:
        return await exporter.upsert_records(records)
    finally:
        await exporter.close()
