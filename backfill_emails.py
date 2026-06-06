"""backfill_emails.py

Fault-tolerant email backfill script for existing Google Sheet prospects.

Reads all rows, finds those with a Website but no Email, then processes them
in batches of 50 using a parallel ThreadPoolExecutor. Each batch is written to
the sheet immediately after it completes — no data is lost if the script is
interrupted. A JSON checkpoint file records which rows have been attempted so
--resume can skip them on the next run.

Run:
    python3 backfill_emails.py             # full live run
    python3 backfill_emails.py --dry-run   # extract and preview, no writes
    python3 backfill_emails.py --resume    # skip checkpointed rows, continue

Dependencies: same virtualenv as main.py (requests, google-api-python-client).
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import string
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from googleapiclient.errors import HttpError

from config import Config, load_config
from google_sheets import GoogleSheetsClient
from pipeline.social import extract_email

# Socket-level safety net — catches hangs that requests timeout alone misses.
# Must be set before any network calls are made, including SSL handshakes.
socket.setdefaulttimeout(5)

# Path to the checkpoint file written after every batch.
CHECKPOINT_FILE = "backfill_checkpoint.json"

# Number of rows to process in each parallel batch.
BATCH_SIZE = 50

# Parallel workers per batch — 5 keeps total open sockets manageable.
_MAX_WORKERS = 5

# Hard timeout for one full batch of 50 rows (60s = 1.2s average per site).
_BATCH_TIMEOUT = 60

# Per-future result() timeout — safety net on top of requests' 4s timeout.
_FUTURE_TIMEOUT = 5

# Retry limit for each batch write call.
_WRITE_RETRIES = 1


# --- CLI ---

def parse_args() -> argparse.Namespace:
    """Parse CLI args; supports --dry-run and --resume."""
    parser = argparse.ArgumentParser(
        description=(
            "Backfill the Email column for existing prospects in the Google Sheet. "
            "Processes in batches of 50, writes immediately, and checkpoints progress."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run extraction and print what would be written — no sheet writes.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Load checkpoint file and skip rows already processed.",
    )
    return parser.parse_args()


# --- Checkpoint ---

def load_checkpoint(resume: bool) -> set[int]:
    """Return the set of already-processed row indices from the checkpoint file.

    Returns an empty set when --resume is not passed or the file does not exist.
    """
    if not resume:
        return set()
    if not os.path.exists(CHECKPOINT_FILE):
        print(f"No checkpoint file found at {CHECKPOINT_FILE} — starting fresh.")
        return set()
    try:
        with open(CHECKPOINT_FILE) as f:
            rows = set(json.load(f))
        print(f"Resuming from checkpoint — {len(rows)} rows already processed.")
        return rows
    except Exception as exc:
        print(f"Warning: could not load checkpoint ({exc}) — starting fresh.")
        return set()


def save_checkpoint(completed_rows: set[int]) -> None:
    """Persist the completed row-index set to disk so --resume can use it."""
    try:
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump(list(completed_rows), f)
    except Exception as exc:
        print(f"Warning: checkpoint save failed — {exc}")


# --- Sheet helpers ---

def read_all_rows(
    sheets_client: GoogleSheetsClient,
    sheet_id: str,
    sheet_name: str,
) -> tuple[list[str], list[list[str]]]:
    """Read the header row and all data rows from the sheet.

    Returns (headers, data_rows). Exits the process on any read failure.
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

    return rows[0], rows[1:]


def find_column_indices(headers: list[str]) -> tuple[int, int]:
    """Return (website_col_index, email_col_index) from the live header row.

    Dynamic lookup so the script survives column reorders. Exits if missing.
    """
    missing = [col for col in ("Website", "Email") if col not in headers]
    if missing:
        print(f"ERROR: Required column(s) not found: {missing}")
        print(f"       Headers present: {headers}")
        sys.exit(1)
    return headers.index("Website"), headers.index("Email")


