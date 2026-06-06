# Changelog

---

## [2026-06-06] — fix: rewrite backfill_emails.py to prevent hangs at high volume

**Files Modified:** `backfill_emails.py`

### Root Cause
The original script submitted all futures (up to 1100+) to one `ThreadPoolExecutor`
at once and waited for them under a single 10-minute ceiling. When slow or hanging
sites accumulated, the OS exhausted its socket quota and new connections stalled
indefinitely. The `requests` timeout parameter controls read/write timeouts but
does not reliably cancel an SSL handshake that never completes — so individual
workers hung without triggering the Python-level timeout, eventually blocking the
entire executor.

### Fix 1 — Socket-level timeout (`socket.setdefaulttimeout(5)`)
Added at module level, before any network calls. This catches connection hangs
that occur at the SSL handshake stage before `requests` even takes over. Acts as
a hard OS-level safety net regardless of what the HTTP layer does.

### Fix 2 — Reduced workers from 10 → 5
Fewer concurrent workers means fewer simultaneous open sockets, which reduces
the chance of hitting OS-level socket exhaustion on a large backfill run.

### Fix 3 — Batch processing (BATCH_SIZE = 50)
Instead of submitting all rows at once, the script now processes 50 rows per
`ThreadPoolExecutor` context. Each batch has its own `as_completed(timeout=60)`
and `future.result(timeout=5)` double guard:
- `as_completed(timeout=60)` — entire batch must complete in 60 seconds
  (1.2 seconds average per site).
- `future.result(timeout=5)` — individual future result() call safety cap.
- On `TimeoutError`, remaining futures in the batch are marked as attempted
  (empty string) and the loop continues with the next batch.

### Fix 4 — Write immediately after each batch
The original script collected all results then wrote at the very end. If it
hung, all collected emails were lost. Now `write_batch_results()` is called
after every batch of 50, so at most 50 rows' results can be lost on interrupt.
Each write call creates a fresh `GoogleSheetsClient` to prevent stale SSL
connections from accumulating over a long multi-batch run.

### Fix 5 — Checkpoint + `--resume` flag
A JSON checkpoint file (`backfill_checkpoint.json`) is saved after every
successful batch write. It stores the set of all attempted row indices
(both found and not-found). `--resume` loads this file and filters the
enrichment queue to skip already-processed rows, so the script can be
interrupted with Ctrl+C and restarted from where it stopped.

### New constants
| Name | Value | Purpose |
|---|---|---|
| `CHECKPOINT_FILE` | `backfill_checkpoint.json` | Persists progress across runs |
| `BATCH_SIZE` | `50` | Rows per executor context |
| `_MAX_WORKERS` | `5` | Parallel threads per batch |
| `_BATCH_TIMEOUT` | `60` | Seconds ceiling per batch |
| `_FUTURE_TIMEOUT` | `5` | Per-future `result()` cap |

### New functions
- `load_checkpoint(resume: bool) → set[int]` — reads checkpoint file when `--resume` is passed
- `save_checkpoint(completed_rows: set[int])` — writes checkpoint file after each batch
- `extract_batch(batch) → dict[int, str]` — runs one batch with all timeout guards
- `write_batch_results(results, email_col, config) → int` — writes one batch; fresh client per attempt
- `_make_sheets_client(config)` — creates a fresh `GoogleSheetsClient` (used by write and read)

### Run commands
```
python3 backfill_emails.py             # fresh run
python3 backfill_emails.py --dry-run   # preview only, no writes
python3 backfill_emails.py --resume    # continue from checkpoint
```

### Expected performance for 1105 rows
- ~22 batches × ~60s max per batch = under 22 minutes worst case
- Typical (most sites respond in < 4s): 5–10 minutes total
- Checkpoint saves after every batch — safe to Ctrl+C and resume at any point

---

## [2026-06-06] — feat: add backfill_emails.py — parallel email enrichment for existing sheet rows

**Files Added:** `backfill_emails.py`

### What This Script Does
One-shot enrichment tool for the existing Google Sheet. Reads all prospect rows,
identifies rows where the Website column is populated but the Email column is empty,
runs `extract_email()` on all matching websites in parallel, and writes the results
back to the sheet in a single batch API call.

### Script Structure

**`parse_args()`**
- Accepts one optional flag: `--dry-run`.
- Dry-run mode runs the full extraction but prints what would be written instead
  of sending any API write calls.

