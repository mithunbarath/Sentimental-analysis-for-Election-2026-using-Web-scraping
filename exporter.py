"""
Data export module for saving collected social media data.
"""

import csv
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from models import SocialMediaRecord

logger = logging.getLogger(__name__)


def export_to_csv(
    records: List[SocialMediaRecord],
    output_path: str,
    include_headers: bool = True
) -> int:
    """Export records to a CSV file."""
    output_file = Path(output_path)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            if include_headers:
                writer = csv.DictWriter(f, fieldnames=SocialMediaRecord.get_csv_headers())
                writer.writeheader()

            writer = csv.DictWriter(f, fieldnames=SocialMediaRecord.get_csv_headers())

            for record in records:
                writer.writerow(record.to_csv_row())

        logger.info(f"Exported {len(records)} records to CSV: {output_path}")
        return len(records)

    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        raise


def export_to_jsonl(
    records: List[SocialMediaRecord],
    output_path: str
) -> int:
    """Export records to a JSONL file (one JSON per line)."""
    output_file = Path(output_path)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            for record in records:
                json.dump(record.to_dict(), f, ensure_ascii=False)
                f.write("\n")

        logger.info(f"Exported {len(records)} records to JSONL: {output_path}")
        return len(records)

    except Exception as e:
        logger.error(f"Error exporting to JSONL: {e}")
        raise


def export_to_json(
    records: List[SocialMediaRecord],
    output_path: str,
    indent: int = 2
) -> int:
    """Export records to a JSON file (as an array)."""
    output_file = Path(output_path)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = [record.to_dict() for record in records]

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)

        logger.info(f"Exported {len(records)} records to JSON: {output_path}")
        return len(records)

    except Exception as e:
        logger.error(f"Error exporting to JSON: {e}")
        raise


def export_all(
    records: List[SocialMediaRecord],
    csv_path: str,
    jsonl_path: str,
    json_path: Optional[str] = None
) -> Dict[str, int]:
    """Export records to multiple formats."""
    results = {}

    csv_count = export_to_csv(records, csv_path)
    results["csv"] = csv_count

    jsonl_count = export_to_jsonl(records, jsonl_path)
    results["jsonl"] = jsonl_count

    if json_path:
        json_count = export_to_json(records, json_path)
        results["json"] = json_count

    return results


def export_by_region(records: List[SocialMediaRecord], output_dir: str) -> Dict[str, int]:
    """Export records split by region into separate CSV files."""
    from collections import defaultdict
    
    by_region = defaultdict(list)
    for r in records:
        region = r.region or "unknown"
        by_region[region].append(r)
        
    results = {}
    base_dir = Path(output_dir) / "regions"
    
    try:
        from region_classifier import TamilNaduRegionClassifier
        classifier = TamilNaduRegionClassifier()
    except ImportError:
        classifier = None
        
    for region, reg_records in by_region.items():
        if classifier:
            zone = classifier.get_zone(region)
            region_dir = base_dir / zone
        else:
            region_dir = base_dir
            
        region_dir.mkdir(parents=True, exist_ok=True)
        csv_path = region_dir / f"{region}.csv"
        
        count = export_to_csv(reg_records, str(csv_path))
        results[region] = count
        
    logger.info(f"Exported by region: {sum(results.values())} records across {len(results)} regions.")
    return results