def build_enrichment_queue(
    data_rows: list[list[str]],
    headers: list[str],
    website_col: int,
    email_col: int,
) -> list[dict[str, Any]]:
    """Return queue items for rows that have a website but no email.

    row_index is the 1-based Sheets row number (header = row 1,
    first data row = row 2). Short rows are padded before index access.
    """
    queue = []
    for i, row in enumerate(data_rows):
        padded = row + [""] * (len(headers) - len(row))
        website = padded[website_col].strip()
        email = padded[email_col].strip()
        if website and not email:
            queue.append({"row_index": i + 2, "website": website})
    return queue


# --- Extraction ---

def extract_batch(batch: list[dict[str, Any]]) -> dict[int, str]:
    """Run extract_email() in parallel for one batch; return row_index → email.

    All rows in the batch are recorded in the result — empty string for rows
    where no email was found or that timed out. This ensures every attempted
    row is checkpointed even when extraction yields nothing.
    """
    results: dict[int, str] = {}

    def _enrich(item: dict[str, Any]) -> tuple[int, str]:
        """Extract email for one row and return (row_index, email)."""
        return item["row_index"], extract_email(item["website"])

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {executor.submit(_enrich, item): item for item in batch}

        try:
            for future in as_completed(futures, timeout=_BATCH_TIMEOUT):
                try:
                    row_index, email = future.result(timeout=_FUTURE_TIMEOUT)
                    results[row_index] = email
                except Exception:
                    # Record the row as attempted with no result.
                    results[futures[future]["row_index"]] = ""
        except TimeoutError:
            # Batch ceiling hit — mark any unfinished rows as attempted.
            remaining = len(batch) - len(results)
            print(f"  Warning: batch timed out — {remaining} row(s) marked as attempted.")
            for item in futures.values():
                if item["row_index"] not in results:
                    results[item["row_index"]] = ""

    return results


# --- Writing ---

def _make_sheets_client(config: Config) -> GoogleSheetsClient:
    """Create a fresh GoogleSheetsClient to avoid stale SSL on long runs."""
    return GoogleSheetsClient(
        sheet_id=config.google_sheet_id,
        service_account_file=config.google_service_account_file,
        sheet_name=config.sheet_name,
    )


def write_batch_results(
    results: dict[int, str],
    email_col: int,
    config: Config,
) -> int:
    """Write one batch of email results to the sheet; reconnects before each attempt.

    Returns the number of emails successfully written.
    Only non-empty emails are included in the write payload.
    """
    col_letter = string.ascii_uppercase[email_col]
    batch_data = [
        {"range": f"{config.sheet_name}!{col_letter}{row_index}", "values": [[email]]}
        for row_index, email in results.items()
        if email
    ]

    if not batch_data:
        return 0

    for attempt in range(1, _WRITE_RETRIES + 2):  # attempts: 1, 2
        # Fresh client on every attempt — prevents stale SSL connections.
        client = _make_sheets_client(config)
        try:
            client.service.spreadsheets().values().batchUpdate(
                spreadsheetId=config.google_sheet_id,
                body={"valueInputOption": "RAW", "data": batch_data},
            ).execute()
            print(f"  Wrote {len(batch_data)} email(s) to sheet.")
            return len(batch_data)
        except HttpError as exc:
            print(f"  Write attempt {attempt} failed: {exc}")
        except Exception as exc:
            print(f"  Write attempt {attempt} failed (unexpected): {exc}")

        if attempt <= _WRITE_RETRIES:
            print("  Retrying...")
            time.sleep(2)

    print(f"  ERROR: Write failed after {_WRITE_RETRIES + 1} attempts — {len(batch_data)} email(s) not saved.")
    return 0


# --- Summary ---