**`read_all_rows()`**
- Uses `sheets_client.service.spreadsheets().values().get()` with `A:Z` range so
  it captures all columns regardless of sheet width.
- Exits cleanly with a printed error message on any `HttpError` or unexpected
  exception — never crashes with a raw traceback.

**`find_column_indices()`**
- Dynamically resolves `"Website"` and `"Email"` column indices from the live
  header row, so the script continues to work correctly if columns are reordered
  or new columns are added.
- Exits with a clear error if either column is missing.

**`build_enrichment_queue()`**
- Pads short rows to the full header width before index access (avoids
  `IndexError` on rows with trailing empty cells).
- Returns only rows where `website` is non-empty AND `email` is empty —
  never overwrites existing email values.
- `row_index` is the correct 1-based Sheets row number (`i + 2`:
  +1 for the header row, +1 for 0-based list index).

**`extract_emails_parallel()`**
- `ThreadPoolExecutor(max_workers=10)` — up to 10 sites in flight at once.
- Hard 10-minute ceiling via `as_completed(timeout=600)`. On `TimeoutError`,
  the executor is shut down without waiting and partial results are returned —
  never hangs the terminal.
- Prints progress every 10 rows so the user can see it's working.

**`build_batch_payload()`**
- Converts `row_index → email` results into Sheets `batchUpdate` data format.
- Uses `string.ascii_uppercase[email_col]` to derive the column letter (Email
  is column W, index 22 — safely within the A–Z range).
- Only includes rows with a non-empty email so no blank cells are written.

**`write_batch()`**
- Sends one `batchUpdate` API call for all results — O(1) API calls regardless
  of how many rows are updated.
- Retries once on failure with a 2-second pause before the second attempt.
- Returns `True`/`False` so the caller can print an appropriate message.

**`print_summary()`**
- Prints total prospects, prospects with website, skipped count, emails found,
  success rate, and still-empty count.
- Appends `(DRY RUN)` to the header line when applicable.

### Run Commands
```
cd ~/growth_agency/internal-tools/service-business-prospecting-assistant
source .venv/bin/activate

python3 backfill_emails.py            # live run
python3 backfill_emails.py --dry-run  # preview only
```

### What Is Not Overwritten
- Rows that already have an email in column W are excluded from the queue
  before any network calls are made.
- Rows with no website are skipped entirely.
- The batch payload only contains entries where `extract_email()` returned a
  non-empty string — blank results are never written.

### Verification Steps
1. Run `--dry-run` first to confirm the queue size and preview emails.
2. Run live and confirm the console shows `Wrote N emails to sheet`.
3. In the Google Sheet, spot-check column W for several rows:
   - Rows with a website and previously empty email → populated.
   - Rows without a website → unchanged.
   - Rows that already had an email → unchanged.
4. Row numbers in column W must match the correct business rows — no off-by-one.

---

## [2026-06-06] — feat: add parallel email extraction to prospecting pipeline

**Files Modified:** `pipeline/social.py`, `google_sheets.py`, `main.py`

### What Changed

**pipeline/social.py — new `extract_email()` function**
- Added `extract_email(website_url: str) -> str` directly below `extract_instagram_url()`.
- Two-pass strategy: fetches the homepage first, then `/contact` as a fallback.
- Within each page, checks `mailto:` href links before falling back to plain-text
  email-pattern scanning — mailto links are the most authoritative signal.
- Filters out framework/platform emails via `_IGNORE_EMAIL_DOMAINS` list:
  `sentry.io`, `wixpress.com`, `squarespace.com`, `wordpress.com`, `example.com`,
  `googleapis.com`, `schema.org`, `w3.org`.
- Skips `noreply@` and `no-reply@` prefixes — never a business contact.
- Hard 4-second timeout per HTTP request (`_EMAIL_TIMEOUT = 4`) shared with
  `_USER_AGENT` already defined in the module.
- Never raises exceptions — all errors are caught and logged at WARNING level;
  empty string returned on any failure.
- Updated module docstring to describe both extractors and note thread-safety.

**google_sheets.py — Email column added (W)**
- Appended `"Email"` to the end of `SHEET_COLUMNS` (position 23, column W).
- Updated `_LAST_COL` from `"V"` to `"W"` (23 columns total: A through W).
- Updated module docstring column layout table to include column W with description.
- Added `prospect.get("email", "")` to the end of `prospect_to_sheet_row()`.

