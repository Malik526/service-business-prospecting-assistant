"""backfill_emails.py

One-shot enrichment script: reads all existing rows from the Google Sheet,
finds prospects where the Email column is empty but a Website URL exists,
extracts the email from each website in parallel, and writes results back
to the sheet in a single batch API call.

Run:
    python3 backfill_emails.py            # live run — writes to sheet
    python3 backfill_emails.py --dry-run  # shows what would be written, no writes

Dependencies: same virtualenv as main.py (requests, google-api-python-client).
"""

from __future__ import annotations

import argparse
import string
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from googleapiclient.errors import HttpError

from config import load_config
from google_sheets import GoogleSheetsClient, SHEET_COLUMNS
from pipeline.social import extract_email


# Hard ceiling on the total extraction phase — never run longer than 10 minutes.
_EXTRACTION_TIMEOUT = 600

# Number of parallel HTTP workers for email extraction.
_MAX_WORKERS = 10

# Retry limit for the single batch write call.
_WRITE_RETRIES = 1


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments; only --dry-run is supported."""
    parser = argparse.ArgumentParser(
        description="Backfill the Email column for existing prospects in the Google Sheet."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run extraction but do not write any changes to the sheet.",
    )
    return parser.parse_args()


def read_all_rows(
    sheets_client: GoogleSheetsClient,
    sheet_id: str,
    sheet_name: str,
) -> tuple[list[str], list[list[str]]]:
    """Read the header row and all data rows from the sheet.

    Returns a (headers, data_rows) tuple. data_rows is a list of raw value
    lists — rows shorter than the header are NOT padded here; callers must
    pad as needed.

    Exits the process if the sheet cannot be read.
    """
    try:
        result = sheets_client.service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{sheet_name}!A:Z",
        ).execute()
    except HttpError as exc:
        print(f"ERROR: Could not read sheet — {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: Unexpected failure reading sheet — {exc}")
        sys.exit(1)

    rows = result.get("values", [])
    if not rows:
        print("Sheet appears empty — nothing to backfill.")
        sys.exit(0)

    headers = rows[0]
    data_rows = rows[1:]
    return headers, data_rows


def find_column_indices(headers: list[str]) -> tuple[int, int]:
    """Return (website_col_index, email_col_index) from the header row.

    Exits the process if either column is missing so callers never receive
    invalid indices.
    """
    missing = [col for col in ("Website", "Email") if col not in headers]
    if missing:
        print(f"ERROR: Required column(s) not found in sheet header: {missing}")
        print(f"       Headers present: {headers}")
        sys.exit(1)

    website_col = headers.index("Website")
    email_col = headers.index("Email")
    return website_col, email_col


def build_enrichment_queue(
    data_rows: list[list[str]],
    headers: list[str],
    website_col: int,
    email_col: int,
) -> list[dict[str, Any]]:
    """Return items describing each row that needs email extraction.

    Only includes rows where Website is non-empty and Email is empty.
    row_index is the 1-based Sheets row number (header is row 1,
    first data row is row 2).
    """
    queue = []
    for i, row in enumerate(data_rows):
        # Pad short rows so index access is always safe.
        padded = row + [""] * (len(headers) - len(row))
        website = padded[website_col].strip()
        email = padded[email_col].strip()

        if website and not email:
            queue.append({
                "row_index": i + 2,   # +1 for header row, +1 for 0-index
                "website": website,
            })

    return queue


def extract_emails_parallel(
    queue: list[dict[str, Any]],
) -> dict[int, str]:
    """Run extract_email() concurrently for all items in the queue.

    Returns a dict mapping row_index → email (empty string if not found).
    Applies a hard 10-minute ceiling on the entire extraction phase.
    """
    results: dict[int, str] = {}

    def _enrich(item: dict[str, Any]) -> tuple[int, str]:
        """Extract email for one row and return (row_index, email)."""
        email = extract_email(item["website"])
        return item["row_index"], email

    # --- Parallel extraction ---
    completed = 0
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {executor.submit(_enrich, item): item for item in queue}

        try:
            for future in as_completed(futures, timeout=_EXTRACTION_TIMEOUT):
                try:
                    row_index, email = future.result()
                    results[row_index] = email
                    completed += 1

                    # Progress update every 10 rows
                    if completed % 10 == 0:
                        print(f"  Progress: {completed}/{len(queue)} processed...")
                except Exception as exc:
                    print(f"  Warning: extraction failed for one row — {exc}")
        except TimeoutError:
            print(
                f"\nWarning: extraction phase hit the {_EXTRACTION_TIMEOUT}s ceiling "
                f"after {completed}/{len(queue)} rows. "
                "Writing partial results."
            )
            executor.shutdown(wait=False)

    return results


def build_batch_payload(
    results: dict[int, str],
    email_col: int,
    sheet_name: str,
) -> tuple[list[dict[str, Any]], int]:
    """Convert row_index→email results into a Sheets batchUpdate data payload.

    Returns (batch_data, emails_found_count). Only rows with a non-empty
    email are included in the payload so no blank values are written.

    email_col is 0-indexed; Sheets column letters are 1-indexed (A=0 → "A").
    This works for columns A–Z (indices 0–25); Email is column W (index 22).
    """
    col_letter = string.ascii_uppercase[email_col]
    batch_data = []
    emails_found = 0

    for row_index, email in results.items():
        if email:
            cell = f"{sheet_name}!{col_letter}{row_index}"
            batch_data.append({"range": cell, "values": [[email]]})
            emails_found += 1

    return batch_data, emails_found


def write_batch(
    sheets_client: GoogleSheetsClient,
    sheet_id: str,
    batch_data: list[dict[str, Any]],
) -> bool:
    """Write batch_data to the sheet in a single API call; retry once on failure.

    Returns True if the write succeeded, False if both attempts failed.
    """
    for attempt in range(1, _WRITE_RETRIES + 2):  # attempts: 1, 2
        try:
            sheets_client.service.spreadsheets().values().batchUpdate(
                spreadsheetId=sheet_id,
                body={"valueInputOption": "RAW", "data": batch_data},
            ).execute()
            return True
        except HttpError as exc:
            print(f"  Write attempt {attempt} failed: {exc}")
        except Exception as exc:
            print(f"  Write attempt {attempt} failed (unexpected): {exc}")

        if attempt <= _WRITE_RETRIES:
            print("  Retrying...")
            time.sleep(2)

    return False


def print_summary(
    total_rows: int,
    enrichment_queue_size: int,
    emails_found: int,
    dry_run: bool,
) -> None:
    """Print the final run summary to stdout."""
    sep = "=" * 50
    skipped = total_rows - enrichment_queue_size
    still_empty = enrichment_queue_size - emails_found
    success_rate = (
        f"{round(emails_found / enrichment_queue_size * 100)}%"
        if enrichment_queue_size
        else "N/A"
    )

    print(f"\n{sep}")
    print("EMAIL BACKFILL COMPLETE" + (" (DRY RUN)" if dry_run else ""))
    print(sep)
    print(f"Total prospects in sheet:  {total_rows}")
    print(f"Prospects with website:    {enrichment_queue_size}")
    print(f"Skipped (already have email or no website): {skipped}")
    print(f"Emails found:              {emails_found}")
    print(f"Success rate:              {success_rate}")
    print(f"Still empty after run:     {still_empty}")
    if dry_run:
        print("\nDRY RUN — no changes were written to the sheet.")
    print(sep)


def main() -> None:
    """Orchestrate the full backfill: read → filter → extract → write → summarise."""
    args = parse_args()
    config = load_config()

    # --- Initialise Sheets client ---
    sheets_client = GoogleSheetsClient(
        sheet_id=config.google_sheet_id,
        service_account_file=config.google_service_account_file,
        sheet_name=config.sheet_name,
    )

    # --- Read sheet ---
    print("Reading sheet...")
    headers, data_rows = read_all_rows(
        sheets_client, config.google_sheet_id, config.sheet_name
    )
    print(f"Read {len(data_rows)} data rows.")

    # --- Locate columns ---
    website_col, email_col = find_column_indices(headers)

    # --- Build enrichment queue ---
    queue = build_enrichment_queue(data_rows, headers, website_col, email_col)
    skipped = len(data_rows) - len(queue)
    print(f"Found {len(queue)} prospects to enrich.")
    print(f"Skipping {skipped} (already have email or no website).")

    if not queue:
        print("\nNothing to do — all eligible prospects already have an email.")
        sys.exit(0)

    # --- Extract emails in parallel ---
    print(f"\nExtracting emails in parallel (up to {_MAX_WORKERS} workers)...")
    results = extract_emails_parallel(queue)

    # --- Build batch payload ---
    batch_data, emails_found = build_batch_payload(
        results, email_col, config.sheet_name
    )

    # --- Dry-run: print preview and exit ---
    if args.dry_run:
        print(f"\nDRY RUN — would write {emails_found} email(s):")
        for entry in batch_data:
            print(f"  {entry['range']}  →  {entry['values'][0][0]}")
        print_summary(len(data_rows), len(queue), emails_found, dry_run=True)
        sys.exit(0)

    # --- Write to sheet ---
    if batch_data:
        print(f"\nWriting {emails_found} email(s) to sheet...")
        success = write_batch(sheets_client, config.google_sheet_id, batch_data)
        if success:
            print(f"Wrote {emails_found} emails to sheet.")
        else:
            print("ERROR: Batch write failed after retries. "
                  "Partial results may not have been saved.")
    else:
        print("\nNo emails found — nothing to write.")

    # --- Final summary ---
    print_summary(len(data_rows), len(queue), emails_found, dry_run=False)


if __name__ == "__main__":
    main()
