# Shared Prospecting Code

## What This Directory Does

`shared/` is the single source of truth for prospect discovery logic that is
used by both the local CLI and the FastAPI backend.

## Files & Purpose

- `prospecting/categories.py`: target service categories and category filtering.
- `prospecting/google_places.py`: Google Places and Geocoding API client.
- `prospecting/dedupe.py`: duplicate detection helpers.
- `prospecting/scoring.py`: lead score, reputation score, and fit explanation logic.
- `prospecting/utils.py`: shared normalization, distance, and type conversion helpers.
- `prospecting/search.py`: backend-oriented search preparation helpers.

## Dependency Boundary

This package does not own environment loading. The root CLI keeps its own
`config.py`; the backend keeps `service-prospecting-backend/prospecting/config.py`.
That separation prevents Google Sheets and Anthropic CLI settings from becoming
required backend settings.

## Import Pattern

Existing CLI imports such as `from google_places import GooglePlacesClient` still
work through compatibility wrappers. Backend imports such as
`from prospecting.categories import filter_target_categories` also still work
through compatibility wrappers.

