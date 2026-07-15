# Service Prospecting Backend

FastAPI and AWS Lambda backend for the Service Business Prospecting SaaS MVP.

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

Supabase and Stripe values are configured through `.env.example`.
