# Service Prospecting Frontend

Next.js interface for the Service Business Prospecting SaaS MVP.

## Local Setup

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000/prospecting`.

## Environment

Set `NEXT_PUBLIC_LAMBDA_URL` to the FastAPI or Lambda Function URL.

```bash
NEXT_PUBLIC_LAMBDA_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
NEXT_PUBLIC_STRIPE_PRICE_STARTER_MONTHLY=price_starter_monthly
NEXT_PUBLIC_STRIPE_PRICE_PRO_MONTHLY=price_pro_monthly
NEXT_PUBLIC_STRIPE_PRICE_BUSINESS_MONTHLY=price_business_monthly
```

## Phase 4 Routes

- `/auth` handles Supabase sign-in.
- `/prospecting` requires an authenticated user and shows usage limits.
- `/upgrade` starts Stripe Checkout for paid plans.
- `/feedback` submits product feedback to the backend.
- `/admin/dashboard` loads high-level metrics with the backend `ADMIN_KEY`.

## Scripts

- `npm run dev` starts local development.
- `npm run build` creates the production build.
- `npm run lint` checks Next.js lint rules.
- `npm run typecheck` checks TypeScript types.
