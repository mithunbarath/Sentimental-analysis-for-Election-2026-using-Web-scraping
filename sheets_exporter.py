"""
Google Sheets export module for the Palladam Politics Scraper.

Writes scraped SocialMediaRecord data to a Google Spreadsheet via the
Google Sheets API using a GCP service account (JSON key file).

Prerequisites:
  1. Create a GCP service account and download the JSON key.
  2. Share the target Google Sheet with the service account email (Editor).
  3. Set GOOGLE_APPLICATION_CREDENTIALS=path/to/key.json  OR supply
     credentials_path directly.

Usage:
  from sheets_exporter import export_to_sheets
  export_to_sheets(records, spreadsheet_id, sheet_name, credentials_path)
"""

import logging
import os
from datetime import datetime
from typing import List, Optional, Dict, Any

from models import SocialMediaRecord

logger = logging.getLogger(__name__)

# ── lazy imports so the module doesn't hard-fail if gspread isn't installed ──

def _get_gspread():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        return gspread, Credentials
    except ImportError as e:
        raise ImportError(
            "Google Sheets dependencies not installed. "
            "Run: pip install gspread google-auth"
        ) from e


# Google API scopes required for Sheets
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def _build_client(credentials_path: Optional[str] = None):
    """
    Build and return an authorised gspread client.

    Credential priority:
      1. ``credentials_path`` argument  (explicit JSON key file)
      2. ``GOOGLE_APPLICATION_CREDENTIALS`` env var  (JSON key file path)
      3. **Application Default Credentials (ADC)** — used automatically on GCP VMs
         that have the service account attached. No JSON key file is needed.
    """
    gspread, Credentials = _get_gspread()  # noqa: F841

    creds_file = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    if creds_file and os.path.exists(creds_file):
        # Explicit JSON key file (local dev / non-GCP environments)
        creds = Credentials.from_service_account_file(creds_file, scopes=_SCOPES)
        logger.debug(f"Using service account key file: {creds_file}")
    else:
        # Application Default Credentials — works automatically on GCP VMs
        # because the service account is attached to the instance.
        try:
            import google.auth
            creds, _ = google.auth.default(scopes=_SCOPES)
            logger.debug("Using Application Default Credentials (ADC).")
        except Exception as e:
            raise EnvironmentError(
                "No Google credentials found. On a GCP VM, attach a service account "
                "to the instance (--service-account flag). "
                "Locally, run: gcloud auth application-default login "
                f"(Error: {e})"
            ) from e

    client = gspread.authorize(creds)
    return client


def _get_or_create_worksheet(spreadsheet, title: str, rows: int = 5000, cols: int = 30):
    """Return existing worksheet by title, or create a new one."""
    try:
        return spreadsheet.worksheet(title)
    except Exception:
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)


def _records_to_rows(records: List[SocialMediaRecord]) -> List[List[str]]:
    """Convert records to a list of string rows (header first)."""
    headers = SocialMediaRecord.get_csv_headers()
    rows = [headers]
    for rec in records:
        csv_row = rec.to_csv_row()
        rows.append([csv_row.get(h, "") for h in headers])
    return rows


def _build_summary_rows(records: List[SocialMediaRecord]) -> List[List[str]]:
    """Build summary statistics rows for the Summary tab."""
    from exporter import generate_summary_stats
    stats = generate_summary_stats(records)

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = [
        ["Palladam Politics Scraper — Summary", ""],
        ["Generated at", run_ts],
        ["", ""],
        ["Metric", "Value"],
        ["Total records", str(stats["total_records"])],
        ["Palladam-related", str(stats["palladam_related_count"])],
        ["Records with text", str(stats["records_with_text"])],
        ["Records with timestamp", str(stats["records_with_timestamp"])],
        ["", ""],
        ["── By Platform ──", ""],
    ]
    for platform, count in sorted(stats["by_platform"].items()):
        rows.append([platform, str(count)])

    rows += [["", ""], ["── By Party ──", ""]]
    for party, count in sorted(stats["by_party"].items()):
        rows.append([party, str(count)])

    rows += [["", ""], ["── By Content Type ──", ""]]
    for ctype, count in sorted(stats["by_type"].items()):
        rows.append([ctype, str(count)])

    if "by_region" in stats:
        rows += [["", ""], ["── By Region ──", ""]]
        for region, count in sorted(stats["by_region"].items()):
            rows.append([region, str(count)])

    return rows


