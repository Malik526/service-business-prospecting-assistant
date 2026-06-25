# Service Business Prospecting Assistant

## Project Overview

Service Business Prospecting Assistant is a local Python CLI tool for discovering, deduplicating, scoring, and storing local service-based business prospects for outreach planning.

It uses:

- Google Places API for business discovery and enrichment
- Google Sheets API for storing and managing prospect records
- Google Geocoding API to convert ZIP codes into search coordinates
- A Google service account so the script can read and write to Sheets as a backend automation tool

This MVP researches and organizes prospects only. It does not send outreach, generate emails, run scheduled jobs, or manage follow-up automation.

---

## What It Collects

| Column | Description |
|---|---|
| Place ID | Google's unique identifier for the business location |
| Business Name | Name from Google Places |
| Category | Target category (e.g., dentists, HVAC, caterers) |
| Address | Formatted address from Google Places |
| Phone | Business phone number |
| Website | Business website URL, if listed |
| Google Maps URL | Direct link to the Google Maps listing |
| Rating | Google star rating (1–5) |
| Review Count | Total number of Google reviews |
| Distance From Search ZIP (mi) | Distance from the search origin ZIP to the business, in miles |
| Source | Always "Google Places API" |
| Lead Score | Heuristic priority score (1–10) — see Lead Score section below |
| Why Good Fit | Short explanation of the scoring rationale |
| Status | Current outreach status — dropdown controlled (see Status section below) |
| Last Contact Date | Manual date field for the most recent outreach attempt |
| Last Outcome | Manual outcome field with dropdown suggestions |
| Notes | Free-form notes field |
| Search ZIP Code | ZIP code used for the prospecting run |
| Search Radius (mi) | Search radius used for the prospecting run |
| Instagram URL | Instagram URL extracted from the business website, when found |
| Email | Email address extracted from the business website, when found |
| Street | Street address parsed from the full Google Places address |
| City | City parsed from the full Google Places address |
| State | Two-letter state parsed from the full Google Places address |
| ZIP | Five-digit ZIP code parsed from the full Google Places address |

---

## Lead Score

**The lead score is a heuristic, feature-engineered signal. It is NOT statistically validated, NOT market-tested, and NOT an objective measure of revenue potential or conversion likelihood.**

It is a lightweight prioritization aid designed to surface the most promising prospects for manual review — not a predictive model.

### How it is calculated

| Signal | Points |
|---|---|
| Service-based business (baseline) | +2 |
| High-ticket category | +2 |
| Has a phone number | +1 |
| Has a website | +1 |
| No website (outreach opportunity) | +2 |
| Strong CRM/lead-capture fit | +2 |
| 25+ Google reviews | +1 |

Score range: **1–10** (clamped).

### Why no website scores higher than having one

A missing website is an actionable outreach hook. Businesses without websites are strong candidates for website builds, SEO, and lead capture services — which is why they receive +2 instead of +1. This is an intentional outreach-opportunity signal, not a measure of business quality.

### Stronger raw analytical signals

These fields often tell a more direct story than the composite score and should be considered alongside it:

- **Rating**: Low ratings may signal service gaps; high ratings signal stability.
- **Review Count**: A proxy for business volume and local market presence.
- **Website**: Direct indicator of digital maturity.
- **Distance**: Useful for geographic campaign clusters and local outreach logistics.

Use the lead score as a starting filter. Apply your own judgment using the raw data before sending outreach.

---

## Weighted Reputation Score

Weighted Reputation Score is a separate analytical metric. It does **not** replace Lead Score.

- **Lead Score**: lightweight operational fit score based on outreach opportunity signals such as category, phone presence, website presence, CRM fit, and review threshold.
- **Weighted Reputation Score**: market-validation-oriented reputation confidence metric based only on Google rating and review count.

Formula:

```text
rating * log10(review_count + 1)
```

### Purpose

Weighted Reputation Score combines:

- **Review quality**: the business's Google rating
- **Review confidence**: how much review volume supports that rating

This helps identify businesses with both strong ratings and enough review history to suggest real local market presence.

### Why logarithmic scaling is used

Raw multiplication would overweight businesses with massive review counts. Logarithmic scaling compresses review volume and reflects diminishing informational returns.

For example:

- Going from 0 to 20 reviews is highly informative.
- Going from 1000 to 1020 reviews is much less informative.

