# Service Prospecting Backend

FastAPI and AWS Lambda backend for the Service Business Prospecting SaaS MVP.

## What This Directory Does

This directory exposes the shared prospecting engine as REST endpoints. It owns
API request/response models, Supabase usage enforcement, Stripe billing flows,
and DynamoDB persistence.

## Files & Purpose

- `main.py`: FastAPI app and HTTP endpoints.
- `lambda_handler.py`: Mangum adapter for AWS Lambda.
- `dynamodb_service.py`: prospect, search history, usage, and feedback storage.
- `supabase_service.py`: user profile lookup, usage caps, and subscription sync.
- `stripe_service.py`: Checkout, Billing Portal, and webhook helpers.
- `prospecting/config.py`: backend-only environment loader.
- `prospecting/*.py`: compatibility wrappers around `../shared/prospecting/`.
- `tests/`: backend unit tests.

Shared scraper logic lives in `../shared/prospecting/`; edit that package when
changing category, Google Places, dedupe, scoring, or search-preparation logic.

## Local Setup

1. Create a local `.env` from `.env.example`.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the API:

```bash
uvicorn main:app --reload
```

4. Open `http://localhost:8000/docs`.

## Supabase API Setup

Authenticated searches send the logged-in Supabase user ID to the backend so
the API can enforce usage limits. The backend `.env` must use the Supabase
service-role key, not the frontend anon key, for `SUPABASE_SERVICE_ROLE_KEY`.

The service-role key is a long JWT-style value that starts with `eyJ`. If a
logged-in search returns `Invalid API key` before Google Places is called,
replace `SUPABASE_SERVICE_ROLE_KEY`, restart the backend, and retry.

## Google API Setup

Prospect search requires the local `GOOGLE_PLACES_API_KEY` to belong to a
Google Cloud project with these APIs enabled:

- Geocoding API, used to convert ZIP codes into latitude and longitude.
- Places API, used for Text Search and Place Details.

If `/api/prospects` returns `Google API error: REQUEST_DENIED` with a message
that the API is not activated, enable the missing API in Google Cloud Console,
wait about 60 seconds, restart the backend, and try the search again.

## Endpoints

- `POST /api/prospects` searches one ZIP/radius/category request, stores new prospects in DynamoDB, and returns JSON results.
- `GET /api/prospects/{user_id}` returns stored prospects for one user.
- `DELETE /api/prospects/{user_id}/{place_id}` deletes one stored prospect.
- `POST /api/create-checkout-session` starts Stripe Checkout.
- `POST /api/billing-portal` opens Stripe Billing Portal.
- `POST /webhook/stripe` syncs Stripe subscription updates.
- `POST /api/feedback` stores product feedback.
- `GET /api/admin/stats` returns basic metrics when `ADMIN_KEY` matches.
- `GET /health` returns service health.

## DynamoDB Shape

The MVP expects a `prospects` table with:

- Partition key: `user_id` (String)
- Sort key: `place_id` (String)

The table name can be overridden with `DYNAMODB_TABLE_PROSPECTS`.

Phase 4 adds optional DynamoDB tables:

- `usage_logs`: `user_id` partition key, `timestamp` sort key.
- `search_history`: `user_id` partition key, `search_id` sort key.
- `feedback`: `feedback_id` partition key.

Supabase and Stripe values are configured through `.env.example`. Keep real
secrets in `.env` only; tracked example files must use placeholders.
