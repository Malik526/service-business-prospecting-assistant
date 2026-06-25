"""backfill_emails.py

Fault-tolerant contact backfill script for existing Google Sheet prospects.

Reads all rows, finds those with a Website and missing requested contact fields,
then processes them in batches of 50 using a parallel ThreadPoolExecutor. Each
batch is written to the sheet immediately after it completes — no data is lost
if the script is interrupted. A JSON checkpoint file records which rows have
been attempted per field so --resume can skip them on the next run.

Run:
    python3 backfill_emails.py                          # email + Instagram
    python3 backfill_emails.py --skip-instagram         # email only
    python3 backfill_emails.py --skip-email             # Instagram only
    python3 backfill_emails.py --skip-email --skip-instagram

Dependencies: same virtualenv as main.py (requests, google-api-python-client).
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeoutError,
    as_completed,
)
from multiprocessing import Process, Queue
from queue import Empty
from typing import Any

from googleapiclient.errors import HttpError

from config import Config, load_config
from google_sheets import GoogleSheetsClient, SheetSchema, column_index_to_letter
from pipeline.social import extract_email, extract_instagram_url

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

# Hard timeout for one website contact extraction process.
_CONTACT_PROCESS_TIMEOUT = 15

# Retry limit for each batch write call.
_WRITE_RETRIES = 1


# --- CLI ---

def parse_args() -> argparse.Namespace:
    """Parse CLI args for live/dry-run backfill target selection."""
    parser = argparse.ArgumentParser(
        description=(
            "Backfill Email and Instagram URL columns for existing prospects. "
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
    parser.add_argument(
        "--skip-email",
        action="store_true",
        help="Do not extract or write missing Email values.",
    )
    parser.add_argument(
        "--skip-instagram",
        action="store_true",
        help="Do not extract or write missing Instagram URL values.",
    )
    return parser.parse_args()


def selected_targets(args: argparse.Namespace) -> list[str]:
    """Return the contact fields selected by CLI flags."""
    targets = []
    if not args.skip_email:
        targets.append("email")
    if not args.skip_instagram:
        targets.append("instagram_url")
    return targets


# --- Checkpoint ---

def load_checkpoint(resume: bool) -> dict[str, set[int]]:
    """Return already-processed row indices per target field.

    Returns empty target sets when --resume is not passed or the file does not
    exist. Older checkpoint files stored a plain row list for email-only runs;
    those are treated as completed email rows for backward compatibility.
    """
    empty_checkpoint = {"email": set(), "instagram_url": set()}
    if not resume:
        return empty_checkpoint
    if not os.path.exists(CHECKPOINT_FILE):
        print(f"No checkpoint file found at {CHECKPOINT_FILE} — starting fresh.")
        return empty_checkpoint
    try:
        with open(CHECKPOINT_FILE) as f:
            payload = json.load(f)

        if isinstance(payload, list):
            checkpoint = {"email": set(payload), "instagram_url": set()}
        else:
            checkpoint = {
                "email": set(payload.get("email", [])),
                "instagram_url": set(payload.get("instagram_url", [])),
            }

        completed_count = sum(len(rows) for rows in checkpoint.values())
        print(f"Resuming from checkpoint — {completed_count} field attempt(s) already processed.")
        return checkpoint
    except Exception as exc:
        print(f"Warning: could not load checkpoint ({exc}) — starting fresh.")
        return empty_checkpoint


def save_checkpoint(completed_rows: dict[str, set[int]]) -> None:
    """Persist completed row-index sets per target field for --resume."""
    try:
        with open(CHECKPOINT_FILE, "w") as f:
            payload = {
                target: sorted(rows)
                for target, rows in completed_rows.items()
            }
            json.dump(payload, f)
    except Exception as exc:
        print(f"Warning: checkpoint save failed — {exc}")


# --- Sheet helpers ---

def read_all_rows(
    sheets_client: GoogleSheetsClient,
    sheet_id: str,
    sheet_name: str,
) -> tuple[SheetSchema, list[list[str]]]:
    """Read and verify the dynamic schema plus all data rows from the sheet.

    Returns (schema, data_rows). Exits the process on any read failure.
    """
    try:
        schema = sheets_client.ensure_header()
        data_rows = sheets_client.get_data_rows(schema)
    except HttpError as exc:
        print(f"ERROR: Could not read sheet — {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: Unexpected failure reading sheet — {exc}")
        sys.exit(1)

    if not schema.headers:
        print("Sheet appears empty — nothing to backfill.")
        sys.exit(0)

    return schema, data_rows


def find_column_indices(
    schema: SheetSchema,
    targets: list[str],
) -> tuple[int, dict[str, int]]:
    """Return website and selected contact columns from the live schema.

    Dynamic lookup so the script survives column reorders. Exits if missing.
    """
    target_to_header = {
        "email": "Email",
        "instagram_url": "Instagram URL",
    }
    required_headers = ["Website"] + [target_to_header[target] for target in targets]
    missing = [col for col in required_headers if col not in schema.columns]
    if missing:
        print(f"ERROR: Required column(s) not found: {missing}")
        print(f"       Headers present: {schema.headers}")
        sys.exit(1)

    contact_cols = {
        target: schema.columns[target_to_header[target]]
        for target in targets
    }
    return schema.columns["Website"], contact_cols


def build_enrichment_queue(
    data_rows: list[list[str]],
    schema: SheetSchema,
    website_col: int,
    contact_cols: dict[str, int],
    targets: list[str],
) -> list[dict[str, Any]]:
    """Return rows that have a website and missing requested contact fields.

    row_index is the 1-based Sheets row number (header = row 1,
    first data row = row 2). Short rows are padded before index access.
    """
    queue = []
    business_col = schema.columns.get("Business Name")
    for i, row in enumerate(data_rows):
        padded = row + [""] * (len(schema.headers) - len(row))
        website = padded[website_col].strip()
        if not website:
            continue

        needed_targets = [
            target
            for target in targets
            if not padded[contact_cols[target]].strip()
        ]
        if targets and not needed_targets:
            continue

        business_name = (
            padded[business_col].strip()
            if business_col is not None
            else ""
        )
        queue.append(
            {
                "row_index": i + 2,
                "business_name": business_name,
                "website": website,
                "targets": needed_targets,
            }
        )
    return queue


# --- Extraction ---

def _extract_contact_process(
    website: str,
    targets: list[str],
    result_queue: Queue,
) -> None:
    """Run selected extractors in a child process and return results through a queue."""
    results = {"email": "", "instagram_url": ""}
    try:
        if "email" in targets:
            results["email"] = extract_email(website)
        if "instagram_url" in targets:
            results["instagram_url"] = extract_instagram_url(website)
        result_queue.put(results)
    except Exception:
        result_queue.put(results)


def _extract_contact_with_process_timeout(
    website: str,
    targets: list[str],
) -> dict[str, str]:
    """Run selected contact extraction with a killable process-level timeout."""
    result_queue: Queue = Queue(maxsize=1)
    process = Process(target=_extract_contact_process, args=(website, targets, result_queue))
    process.daemon = True
    process.start()
    process.join(_CONTACT_PROCESS_TIMEOUT)

    if process.is_alive():
        process.terminate()
        process.join(1)
        if process.is_alive():
            process.kill()
            process.join()
        return {"email": "", "instagram_url": ""}

    try:
        return result_queue.get_nowait()
    except Empty:
        return {"email": "", "instagram_url": ""}


def extract_batch(batch: list[dict[str, Any]]) -> dict[int, dict[str, str]]:
    """Run selected contact extractors for one batch.

    All rows in the batch are recorded in the result — empty string for rows
    where nothing was found or that timed out. This ensures every attempted row
    is checkpointed for the requested fields even when extraction yields nothing.
    """
    results: dict[int, dict[str, str]] = {}

    def _enrich(item: dict[str, Any]) -> tuple[int, dict[str, str]]:
        """Extract selected contact fields for one row."""
        values = _extract_contact_with_process_timeout(item["website"], item["targets"])
        return item["row_index"], values

    executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS)
    timed_out = False
    try:
        futures = {executor.submit(_enrich, item): item for item in batch}

        try:
            for future in as_completed(futures, timeout=_BATCH_TIMEOUT):
                try:
                    row_index, values = future.result(timeout=_FUTURE_TIMEOUT)
                    results[row_index] = values
                except Exception:
                    # Record the row as attempted with no result.
                    results[futures[future]["row_index"]] = {"email": "", "instagram_url": ""}
        except FuturesTimeoutError:
            timed_out = True
            unfinished = [
                (future, item)
                for future, item in futures.items()
                if not future.done()
            ]
            print(
                f"  Batch timeout: {len(unfinished)} unfinished futures. "
                "Skipping unfinished websites."
            )
            for future, item in unfinished:
                row_index = item["row_index"]
                business_name = item.get("business_name") or "[unknown business]"
                website = item["website"]
                print(f"    Skipped row {row_index}: {business_name} — {website}")
                future.cancel()
    finally:
        executor.shutdown(wait=not timed_out, cancel_futures=timed_out)

    return results


def apply_checkpoint_filter(
    queue: list[dict[str, Any]],
    completed_rows: dict[str, set[int]],
) -> list[dict[str, Any]]:
    """Remove target fields already attempted for each row from the queue."""
    filtered_queue = []
    for item in queue:
        remaining_targets = [
            target
            for target in item["targets"]
            if item["row_index"] not in completed_rows.get(target, set())
        ]
        if not remaining_targets:
            continue

        filtered_item = item.copy()
        filtered_item["targets"] = remaining_targets
        filtered_queue.append(filtered_item)

    return filtered_queue


# --- Writing ---

def _make_sheets_client(config: Config) -> GoogleSheetsClient:
    """Create a fresh GoogleSheetsClient to avoid stale SSL on long runs."""
    return GoogleSheetsClient(
        sheet_id=config.google_sheet_id,
        service_account_file=config.google_service_account_file,
        sheet_name=config.sheet_name,
    )


def write_batch_results(
    results: dict[int, dict[str, str]],
    contact_cols: dict[str, int],
    config: Config,
) -> int:
    """Write one batch of contact results to the sheet; reconnects per attempt.

    Returns the number of non-empty contact values successfully written.
    Only non-empty values are included in the write payload.
    """
    batch_data = []
    for row_index, values in results.items():
        for target, value in values.items():
            if not value or target not in contact_cols:
                continue

            col_letter = column_index_to_letter(contact_cols[target])
            batch_data.append(
                {"range": f"{config.sheet_name}!{col_letter}{row_index}", "values": [[value]]}
            )

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
            print(f"  Wrote {len(batch_data)} contact value(s) to sheet.")
            return len(batch_data)
        except HttpError as exc:
            print(f"  Write attempt {attempt} failed: {exc}")
        except Exception as exc:
            print(f"  Write attempt {attempt} failed (unexpected): {exc}")

        if attempt <= _WRITE_RETRIES:
            print("  Retrying...")
            time.sleep(2)

    print(
        f"  ERROR: Write failed after {_WRITE_RETRIES + 1} attempts — "
        f"{len(batch_data)} contact value(s) not saved."
    )
    return 0


# --- Summary ---

def print_summary(
    total_rows: int,
    total_to_enrich: int,
    processed_this_run: int,
    emails_found: int,
    instagram_found: int,
    targets: list[str],
    dry_run: bool,
) -> None:
    """Print the final run summary."""
    sep = "=" * 50
    skipped = total_rows - total_to_enrich
    values_found = emails_found + instagram_found

    print(f"\n{sep}")
    print("CONTACT BACKFILL COMPLETE" + (" (DRY RUN)" if dry_run else ""))
    print(sep)
    print(f"Total prospects in sheet:              {total_rows}")
    print(f"Requested targets:                     {', '.join(targets) if targets else 'none'}")
    print(f"Prospects needing enrichment:          {total_to_enrich}")
    print(f"Processed this run:                    {processed_this_run}")
    print(f"Skipped (complete or no website):      {skipped}")
    if "email" in targets:
        print(f"Emails found:                          {emails_found}")
    if "instagram_url" in targets:
        print(f"Instagram URLs found:                  {instagram_found}")
    print(f"Contact values found:                  {values_found}")
    if dry_run:
        print("\nDRY RUN — no changes were written to the sheet.")
    elif not targets:
        print("\nNo targets selected — no extraction or writes were performed.")
    else:
        print(f"\nCheckpoint saved to: {CHECKPOINT_FILE}")
        print("Run with --resume to continue if interrupted.")
    print(sep)


# --- Orchestration ---

def main() -> None:
    """Orchestrate the full backfill from read to checkpoint."""
    args = parse_args()
    targets = selected_targets(args)
    config = load_config()

    # --- Read sheet ---
    print("Reading sheet...")
    sheets_client = _make_sheets_client(config)
    schema, data_rows = read_all_rows(
        sheets_client,
        config.google_sheet_id,
        config.sheet_name,
    )
    print(f"Read {len(data_rows)} data rows.")

    # --- Locate columns ---
    website_col, contact_cols = find_column_indices(schema, targets)

    # --- Build full enrichment queue ---
    full_queue = build_enrichment_queue(data_rows, schema, website_col, contact_cols, targets)
    print(
        f"Found {len(full_queue)} prospects needing enrichment "
        "(website present, requested field empty)."
    )
    print(f"Skipping {len(data_rows) - len(full_queue)} (already complete or no website).")

    if not targets:
        print("\nBoth --skip-email and --skip-instagram were passed.")
        print("No extraction or sheet writes will be performed.")
        sys.exit(0)

    # --- Apply checkpoint filter ---
    if not full_queue:
        print("\nNothing to do — all eligible prospects already have requested contact data.")
        sys.exit(0)

    completed_rows = load_checkpoint(args.resume)
    queue = apply_checkpoint_filter(full_queue, completed_rows)

    checkpoint_count = sum(len(rows) for rows in completed_rows.values())
    if checkpoint_count and not args.resume:
        # Checkpoint exists but --resume not passed — warn and continue fresh.
        print(f"Note: checkpoint file exists with {checkpoint_count} field attempt(s). "
              f"Pass --resume to skip them.")

    print(f"Rows to process this run: {len(queue)}")

    if not queue:
        print("\nAll rows already processed per checkpoint. Nothing to do.")
        sys.exit(0)

    # --- Process in batches ---
    total_batches = max(1, (len(queue) + BATCH_SIZE - 1) // BATCH_SIZE)
    total_emails_found = 0
    total_instagram_found = 0

    for batch_num, batch_start in enumerate(range(0, len(queue), BATCH_SIZE), 1):
        batch = queue[batch_start : batch_start + BATCH_SIZE]
        end_idx = batch_start + len(batch)

        print(
            f"\nBatch {batch_num}/{total_batches} "
            f"(rows {batch_start + 1}–{end_idx} of {len(queue)})"
        )

        # --- Extract ---
        batch_results = extract_batch(batch)
        batch_emails = sum(1 for values in batch_results.values() if values.get("email"))
        batch_instagram = sum(1 for values in batch_results.values() if values.get("instagram_url"))
        if "email" in targets:
            print(f"  Emails found in batch: {batch_emails}/{len(batch)}")
        if "instagram_url" in targets:
            print(f"  Instagram URLs found in batch: {batch_instagram}/{len(batch)}")

        # --- Update completed set (mark attempted requested targets regardless of result) ---
        batch_targets_by_row = {item["row_index"]: item["targets"] for item in batch}
        for row_index in batch_results:
            for target in batch_targets_by_row.get(row_index, []):
                completed_rows.setdefault(target, set()).add(row_index)

        # --- Write or dry-run ---
        if args.dry_run:
            for row_index, values in batch_results.items():
                for target, value in values.items():
                    if not value or target not in contact_cols:
                        continue
                    col_letter = column_index_to_letter(contact_cols[target])
                    cell = f"{config.sheet_name}!{col_letter}{row_index}"
                    print(f"  DRY RUN: {cell}  →  {value}")
            total_emails_found += batch_emails
            total_instagram_found += batch_instagram
        else:
            write_batch_results(batch_results, contact_cols, config)
            total_emails_found += batch_emails
            total_instagram_found += batch_instagram
            # Save checkpoint after every successful batch write.
            save_checkpoint(completed_rows)

    # --- Final summary ---
    print_summary(
        total_rows=len(data_rows),
        total_to_enrich=len(full_queue),
        processed_this_run=len(queue),
        emails_found=total_emails_found,
        instagram_found=total_instagram_found,
        targets=targets,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