The `+1` in `log10(review_count + 1)` prevents `log10(0)` when a business has zero reviews.

### Important clarification

Weighted Reputation Score is heuristic feature engineering. It is not formal statistical inference, not a Google-provided metric, and not a definitive quality ranking. It is intended as an operational analysis tool for prioritizing review.

---

## Business Category Assumptions

Each category in `categories.py` carries two heuristic flags:

### `high_ticket`

True when the category is heuristically associated with higher average transaction values. Higher transaction value means greater ROI on marketing, CRM, or lead capture tools — making these businesses stronger outreach candidates.

**These are generalized industry assumptions, not verified data for any specific business.**

Examples:
- **Dentists**: Treatment plans and cosmetic work are often $500–$5,000+ per case.
- **Med spas**: Cosmetic procedures (Botox, fillers, laser) are often $300–$2,000+ per visit.
- **Caterers**: Event bookings are typically $1,000–$20,000+ per engagement.
- **HVAC/Plumbers**: Emergency and installation jobs commonly run $500–$10,000+.
- **Contractors**: Renovation and construction projects are often $5,000–$100,000+.
- **Fitness studios / Gyms**: Membership-based; lower per-transaction value → `high_ticket: False`.
- **Salons / Barbers**: Per-visit revenue is lower ($30–$150) → `high_ticket: False`.

### `crm_fit`

True when the category clearly benefits from appointment booking, automated follow-up, lead capture, or customer retention tools. The operational need is especially pronounced and the value of a CRM or automation tool is easiest to demonstrate.

Examples:
- **Plumbers / HVAC**: Urgent lead capture is critical — a missed call is a missed job.
- **Dentists**: Appointment reminders, recall campaigns, and follow-up sequences drive retention.
- **Caterers**: Inquiry tracking and quote follow-up are core operational needs.
- **Med spas**: Rebooking reminders and retention sequences directly affect revenue.

Currently, all target categories have `crm_fit: True` because this tool is specifically designed for outreach to businesses that can benefit from digital growth and CRM-adjacent services.

---

## Status And Outcome Columns

The Status and Last Outcome columns are Google Sheets dropdowns with suggested values. They are intentionally non-strict, so manual additions do not break the sheet.

New records are automatically set to **New** when written by the script.

| Status | Meaning |
|---|---|
| New | Just discovered, not yet manually reviewed |
| Reviewed | Manually reviewed; decision pending |
| Good Fit | Confirmed strong outreach candidate |
| Not Fit | Reviewed and ruled out |
| Do Not Contact | Should not be contacted |
| Not Interested | Prospect declined or should be deprioritized |

| Last Outcome | Meaning |
|---|---|
| Not Called Yet | No call has been attempted |
| Answered - Interested | Prospect answered and showed interest |
| Answered - Not Interested | Prospect answered and declined |
| Answered - Hung Up | Prospect answered and ended the call |
| Answered - Scheduled Demo | Demo or meeting was scheduled |
| Voicemail Left | Call reached voicemail and a message was left |
| Wrong Number | Listed number does not reach the business |
| Business Closed | Business appears closed |
| Do Not Call List | Prospect should not be called |

The dropdowns are applied automatically by the script on every run using the Google Sheets `setDataValidation` API. Re-applying them does not reset existing values.

---

## Distance From Search ZIP

The **Distance From Search ZIP (mi)** column shows the straight-line distance between the search origin ZIP code and each business, calculated using the Haversine formula.

The Haversine formula computes the shortest great-circle distance between two points on Earth's surface, accounting for curvature. It is accurate to within ~0.5% for distances under 100 miles — sufficient for local prospecting radii.

Distance is calculated from the business's geographic coordinates (from the Google Places Text Search response geometry) back to the center of the input ZIP code (from the Geocoding API).

### Why it matters

- **Geographic targeting**: Identify clusters of prospects within a specific mile range for logistically grouped outreach.
- **Radius validation**: Confirm that results actually fall within expected distance bands.
- **Local logistics**: Closer businesses may be practical for in-person outreach or site visits.
- **Sorting and filtering**: Sort by distance in the sheet to prioritize the nearest prospects first.

---

## Validation Recommendations

Before beginning outreach, manually validate a sample of your highest-scored prospects:

