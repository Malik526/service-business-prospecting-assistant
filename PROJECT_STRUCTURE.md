# Project Structure

## Current Decision

The project is intentionally nested under one root directory:

```text
service-business-prospecting-assistant/
├── shared/
│   └── prospecting/
├── service-prospecting-backend/
├── service-prospecting-frontend/
├── pipeline/
├── tests/
├── README.md
├── CHANGELOG.md
└── PROJECT_STRUCTURE.md
```

This follows the shared-code structure from the cleanup brief while preserving
the current backend and frontend directory names to avoid breaking existing
local commands, deployment notes, and open workspace paths.

## Directory Ownership

### Root CLI

The root Python scripts are the original Google Sheets and research workflow.
They discover prospects, score them, enrich records, write to Google Sheets,
and generate research briefs.

Key files:

- `main.py`: CLI prospect discovery and Google Sheets writer.
- `run_scraper_parallel.py`: batch launcher for multiple scrape configs.
- `run_pipeline.py`: research brief pipeline for an existing prospect.
- `research_by_place_id.py`: standalone research brief flow by Google Place ID.
- `config.py`: CLI-only environment loading for Google Sheets and Anthropic.
- `pipeline/`: website/email/social extraction and brief writing helpers.

### Shared Prospecting Code

`shared/prospecting/` is the source of truth for reusable prospect logic.

Key files:

- `categories.py`: target service categories and category filtering.
- `google_places.py`: Google Places and Geocoding API wrapper.
- `dedupe.py`: duplicate detection helpers.
- `scoring.py`: lead scoring, reputation scoring, and fit explanation.
- `utils.py`: normalization, conversion, and distance helpers.
- `search.py`: API-ready search preparation and address component extraction.

### Backend

`service-prospecting-backend/` is the FastAPI and Lambda API layer. It wraps the
shared prospecting code with HTTP endpoints, Supabase usage enforcement, Stripe
billing helpers, and DynamoDB storage.

The backend keeps its own `prospecting/config.py` because backend environment
requirements are different from CLI requirements. Backend config does not
require Google Sheets or Anthropic values.

### Frontend

`service-prospecting-frontend/` is the Next.js app. It talks to the backend via
`NEXT_PUBLIC_LAMBDA_URL` and uses Supabase browser auth through public anon-key
settings.

## Duplication Audit

Before cleanup, the root CLI and backend both had copies of:

- `categories.py`
- `google_places.py`
- `dedupe.py`
- `scoring.py`
- `utils.py`

Those copies were functionally the same except for import style and a few helper
docstrings. They now import from `shared/prospecting/` through compatibility
wrappers.

The backend-only `prospecting/search.py` was also moved into
`shared/prospecting/search.py` and re-exported from the backend wrapper because
it prepares shared search results for API responses.

`config.py` was not merged because the CLI and backend intentionally have
different environment contracts.

## Environment File Sources

Each component owns exactly one tracked example template:

- Root CLI: `.env.example`
- Backend: `service-prospecting-backend/.env.example`
- Frontend: `service-prospecting-frontend/.env.local.example`

Real local env files remain ignored:

- `.env`
- `service-prospecting-backend/.env`
- `service-prospecting-frontend/.env`
- `service-prospecting-frontend/.env.local`

Never put service role keys, API keys, or credential JSON in tracked example
files. Use placeholders only.

## Compatibility Imports

Existing CLI imports continue to work:

```python
from google_places import GooglePlacesClient
from scoring import score_prospect
```

Existing backend imports continue to work:

```python
from prospecting.google_places import GooglePlacesClient
from prospecting.search import prepare_new_prospects
```

The compatibility wrappers keep old code stable while making shared modules the
only place where scraper and scoring logic should change.
