# Service Business Prospecting Assistant

A local Python CLI tool for finding, deduping, scoring, and storing local service-based business prospects for outreach planning.

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

## Setup

```bash
cd GrowthAgency/internal-tools/service-business-prospecting-assistant
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

```bash
GOOGLE_PLACES_API_KEY=your_google_api_key
GOOGLE_SHEET_ID=your_google_sheet_id
GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json
GOOGLE_SHEET_NAME=Prospects
MAX_PAGES_PER_CATEGORY=3
```

## Google API Setup

1. Create or select a Google Cloud project.
2. Enable these APIs:
   - Places API
   - Geocoding API
   - Google Sheets API
3. Create an API key for Places and Geocoding.
4. Add the key to `GOOGLE_PLACES_API_KEY`.

## Google Sheets Setup

1. Create a Google Sheet.
2. Add a tab named `Prospects`, or change `GOOGLE_SHEET_NAME`.
3. Copy the Sheet ID from the URL:

```text
https://docs.google.com/spreadsheets/d/<GOOGLE_SHEET_ID>/edit
```

4. Create a Google Cloud service account.
5. Download its JSON key file.
6. Save it as `service-account.json` in this project, or update `GOOGLE_SERVICE_ACCOUNT_FILE`.
7. Share the Google Sheet with the service account email address.

The tool will create/update the header row automatically.

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
- `MAX_PAGES_PER_CATEGORY=3` fetches up to three Google Places result pages per category.
