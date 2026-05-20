# Service Business Prospecting Assistant

## Project Overview

Service Business Prospecting Assistant is a local Python CLI tool for discovering, deduping, scoring, and storing local service-based business prospects for outreach planning.

It uses:

- Google Places API for business discovery and enrichment
- Google Sheets API for storing and managing prospect records
- Google Geocoding API to convert ZIP codes into search coordinates
- A Google service account so the script can read and write to Sheets as a backend automation tool

This MVP researches and organizes prospects only. It does not send outreach, generate emails, run scheduled jobs, or manage follow-up automation.

## What It Collects

- Place ID
- Business Name
- Category
- Address
- Phone
- Website
- Google Maps URL
- Rating
- Review Count
- Source
- Lead Score
- Why Good Fit
- Status
- Date Added
- Notes

## Local Setup

Python 3.11+ is recommended. Current Google API libraries continue to evolve and will eventually phase out support for older Python versions.

```bash
cd GrowthAgency/internal-tools/service-business-prospecting-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Authentication Architecture

This project uses two different Google authentication methods:

- Google Places API key authentication: used for Places and Geocoding requests. The API key is stored in `.env` as `GOOGLE_PLACES_API_KEY`.
- Google Sheets service account authentication: used to read existing prospects and append new rows to a Google Sheet. The service account JSON file is stored locally in `credentials/`.

The script acts like a backend automation tool. No OAuth user login flow is required because it does not need to act as a signed-in human user. Instead, the Google Sheet must be shared directly with the service account email.

## Required Google APIs

Enable only the APIs this project uses:

- Places API (New)
- Google Sheets API
- Geocoding API

Only enabling required APIs reduces accidental billing exposure and limits what leaked or misconfigured credentials could access.

## Environment Variables

Copy `.env.example` to `.env`, then fill in the values:

```bash
GOOGLE_PLACES_API_KEY=your_google_api_key
GOOGLE_SHEET_ID=your_google_sheet_id
GOOGLE_SERVICE_ACCOUNT_FILE=./credentials/service-account.json
GOOGLE_SHEET_NAME=Prospects
MAX_PAGES_PER_CATEGORY=3
```

- `GOOGLE_PLACES_API_KEY`: API key used for Google Places and Geocoding requests.
- `GOOGLE_SHEET_ID`: ID of the Google Sheet where prospects will be stored.
- `GOOGLE_SERVICE_ACCOUNT_FILE`: local path to the service account JSON file.
- `GOOGLE_SHEET_NAME`: tab name inside the Google Sheet. Defaults to `Prospects`.
- `MAX_PAGES_PER_CATEGORY`: number of Google Places result pages to request per category.

## Google API Setup

1. Create or select a Google Cloud project.
2. Enable these APIs:
   - Places API (New)
   - Google Sheets API
   - Geocoding API
3. Create an API key for Places and Geocoding.
4. Add the key to `GOOGLE_PLACES_API_KEY`.
5. Restrict the API key to only the APIs used by this project.

## Credentials Setup

1. In Google Cloud, create a service account for this tool.
2. Generate a JSON key for the service account.
3. Save the file locally as:

```text
credentials/service-account.json
```

4. Confirm `.env` points to that file:

```bash
GOOGLE_SERVICE_ACCOUNT_FILE=./credentials/service-account.json
```

Credential files should never be committed to GitHub. The project `.gitignore` excludes `.env` and `credentials/`.

## Google Sheets Setup

1. Create a Google Sheet.
2. Add a tab named `Prospects`, or change `GOOGLE_SHEET_NAME`.
3. Copy the Sheet ID from the URL:

```text
https://docs.google.com/spreadsheets/d/<GOOGLE_SHEET_ID>/edit
```

4. Add the ID to `.env` as `GOOGLE_SHEET_ID`.
5. Share the Google Sheet with the service account email address as an Editor.

The tool will create/update the header row automatically.

## Common Debugging Issues

### 403: The caller does not have permission

This usually means the Google Sheet was not shared with the service account.

Fix:

1. Open `credentials/service-account.json`.
2. Find the `client_email` value.
3. Open the Google Sheet.
4. Share the Sheet with that email address.
5. Give it Editor access.

Without this step, the script can authenticate successfully but still cannot read or write to the Sheet.

### Missing credential file

If you see an error that `GOOGLE_SERVICE_ACCOUNT_FILE` does not exist, confirm the JSON key is saved at:

```text
credentials/service-account.json
```

Or update `GOOGLE_SERVICE_ACCOUNT_FILE` in `.env` to match the actual local path.

### Places or Geocoding API errors

Check that:

- `GOOGLE_PLACES_API_KEY` is set in `.env`
- Places API (New) is enabled
- Geocoding API is enabled
- API key restrictions allow these APIs
- billing is enabled for the Google Cloud project

## Security Notes

- `.env` is gitignored and should stay local.
- `credentials/` is gitignored and should stay local.
- `service-account.json` should never be public or committed to GitHub.
- API keys should be restricted to only the required APIs.
- If a credential is accidentally exposed, revoke or rotate it immediately in Google Cloud.

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

- businesses found
- duplicates skipped
- new businesses added
- top 10 highest-scored new prospects

## Pagination

`MAX_PAGES_PER_CATEGORY` controls Google Places API pagination, not Google Sheets pages.

Google Places returns search results in batches. Each page is typically around 20 businesses. Increasing `MAX_PAGES_PER_CATEGORY` can find more prospects, but it also increases API usage, runtime, and potential billing.

## Deduplication

Google Place ID is the primary dedupe key.

The tool also checks:

- phone number
- website
- business name plus address similarity

It checks both prospects found during the current run and existing rows already stored in Google Sheets.

## Lead Scoring

Scoring is in `scoring.py`.

Current rules:

- service-based business: `+2`
- high-ticket category: `+2`
- has phone number: `+1`
- has website: `+1`
- missing website: `+2`
- strong fit for lead capture, CRM, or automation: `+2`
- at least 25 reviews: `+1`

Scores are capped from `1` to `10`.

## Changing Categories

Edit `categories.py`.

Each category has:

- `name`: stored in the Sheet
- `query`: sent to Google Places
- `high_ticket`: affects score and fit explanation
- `crm_fit`: affects score and fit explanation

## Notes

- This tool uses official Google APIs.
- It does not scrape Google Maps.
- Radius is entered in miles and converted to meters for Google Places.
- `MAX_PAGES_PER_CATEGORY=1` fetches up to three Google Places result pages per category.