def write_region_tabs(
    records: List[SocialMediaRecord],
    spreadsheet,
    clear_existing: bool = True
) -> None:
    """Write one worksheet tab per region."""
    from collections import defaultdict
    by_region = defaultdict(list)
    for r in records:
        region = r.region or "unknown"
        by_region[region].append(r)
        
    for region, reg_records in by_region.items():
        tab_name = region.replace("_", " ").title()
        if len(tab_name) > 100:
            tab_name = tab_name[:100]
            
        try:
            ws = _get_or_create_worksheet(spreadsheet, tab_name)
            if clear_existing:
                ws.clear()
                
            all_rows = _records_to_rows(reg_records)
            ws.update("A1", all_rows)
            ws.freeze(rows=1)
            logger.info(f"Wrote {len(all_rows)-1} records to region tab '{tab_name}'.")
        except Exception as e:
            logger.warning(f"Could not write region tab '{tab_name}': {e}")


def write_summary_tab(
    records: List[SocialMediaRecord],
    spreadsheet,
    tab_name: str = "Summary"
) -> None:
    """Write a summary statistics tab to the spreadsheet."""
    ws = _get_or_create_worksheet(spreadsheet, tab_name)
    ws.clear()
    summary_rows = _build_summary_rows(records)
    ws.update("A1", summary_rows)
    logger.info(f"Summary tab '{tab_name}' written ({len(summary_rows)} rows).")


def export_to_sheets(
    records: List[SocialMediaRecord],
    spreadsheet_id: str,
    sheet_name: str = "RawData",
    credentials_path: Optional[str] = None,
    write_summary: bool = True,
    summary_tab_name: str = "Summary",
    clear_existing: bool = True,
    split_by_region: bool = False,
) -> int:
    """
    Export scraped records to a Google Sheet.

    Args:
        records:           List of SocialMediaRecord objects to export.
        spreadsheet_id:    The ID from the Google Sheets URL
                           (https://docs.google.com/spreadsheets/d/<ID>/edit).
        sheet_name:        Name of the worksheet tab for raw data.
        credentials_path:  Path to GCP service account JSON key file.
        write_summary:     Whether to also write a Summary tab.
        summary_tab_name:  Name of the summary worksheet tab.
        clear_existing:    If True, clears the sheet before writing.
        split_by_region:   If True, automatically writes to tabs named by region.

    Returns:
        Number of data rows written (excluding header).
    """
    if not records:
        logger.warning("No records to export to Google Sheets.")
        return 0

    client = _build_client(credentials_path)

    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        logger.info(f"Opened spreadsheet: '{spreadsheet.title}' ({spreadsheet_id})")
    except Exception as e:
        raise ConnectionError(
            f"Cannot open spreadsheet '{spreadsheet_id}'. "
            f"Make sure the service account has Editor access. Error: {e}"
        ) from e

    # ── Raw data tab ──────────────────────────────────────────────────────────
    raw_ws = _get_or_create_worksheet(spreadsheet, sheet_name)
    if clear_existing:
        raw_ws.clear()

    all_rows = _records_to_rows(records)           # header + data rows
    raw_ws.update("A1", all_rows)

    # Freeze the header row
    raw_ws.freeze(rows=1)

    data_row_count = len(all_rows) - 1  # exclude header
    logger.info(
        f"Exported {data_row_count} records to sheet '{sheet_name}' "
        f"in spreadsheet '{spreadsheet.title}'."
    )

    # ── Summary tab ───────────────────────────────────────────────────────────
    if write_summary:
        try:
            write_summary_tab(records, spreadsheet, tab_name=summary_tab_name)
        except Exception as e:
            logger.warning(f"Could not write summary tab: {e}")

    # ── Region tabs ───────────────────────────────────────────────────────────
    if split_by_region:
        write_region_tabs(records, spreadsheet, clear_existing=clear_existing)

    return data_row_count


def append_to_sheets(
    records: List[SocialMediaRecord],
    spreadsheet_id: str,
    sheet_name: str = "RawData",
    credentials_path: Optional[str] = None,
    split_by_region: bool = False,
) -> int:
    """
    Append records to an existing sheet without clearing it.
    Useful for incremental / scheduled runs.

    Returns:
        Number of rows appended.
    """
    if not records:
        return 0

    client = _build_client(credentials_path)
    spreadsheet = client.open_by_key(spreadsheet_id)
    raw_ws = _get_or_create_worksheet(spreadsheet, sheet_name)

    headers = SocialMediaRecord.get_csv_headers()
    existing = raw_ws.get_all_values()

    # Write header only if sheet is empty
    if not existing:
        raw_ws.append_row(headers)

    rows_to_add = []
    for rec in records:
        csv_row = rec.to_csv_row()
        rows_to_add.append([csv_row.get(h, "") for h in headers])

    if rows_to_add:
        raw_ws.append_rows(rows_to_add, value_input_option="RAW")

    logger.info(
        f"Appended {len(rows_to_add)} records to '{sheet_name}'."
    )
    
    if split_by_region:
        write_region_tabs(records, spreadsheet, clear_existing=False)
        
    return len(rows_to_add)
