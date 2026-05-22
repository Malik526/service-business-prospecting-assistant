# Changelog

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