**main.py — Parallel extraction replacing sequential stub**
- Added `import logging`, `import time`, and
  `from concurrent.futures import ThreadPoolExecutor, as_completed` at the top.
- Added `logger = logging.getLogger(__name__)` at module level.
- Removed `enriched["instagram_url"] = ""` stub from the deduplication loop.
- After the loop, new parallel extraction block:
  - Filters to `prospects_with_sites` (those with a `website` field).
  - Defines `enrich_prospect()` — calls both `extract_email()` and
    `extract_instagram_url()` for one prospect; import kept inline to avoid
    circular-import issues.
  - Runs with `ThreadPoolExecutor(max_workers=10)` — up to 10 sites in flight
    at once, bounded by `as_completed(timeout=180)`.
  - Hard 3-minute ceiling (`EXTRACTION_TIMEOUT = 180`): if elapsed time exceeds
    the ceiling, logs a warning, shuts the executor down without waiting, and
    breaks — partial results are kept and written to the sheet.
  - Fallback loop sets `email = ""` and `instagram_url = ""` on any prospect
    that wasn't reached before the ceiling.
  - Logs summary counts on completion: `emails: N, instagram: N`.
- `print_summary()` updated:
  - Docstring updated to list the new "Contact data extraction results" section.
  - New "Contact Data Extraction" block printed between Website Coverage and
    Lead Score Distribution showing:
    `Emails found: X / Y prospects with websites`
    `Instagram URLs: X / Y prospects with websites`

### Column Safety
- Columns A through V are completely unchanged — all existing rows are unaffected.
- Column W (`Email`) will be empty for all existing rows; new prospects
  auto-populate it when the website has a publicly listed contact email.

### Why Parallel
Per-prospect HTTP fetches ran sequentially in the previous Instagram extractor,
adding 0–5 seconds per site and causing SSL timeout failures at scale (60+ prospects).
This implementation runs both extractors concurrently with a hard ceiling so the
total pipeline time grows by at most 3 minutes regardless of prospect count.

### Verification Steps
```
cd ~/growth_agency/internal-tools/service-business-prospecting-assistant
source .venv/bin/activate
python3 main.py --zip 11375 --radius 5
```
Confirm:
1. Pipeline completes in under 5 minutes total.
2. No hanging or indefinite waits — each request caps at 4 seconds.
3. New column W header `Email` appears in Google Sheet.
4. Businesses with publicly listed emails populate column W.
5. Console report shows `Contact Data Extraction` section with counts.
6. All other columns (A–V) and pipeline stages are unaffected.

---

## [2026-05-27] — chore: disable Instagram URL extraction; preserve column for manual entry

**Files Modified:** `main.py`, `pipeline/social.py`

### What Changed

**main.py — Extraction block removed**
- Removed the conditional `if enriched.get("website")` block that called
  `extract_instagram_url()` and its inline `from pipeline.social import` statement.
- Replaced with a single unconditional assignment: `enriched["instagram_url"] = ""`.
  The field is still written to every prospect dict so the Google Sheet column (V)
  continues to receive a value on every row — it is just always empty.

**main.py — `print_summary()` Instagram section removed**
- Removed the "Instagram URL Coverage" section (count and percentage block) that
  would always show 0 / 0.0% with extraction disabled. The Website Coverage and
  Lead Score sections are unaffected.

**pipeline/social.py — Disable comment added**
- Added a four-line comment block immediately after the module docstring explaining
  that extraction is disabled, why (performance impact at scale), and exactly how
  to re-enable it (import and call `extract_instagram_url()` in `main.py`).
- The file, function, and all implementation code are fully preserved.

### What Was Kept
- `pipeline/social.py` — file intact, function intact, ready to re-enable.
- `"Instagram URL"` column V in `google_sheets.py` — unchanged; rows will have an
  empty string written automatically, which keeps the column present and available
  for manual entry in the sheet.
- All other pipeline functionality — unchanged.

### Why
Per-prospect HTTP fetches added 0–5 seconds per site at the tail of each enrichment
loop iteration. At scale (60+ prospects per run) this caused SSL timeout errors and
significantly slowed pipeline completion. The column is preserved so high-priority
prospects can have Instagram URLs entered manually after the run.