def load_from_csv(csv_path: str) -> List[SocialMediaRecord]:
    """Load records from a CSV file."""
    records = []

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                record = SocialMediaRecord(
                    platform=row.get("platform", ""),
                    type=row.get("type", ""),
                    id=row.get("id", ""),
                    parent_id=row.get("parent_id") or None,
                    url=row.get("url") or None,
                    author=row.get("author") or None,
                    title=row.get("title") or None,
                    text=row.get("text") or None,
                    like_count=int(row.get("like_count")) if row.get("like_count") else None,
                    reaction_count=int(row.get("reaction_count")) if row.get("reaction_count") else None,
                    view_count=int(row.get("view_count")) if row.get("view_count") else None,
                    retweet_count=int(row.get("retweet_count")) if row.get("retweet_count") else None,
                    reply_count=int(row.get("reply_count")) if row.get("reply_count") else None,
                    comment_count=int(row.get("comment_count")) if row.get("comment_count") else None,
                    source=row.get("source") or None,
                    timestamp=row.get("timestamp") or None,
                    parties_mentioned=row.get("parties_mentioned", "").split(",") if row.get("parties_mentioned") else [],
                    is_palladam_related=row.get("is_palladam_related", "").lower() == "true"
                )
                records.append(record)

        logger.info(f"Loaded {len(records)} records from CSV: {csv_path}")

    except Exception as e:
        logger.error(f"Error loading from CSV: {e}")
        raise

    return records


def load_from_jsonl(jsonl_path: str) -> List[SocialMediaRecord]:
    """Load records from a JSONL file."""
    records = []

    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    record = SocialMediaRecord.from_dict(data)
                    records.append(record)

        logger.info(f"Loaded {len(records)} records from JSONL: {jsonl_path}")

    except Exception as e:
        logger.error(f"Error loading from JSONL: {e}")
        raise

    return records


def generate_summary_stats(records: List[SocialMediaRecord]) -> Dict[str, Any]:
    """Generate summary statistics for a collection of records."""
    stats = {
        "total_records": len(records),
        "by_platform": {},
        "by_type": {},
        "by_party": {},
        "by_region": {},
        "palladam_related_count": 0,
        "records_with_text": 0,
        "records_with_timestamp": 0
    }

    for record in records:
        stats["by_platform"][record.platform] = stats["by_platform"].get(record.platform, 0) + 1
        stats["by_type"][record.type] = stats["by_type"].get(record.type, 0) + 1

        for party in record.parties_mentioned:
            stats["by_party"][party] = stats["by_party"].get(party, 0) + 1

        region = record.region or "unknown"
        stats["by_region"][region] = stats["by_region"].get(region, 0) + 1

        if record.is_palladam_related:
            stats["palladam_related_count"] += 1

        if record.text:
            stats["records_with_text"] += 1

        if record.timestamp:
            stats["records_with_timestamp"] += 1

    return stats


def export_to_sheets_if_configured(
    records: List[SocialMediaRecord],
    sheets_config,
) -> Optional[int]:
    """
    Push records to Google Sheets if sheets_config.is_configured is True.

    Args:
        records:       List of SocialMediaRecord objects.
        sheets_config: GoogleSheetsConfig instance from Config.

    Returns:
        Number of rows written, or None if Sheets export was skipped.
    """
    if not sheets_config.is_configured:
        return None

    try:
        from sheets_exporter import export_to_sheets, append_to_sheets
    except ImportError:
        logger.error(
            "sheets_exporter unavailable. Install: pip install gspread google-auth"
        )
        return None

    fn = append_to_sheets if sheets_config.append_mode else export_to_sheets

    kwargs: Dict[str, Any] = {
        "records": records,
        "spreadsheet_id": sheets_config.spreadsheet_id,
        "sheet_name": sheets_config.sheet_name,
        "credentials_path": sheets_config.credentials_path or None,
        "split_by_region": getattr(sheets_config, "split_by_region", False),
    }
    if not sheets_config.append_mode:
        kwargs["write_summary"] = True
        kwargs["summary_tab_name"] = sheets_config.summary_tab_name

    try:
        count = fn(**kwargs)
        logger.info(
            f"Google Sheets export complete: {count} rows → "
            f"spreadsheet '{sheets_config.spreadsheet_id}' / "
            f"sheet '{sheets_config.sheet_name}'."
        )
        return count
    except Exception as e:
        logger.error(f"Google Sheets export failed: {e}")
        return None