def print_summary(
    total_rows: int,
    total_to_enrich: int,
    processed_this_run: int,
    emails_found: int,
    dry_run: bool,
) -> None:
    """Print the final run summary."""
    sep = "=" * 50
    skipped = total_rows - total_to_enrich
    still_empty = total_to_enrich - emails_found
    success_rate = (
        f"{round(emails_found / total_to_enrich * 100)}%"
        if total_to_enrich
        else "N/A"
    )

    print(f"\n{sep}")
    print("EMAIL BACKFILL COMPLETE" + (" (DRY RUN)" if dry_run else ""))
    print(sep)
    print(f"Total prospects in sheet:              {total_rows}")
    print(f"Prospects needing enrichment:          {total_to_enrich}")
    print(f"Processed this run:                    {processed_this_run}")
    print(f"Skipped (email exists or no website):  {skipped}")
    print(f"Emails found:                          {emails_found}")
    print(f"Success rate:                          {success_rate}")
    print(f"Still empty after run:                 {still_empty}")
    if dry_run:
        print("\nDRY RUN — no changes were written to the sheet.")
    else:
        print(f"\nCheckpoint saved to: {CHECKPOINT_FILE}")
        print("Run with --resume to continue if interrupted.")
    print(sep)


# --- Orchestration ---

def main() -> None:
    """Orchestrate the full backfill: read → filter → batch extract → write → checkpoint."""
    args = parse_args()
    config = load_config()

    # --- Read sheet ---
    print("Reading sheet...")
    sheets_client = _make_sheets_client(config)
    headers, data_rows = read_all_rows(sheets_client, config.google_sheet_id, config.sheet_name)
    print(f"Read {len(data_rows)} data rows.")

    # --- Locate columns ---
    website_col, email_col = find_column_indices(headers)

    # --- Build full enrichment queue ---
    full_queue = build_enrichment_queue(data_rows, headers, website_col, email_col)
    print(f"Found {len(full_queue)} prospects needing enrichment (website present, email empty).")
    print(f"Skipping {len(data_rows) - len(full_queue)} (already have email or no website).")

    if not full_queue:
        print("\nNothing to do — all eligible prospects already have an email.")
        sys.exit(0)

    # --- Apply checkpoint filter ---
    completed_rows: set[int] = load_checkpoint(args.resume)
    queue = [item for item in full_queue if item["row_index"] not in completed_rows]

    if completed_rows and not args.resume:
        # Checkpoint exists but --resume not passed — warn and continue fresh.
        print(f"Note: checkpoint file exists with {len(completed_rows)} rows. "
              f"Pass --resume to skip them.")

    print(f"Rows to process this run: {len(queue)}")

    if not queue:
        print("\nAll rows already processed per checkpoint. Nothing to do.")
        sys.exit(0)

    # --- Process in batches ---
    total_batches = max(1, (len(queue) + BATCH_SIZE - 1) // BATCH_SIZE)
    total_emails_found = 0

    for batch_num, batch_start in enumerate(range(0, len(queue), BATCH_SIZE), 1):
        batch = queue[batch_start : batch_start + BATCH_SIZE]
        end_idx = batch_start + len(batch)

        print(
            f"\nBatch {batch_num}/{total_batches} "
            f"(rows {batch_start + 1}–{end_idx} of {len(queue)})"
        )

        # --- Extract ---
        batch_results = extract_batch(batch)
        batch_emails = sum(1 for e in batch_results.values() if e)
        print(f"  Emails found in batch: {batch_emails}/{len(batch)}")

        # --- Update completed set (mark attempted regardless of result) ---
        for row_index in batch_results:
            completed_rows.add(row_index)

        # --- Write or dry-run ---
        if args.dry_run:
            col_letter = string.ascii_uppercase[email_col]
            for row_index, email in batch_results.items():
                if email:
                    cell = f"{config.sheet_name}!{col_letter}{row_index}"
                    print(f"  DRY RUN: {cell}  →  {email}")
            total_emails_found += batch_emails
        else:
            written = write_batch_results(batch_results, email_col, config)
            total_emails_found += written
            # Save checkpoint after every successful batch write.
            save_checkpoint(completed_rows)

    # --- Final summary ---
    print_summary(
        total_rows=len(data_rows),
        total_to_enrich=len(full_queue),
        processed_this_run=len(queue),
        emails_found=total_emails_found,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