### Verification Steps
```
cd ~/growth_agency/internal-tools/service-business-prospecting-assistant
source .venv/bin/activate
python3 main.py --zip 07032 --radius 15
```
Confirm:
1. Pipeline completes without SSL timeout errors.
2. Console report has no "Instagram URL Coverage" section.
3. Google Sheet column V (`Instagram URL`) exists with empty cells for new rows.
4. All other columns (A–U) populate correctly.

---

## [2026-05-27] — feat: add Instagram URL extraction to prospecting pipeline

**Files Added:** `pipeline/social.py`
**Files Modified:** `google_sheets.py`, `main.py`, `pipeline/__init__.py`

### What Changed

**pipeline/social.py — New file**
- New module `extract_instagram_url(website_url: str) -> str` that fetches a business
  website and scans the HTML for any `href` containing `instagram.com/`.
- Uses `requests` with a 5-second timeout and a realistic `User-Agent` header to reduce
  bot-detection blocks.
- Extracts the matched URL, prepends `https://` if no scheme is present, and strips
  trailing slashes for consistent formatting.
- Returns empty string on any exception (timeout, connection error, HTTP error) —
  never propagates an error into the main pipeline.
- Logs `WARNING`-level messages when a site is unreachable or times out.

**google_sheets.py — Column layout (A–U → A–V)**
- Appended one new column to the END of `SHEET_COLUMNS` (position 22, column V):
  `"Instagram URL"` — extracted from the business website; auto-populated on creation.
- Updated `_LAST_COL` from `"U"` to `"V"` (22 columns total: A through V).
- Updated module docstring column layout table to include column V with description.
- Added `prospect.get("instagram_url", "")` to the end of `prospect_to_sheet_row()`.

**main.py — Instagram extraction in the enrichment loop**
- After `enrich_with_score()`, conditionally calls `extract_instagram_url()` for each
  new prospect that has a `website` field.
- Prospects without a website get `instagram_url = ""` without any network call.
- Import of `pipeline.social` is kept inline (inside the loop) to avoid circular-import
  issues during module initialization.

**main.py — `print_summary()` Instagram coverage block**
- Added an "Instagram URL Coverage" section between Website Coverage and Lead Score
  Distribution, showing count and percentage of new prospects with an Instagram URL.

**pipeline/__init__.py**
- Updated module list docstring to include `social.py`.

### Column Safety
- Columns A through U are completely unchanged — all existing rows are unaffected.
- Column V will be empty for all existing rows; new prospects auto-populate it when
  a website is present and the site links to Instagram.

### Verification Steps
```
cd ~/growth_agency/internal-tools/service-business-prospecting-assistant
source .venv/bin/activate
python3 main.py --zip 11375 --radius 5
```
Confirm:
1. New column V header `Instagram URL` appears in Google Sheet.
2. Businesses with websites that link Instagram show the URL in column V.
3. Businesses without a website show an empty string in column V.
4. Console report includes "Instagram URL Coverage" section.
5. Pipeline runtime is not significantly slower (5-second cap per site).

### Anything To Watch
- Best-effort only: not every business links Instagram from their homepage.
- Sites using JavaScript-rendered links (React/Vue SPAs) will not have the link
  in the initial HTML response — `extract_instagram_url` only parses the raw response body.
- The 5-second timeout means slow sites are skipped rather than stalling the run.
- Businesses with no website will always return empty — this is intentional.

---

## [2026-05-21] — feat: add search params, date tracking columns, and expanded status options

**Files Modified:** `google_sheets.py`, `main.py`

### What Changed

**google_sheets.py — Column layout (A–Q → A–U)**
- Appended four new columns to the END of `SHEET_COLUMNS` (positions 18–21, columns R–U):
  - `"Search ZIP Code"` (R) — ZIP code used in the discovery run, auto-populated from CLI args
  - `"Search Radius (mi)"` (S) — radius used in the discovery run, auto-populated from CLI args
  - `"Date Contacted"` (T) — date of first outreach attempt; left empty on creation, manual entry only
  - `"Follow-Up Date"` (U) — date of next intended follow-up; left empty on creation, manual entry only
- Updated `_LAST_COL` from `"Q"` to `"U"` (21 columns total: A through U)
- Updated column layout docstring at the top of the file to reflect the full A–U layout with column letters and descriptions

