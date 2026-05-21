# Changelog

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
