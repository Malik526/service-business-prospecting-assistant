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
```

## Scripts

- `npm run dev` starts local development.
- `npm run build` creates the production build.
- `npm run lint` checks Next.js lint rules.
- `npm run typecheck` checks TypeScript types.