**google_sheets.py — `prospect_to_sheet_row()`**
- Appended four new fields at the end of the return list, matching the new SHEET_COLUMNS order exactly:
  `search_zip`, `search_radius`, `date_contacted`, `follow_up_date`
- Added `# --- Manually updated fields ---` comment block above these four lines explaining auto-populate vs. manual-entry intent

**google_sheets.py — `STATUS_OPTIONS`**
- Replaced the previous 10-option list with an expanded 18-option list covering the full outreach lifecycle:
  `New → Reviewed → Good Fit / Not Fit → Called → Contacted → FollowUp 1/2/3 → Interested → Demo Booked → Proposal Sent → Negotiating → Meeting Booked → Client`
  Dead-end statuses: `Not Interested`, `Ghosted`, `Do Not Contact`
- Updated the STATUS_OPTIONS docstring to show the full stage progression

**main.py — Search parameter tagging**
- Inside the deduplication loop, added two lines BEFORE `enrich_with_score()` to tag each prospect with the run's CLI parameters:
  `prospect["search_zip"] = args.zip_code` and `prospect["search_radius"] = args.radius`
- `date_contacted` and `follow_up_date` are intentionally NOT set here — manual entry only

### Column Safety
- Columns A through Q are completely unchanged — existing 341 rows are unaffected and not shifted
- Columns R–U will be empty for all existing rows; new prospects auto-populate R and S; T and U remain empty on creation

### Verification Steps
```
cd ~/growth_agency/internal-tools/service-business-prospecting-assistant
source .venv/bin/activate
python3 main.py --zip 11375 --radius 5
```
Confirm in Google Sheets:
1. Columns A–Q unchanged and aligned for all existing rows
2. Column headers R → `Search ZIP Code`, S → `Search Radius (mi)`, T → `Date Contacted`, U → `Follow-Up Date`
3. New prospect rows show correct ZIP and radius in R and S; T and U empty
4. Status dropdown on all rows shows the full 18-option list

### Anything To Watch
- The `ensure_header()` call will rewrite the header row if it detects a mismatch (R–U headers will be added on first run)
- The `apply_status_dropdown()` call is idempotent — it updates the validation rule on every run without resetting existing cell values
- Existing rows with old status values (`"Followed Up"` → replaced by `"FollowUp 1/2/3"`) will show a validation warning in Sheets until manually updated; they are not corrupted

---

## [2026-05-21 14:16] — feat

**Files Modified:** `google_places.py`, `pipeline/research.py`, `run_pipeline.py`, `.env.example`, `.gitignore`

### What Changed
- Added `reviews` field to `get_place_details()` Places API request in `google_places.py`
- Added `get_place_reviews()` method to `GooglePlacesClient` — fetches up to 5 five-star reviews for a given Place ID
- Updated `build_user_prompt()` in `pipeline/research.py` to accept an optional `reviews` parameter and inject real review text into the Claude prompt before the JSON instruction block
- Updated `run_research_agent()` to accept and pass through `reviews` to `build_user_prompt()`
- Added Step 1b to `run_pipeline.py` — fetches five-star reviews from Google Places between the Sheets fetch and the Claude agent call
- Added `GooglePlacesClient` import to `run_pipeline.py`
- Added `ANTHROPIC_API_KEY` placeholder to `.env.example`
- Added `briefs/` to `.gitignore`

### Recommendation
Run the pipeline against a known high-review business (e.g. Glow Aesthetics, Place ID `ChIJhVpybR5fwokRSgKTBw5tuUU`) to confirm Step 1b logs the correct review count and that the resulting `brand_brief` JSON contains `review_themes` and `brand_voice` grounded in actual customer language rather than category-level assumptions. Compare a before/after brief to validate quality improvement.

### Anything To Watch
- Google Places API returns a **maximum of 5 reviews** sorted by relevance — there is no way to request more via the Basic/Advanced Places API. If a business has many reviews but none surface as five-star in the top 5, `reviews` will be empty and Claude falls back to category-level assumptions (logged as a warning).
- The `reviews` field in Place Details is billed under the **Contact** data SKU — confirm billing is enabled for this field in the Google Cloud Console.
- `run_pipeline.py` now instantiates `GooglePlacesClient` with `max_pages_per_category=1` for the review fetch — this is intentional (only one details call needed) and does not affect the prospecting pipeline in `main.py`.