- **Websites**: Verify the listed site is active, professional, and belongs to the business.
- **Ratings**: Check if a low rating is an outlier or a pattern.
- **Categories**: Confirm the business type matches what you expected — Places API search results can include tangential matches.
- **Top-scored businesses**: Spot-check 5–10 of your highest-scored prospects to calibrate whether the scoring heuristics are surfacing the right types of businesses for your specific market.
- **Distance**: Confirm any outlier distances are real and not geocoding artifacts.

The lead score is a filter, not a guarantee. Your own judgment on the raw data signals should drive final outreach decisions.

---

## Local Setup

Python 3.11+ is recommended. Current Google API libraries continue to evolve and will eventually phase out support for older Python versions.

```bash
cd growth_agency/internal-tools/service-business-prospecting-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

---

## Authentication Architecture

This project uses two different Google authentication methods:

- **Google Places API key**: used for Places and Geocoding requests. The key is stored in `.env` as `GOOGLE_PLACES_API_KEY`.
- **Google Sheets service account**: used to read existing prospects and append new rows. The service account JSON file is stored locally in `credentials/`.

The script acts as a backend automation tool. No OAuth user login flow is required because it does not act as a signed-in human user. Instead, the Google Sheet must be shared directly with the service account email as an Editor.

---

## Required Google APIs

Enable only the APIs this project uses:

- Places API (New)
- Google Sheets API
- Geocoding API

Only enabling required APIs reduces accidental billing exposure and limits what a misconfigured or leaked credential could access.

---

## Environment Variables

Copy `.env.example` to `.env`, then fill in the values:

```bash
GOOGLE_PLACES_API_KEY=your_google_api_key
GOOGLE_SHEET_ID=your_google_sheet_id
GOOGLE_SERVICE_ACCOUNT_FILE=./credentials/service-account.json
GOOGLE_SHEET_NAME=PROSPECTS
MAX_PAGES_PER_CATEGORY=3
```

| Variable | Description |
|---|---|
| `GOOGLE_PLACES_API_KEY` | API key used for Google Places and Geocoding requests |
| `GOOGLE_SHEET_ID` | ID of the Google Sheet where prospects will be stored |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Local path to the service account JSON file |
| `GOOGLE_SHEET_NAME` | Tab name inside the Google Sheet. Defaults to `PROSPECTS` |
| `MAX_PAGES_PER_CATEGORY` | Number of Google Places result pages per category (each page ~20 results) |

---

## Google API Setup

1. Create or select a Google Cloud project.
2. Enable these APIs:
   - Places API (New)
   - Google Sheets API
   - Geocoding API
3. Create an API key for Places and Geocoding.
4. Add the key to `GOOGLE_PLACES_API_KEY`.
5. Restrict the API key to only the APIs used by this project.

---

## Credentials Setup

1. In Google Cloud, create a service account for this tool.
2. Generate a JSON key for the service account.
3. Save the file locally as:

```
credentials/service-account.json
```

4. Confirm `.env` points to that file:

```bash
GOOGLE_SERVICE_ACCOUNT_FILE=./credentials/service-account.json
```

Credential files should never be committed to GitHub. The project `.gitignore` excludes `.env` and `credentials/`.

---

## Google Sheets Setup

1. Create a Google Sheet.
2. Add a tab named `PROSPECTS`, or set a different name via `GOOGLE_SHEET_NAME`.
3. Copy the Sheet ID from the URL:

```
https://docs.google.com/spreadsheets/d/<GOOGLE_SHEET_ID>/edit
```

4. Add the ID to `.env` as `GOOGLE_SHEET_ID`.
5. Share the Google Sheet with the service account email address as an Editor.

The tool will create and maintain the header row automatically. Status and Last Outcome dropdown validation is applied on every run.

### Dynamic PROSPECTS Schema

On every run, the tool reads row 1 of the `PROSPECTS` tab and builds a live column map. Scraper appends, Place ID duplicate checks, dropdown validations, and email backfills all use that map instead of fixed column positions.

The latest detected schema is cached at:

```text
config/PROSPECTS_SCHEMA.json
```

If columns are rearranged, added, or removed, the next run logs the schema change and updates the cache. Missing expected columns are handled gracefully: values for deleted columns are skipped, and dropdowns are only applied when their target columns exist.

---

## Usage

```bash
python main.py --zip 11385 --radius 20
```

Adjust the radius:

```bash
python main.py --zip 11385 --radius 10
python main.py --zip 11385 --radius 30
```

After each run, the CLI prints:

- Run parameters (ZIP, radius)
- Businesses found, duplicates skipped, new records added
- Website coverage (with / without website)
- Lead score average and range
- 5 closest businesses by distance
- 5 most-reviewed businesses
- 5 highest businesses by Weighted Reputation Score
- Top 10 highest-scored new prospects

---

## Pagination

`MAX_PAGES_PER_CATEGORY` controls Google Places API pagination per category search, not Google Sheets pagination.

Google Places returns results in batches of up to 20 businesses per page. Increasing `MAX_PAGES_PER_CATEGORY` finds more prospects but increases API usage, runtime, and billing. A 2-second delay between pages is required because the Google Places `next_page_token` has a server-side propagation delay before it becomes usable.

---

## Deduplication

A prospect is skipped if it matches an existing record on any of these signals (checked in priority order):

1. **Google Place ID** (exact match) — most authoritative signal.
2. **Phone number** (digits-only exact match) — handles formatting differences.
3. **Website** (normalized URL exact match) — strips protocol, www, and trailing slashes.
4. **Business name + address** (fuzzy match, both must exceed threshold) — fallback when other signals are absent.

Deduplication runs against both existing Google Sheet records and all prospects accepted earlier in the same run, preventing within-run duplicates when a business appears across multiple category searches.

---

## Changing Categories

Edit `categories.py`.

Use `--categories` to limit a run to specific business types:

```bash
python3 main.py --zip 11375 --radius 5 --categories electrician,hvac,plumber
```

The filter accepts comma-separated category names, Google Places query names,
singular forms, and case/spacing variants. If omitted, the scraper searches all
categories in `TARGET_CATEGORIES`.

Each category has:

| Key | Type | Description |
|---|---|---|
| `name` | str | Stored in the Google Sheet. Human-readable label. |
| `query` | str | Sent to Google Places Text Search. |
| `high_ticket` | bool | Heuristic flag — higher average transaction value. |
| `crm_fit` | bool | Heuristic flag — clear benefit from CRM/automation tools. |

---

## Project Structure

```
main.py           Orchestration: connects all modules, runs the pipeline
google_places.py  Google Places and Geocoding API client
google_sheets.py  Google Sheets read/write and dropdown validation
dedupe.py         Duplicate detection across all signal types
scoring.py        Lead scoring, weighted reputation scoring, and fit explanation
categories.py     Target category definitions with heuristic flags
config.py         Environment variable loading and validation
utils.py          Shared helpers (distance, normalization, formatting)
```

---

## Common Debugging Issues

### 403: The caller does not have permission

The Google Sheet was not shared with the service account.

Fix:
1. Open `credentials/service-account.json`.
2. Find the `client_email` value.
3. Open the Google Sheet.
4. Share the Sheet with that email address as an Editor.

### REQUEST_DENIED from the Geocoding or Places API

The API is not enabled on your Google Cloud project, or the API key restrictions exclude it.

Fix:
1. Go to [Google Cloud Console → APIs & Services → Library](https://console.cloud.google.com/apis/library).
2. Enable **Geocoding API** and **Places API (New)**.
3. Check the API key's restriction list includes both APIs.

### Missing credential file

Confirm the JSON key is saved at the path specified by `GOOGLE_SERVICE_ACCOUNT_FILE` in `.env`. Default path is `credentials/service-account.json`.

---

## Security Notes

- `.env` is gitignored and should stay local.
- `credentials/` is gitignored and should stay local.
- `service-account.json` should never be public or committed to GitHub.
- API keys should be restricted to only the required APIs.
- If a credential is accidentally exposed, revoke or rotate it immediately in Google Cloud.

---

## Notes

- This tool uses official Google APIs. It does not scrape Google Maps.
- Radius is entered in miles and converted to meters internally for the Google Places API.
- `MAX_PAGES_PER_CATEGORY=3` fetches up to 60 results per category (3 pages × 20 results).
- The lead score, weighted reputation score, `high_ticket`, and `crm_fit` flags are heuristic assumptions — not statistically validated signals. Treat them as starting filters, not ground truth.
