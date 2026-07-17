# Changelog

---

## [2026-07-16 21:26 EDT] — docs: clarify backend Supabase service key

**Files Modified:** `service-prospecting-backend/README.md`, `CHANGELOG.md`

### Summary
Documented that authenticated backend searches require the Supabase
service-role key, not the frontend anon key.

### Diagnostic Note
- Local `.env` has a `SUPABASE_SERVICE_ROLE_KEY` value, but its masked shape
  does not look like a Supabase service-role JWT.
- Direct search with a non-guest `user_id` reached the backend but returned
  `Invalid API key` during the Supabase usage check.

### Manual Action Required
- Replace backend `SUPABASE_SERVICE_ROLE_KEY` with the real Supabase
  service-role key, restart the backend, and retry authenticated search.

---

## [2026-07-16 21:23 EDT] — fix: declare backend OpenSSL dependency

**Files Modified:** `service-prospecting-backend/requirements.txt`,
`service-prospecting-backend/README.md`, `CHANGELOG.md`

### Summary
Declared a modern `pyOpenSSL` dependency for the backend after local diagnosis
showed the FastAPI worker crashing during `boto3` import before the API could
serve search requests.

### Behavior
- Prevents the backend from falling back to the incompatible system
  `pyOpenSSL 21.0.0` package when newer user-site `cryptography` packages are
  installed.
- Allows the backend process to reach `/health` and accept prospect search
  requests once dependencies are installed from `requirements.txt`.
- Keeps frontend API configuration unchanged because
  `NEXT_PUBLIC_LAMBDA_URL` already points to `http://localhost:8000`.
- Documents that both Google Geocoding API and Places API must be enabled for
  the configured Google Cloud project.

### Verification
- `cd service-prospecting-backend && python3 -m pip install -r requirements.txt`
- `cd service-prospecting-backend && python3 -m unittest discover -s tests`
- `cd service-prospecting-backend && uvicorn main:app --reload`
- `GET http://127.0.0.1:8000/health` returned HTTP 200.
- `POST http://127.0.0.1:8000/api/prospects` reached the backend and returned
  Google `REQUEST_DENIED` because the required Google API is not activated for
  the configured project.

### Manual Action Required
- Enable the missing Google Maps Platform API in Google Cloud Console for the
  project that owns the local `GOOGLE_PLACES_API_KEY`, wait about 60 seconds,
  restart the backend, and retry search.

---

## [2026-07-16 20:53 EDT] — fix: parse OAuth callback tokens explicitly

**Files Modified:** `service-prospecting-frontend/pages/auth/callback.tsx`,
`CHANGELOG.md`

### Summary
Updated the OAuth callback to manually consume Supabase access and refresh
tokens from the URL fragment before checking for an authenticated session.

### Behavior
- Parses `access_token` and `refresh_token` from the callback URL fragment.
- Calls `supabase.auth.setSession()` when both tokens are available.
- Removes the token-bearing fragment from browser history after the session is
  stored.
- Verifies the session with `getSession()` before routing to `/prospecting`.
- Routes failed or sessionless callbacks back to `/auth` without logging token
  values.
- Preserves the existing CSS-module-based callback UI and accessible status
  announcement.

### Verification
- `cd service-prospecting-frontend && npm run typecheck`
- `cd service-prospecting-frontend && npm run lint`
- `cd service-prospecting-frontend && npm run build`
- `cd service-prospecting-frontend && npm run dev`

### Manual Verification Still Required
- Complete Google OAuth in a browser and confirm the callback reports that the
  access token was found and the session was set and confirmed.
- Confirm `/prospecting` loads without returning to `/auth`.
- Confirm logout and a second Google sign-in both complete successfully.
- Run a prospect search and confirm authenticated backend requests do not
  return HTTP 401.

---

## [2026-07-16 20:42 EDT] — fix: detect OAuth sessions from callback URLs

**Files Modified:** `service-prospecting-frontend/lib/supabase.ts`,
`service-prospecting-frontend/pages/auth/callback.tsx`, `CHANGELOG.md`

### Summary
Made Supabase browser session parsing explicit and gave the callback route time
to detect OAuth sessions before redirecting users.

### Behavior
- Added explicit Supabase auth options for URL session detection, session
  persistence, and token refresh.
- Added an initial callback delay before polling `getSession()` so Supabase can
  parse OAuth URL fragments and write the browser session.
- Added callback console messages for session-created, no-session, and callback
  error outcomes.

### Verification
- `cd service-prospecting-frontend && npm run typecheck`
- `cd service-prospecting-frontend && npm run lint`
- `cd service-prospecting-frontend && npm run build`
- `cd service-prospecting-frontend && npm run dev`
- `GET http://localhost:3000/auth` returned HTTP 200.
- `GET http://localhost:3000/auth/callback` returned HTTP 200.

### Manual Verification Still Required
- Confirm Google OAuth redirect URI settings include the local auth callback
  route required for the active Supabase/Google flow.
- Complete Google OAuth in a browser and confirm the callback logs
  `Session created, redirecting to prospecting.`
- Confirm `/prospecting` loads without returning to `/auth`.

---

## [2026-07-16 20:18 EDT] — fix: add OAuth callback handler

**Files Added:** `service-prospecting-frontend/pages/auth/callback.tsx`

**Files Modified:** `service-prospecting-frontend/pages/auth.tsx`, `CHANGELOG.md`

### Summary
Added a dedicated Supabase OAuth callback page so Google sign-in returns to an
intermediate route that waits for the browser session before entering the
protected prospecting workspace.

### Behavior
- Updated the Supabase Auth UI to redirect OAuth results to `/auth/callback`.
- Added `onlyThirdPartyProviders={false}` explicitly on the Auth UI.
- Added `/auth/callback` to check for a Supabase session with a short retry
  window before redirecting.
- Sends authenticated users to `/prospecting` and failed/no-session callbacks
  back to `/auth`.
- Styled the callback page with the existing auth shell and panel classes.

### Verification
- `cd service-prospecting-frontend && npm run typecheck`
- `cd service-prospecting-frontend && npm run lint`
- `cd service-prospecting-frontend && npm run build`
- `cd service-prospecting-frontend && npm run dev`
- `GET http://localhost:3000/auth` returned HTTP 200.
- `GET http://localhost:3000/auth/callback` returned HTTP 200.

### Manual Verification Still Required
- Complete Google OAuth in a browser and confirm the flow briefly visits
  `/auth/callback`, then lands on `/prospecting` without looping.
- Confirm the browser has a Supabase `sb-...` localStorage session.
- Confirm Supabase auth logs show successful callback/user requests.
- Confirm logout still returns to `/auth`.

---

## [2026-07-16 19:51 EDT] — fix: wait for Supabase sign-in before redirecting

**Files Modified:** `service-prospecting-frontend/pages/auth.tsx`, `CHANGELOG.md`

### Summary
Fixed the Google sign-in redirect timing that could bounce users between
`/auth` and `/prospecting` before the Supabase browser session was available.

### Behavior
- Removed the immediate `redirectTo="/prospecting"` behavior from the Supabase
  Auth UI.
- Added a Supabase `onAuthStateChange` listener that redirects to
  `/prospecting` only after a `SIGNED_IN` event includes a confirmed session.
- Kept the existing already-signed-in session check for users who revisit
  `/auth`.
- Added cleanup for the auth subscription on unmount.

### Verification
- `cd service-prospecting-frontend && npm run typecheck`
- `cd service-prospecting-frontend && npm run lint`
- `cd service-prospecting-frontend && npm run build`
- `cd service-prospecting-frontend && npm run dev`
- `GET http://localhost:3000/auth` returned HTTP 200.

### Manual Verification Still Required
- Complete Google OAuth sign-in in a browser and confirm it lands on
  `/prospecting` without flickering back to `/auth`.
- Confirm Supabase auth logs show a successful callback/user request.
- Confirm the browser has the Supabase session token in localStorage.
- Confirm logout returns to `/auth`.

---

## [2026-07-16 17:50 EDT] — config: simplify frontend env templates

**Files Removed:** `service-prospecting-frontend/.env.example`

**Files Modified:** `.gitignore`, `README.md`, `PROJECT_STRUCTURE.md`,
`service-prospecting-frontend/README.md`, `CHANGELOG.md`

### Summary
Audited the backend and frontend environment file setup and simplified the
frontend to one committed local template plus one ignored local values file.

### Changed
- Removed the duplicate frontend `.env.example` template.
- Standardized frontend setup on `.env.local.example` for the committed template
  and `.env.local` for actual local values.
- Updated root and frontend README instructions to copy
  `.env.local.example` to `.env.local`.
- Updated `PROJECT_STRUCTURE.md` so the environment file map matches the
  simplified frontend convention.
- Added `service-prospecting-frontend/.env` to `.gitignore` to prevent accidental
  frontend env files from being committed.

### Local Setup
- Created ignored local `service-prospecting-backend/.env` from
  `service-prospecting-backend/.env.example`; real secret values still need to
  be filled in locally.

### Verification
- Confirmed `.gitignore` protects root `.env`, backend `.env`, frontend `.env`,
  and frontend `.env.local`.
- Confirmed backend `.env` exists locally and remains untracked.

---

## [2026-07-16 17:36 EDT] — docs: clarify structure and consolidate shared prospecting code

**Files Added:** `PROJECT_STRUCTURE.md`, `shared/`,
`service-prospecting-frontend/.env.local.example`

**Files Modified:** root CLI compatibility modules, backend prospecting
compatibility modules, backend/frontend README files, env examples,
`README.md`, `CHANGELOG.md`

### Summary
Reviewed the CLI, backend, and frontend hierarchy and clarified that the SaaS
backend/frontend are intentionally nested inside the original prospecting
assistant root. Consolidated duplicated prospecting logic behind a shared
package while preserving existing CLI and backend import paths.

### Added
- Added `shared/prospecting/` as the source of truth for categories, Google
  Places discovery, dedupe, scoring, utility helpers, and search preparation.
- Added `PROJECT_STRUCTURE.md` to document directory ownership, duplication
  audit results, environment-file ownership, and compatibility import paths.
- Added `shared/README.md` describing the shared package boundary.
- Added `service-prospecting-frontend/.env.local.example` for local browser-safe
  frontend setup.

### Changed
- Replaced duplicated root CLI scraper/scoring modules with documented wrappers
  that re-export from `shared.prospecting`.
- Replaced duplicated backend `prospecting` modules with documented wrappers
  that re-export from `shared.prospecting`.
- Kept backend `prospecting/config.py` separate because backend env values are
  intentionally different from root CLI env values.
- Updated root, backend, and frontend READMEs with ownership and setup notes.
- Restored tracked backend env example values to placeholders only.

### Security
- Removed a real-looking Supabase service role value from
  `service-prospecting-backend/.env.example`.
- Confirmed `.gitignore` excludes real local env files, credentials, venvs,
  frontend build output, and node modules.

### Verification
- `python3 -m compileall -q .`
- `python3 -m unittest discover -s tests -p 'test_*.py'`
- `cd service-prospecting-backend && .venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
- `cd service-prospecting-frontend && npm run typecheck`
- `cd service-prospecting-frontend && npm run lint`
- `cd service-prospecting-frontend && npm run build`

---

## [2026-07-15 04:30 EDT] — feat: add Phase 4 monetization foundation

**Files Added:** Supabase/Stripe backend services, frontend auth hook, auth,
upgrade, feedback, admin dashboard, and Stripe return pages.

**Files Modified:** `service-prospecting-backend/`,
`service-prospecting-frontend/`, `README.md`, `CHANGELOG.md`

### Summary
Added the Phase 4 post-launch monetization foundation: authenticated access,
usage cap enforcement, Stripe checkout and billing portal endpoints, webhook
subscription sync, usage logging, admin metrics, and feedback collection.

### Behavior
- Added Supabase service-role backend helpers for user profiles and usage caps.
- Added Stripe Checkout, Billing Portal, and subscription webhook helpers.
- Added DynamoDB usage logs, search history, and feedback helpers.
- Protected the prospecting page behind Supabase auth.
- Added usage banner showing current monthly search allowance.
- Added `/auth`, `/upgrade`, `/upgrade-success`, `/upgrade-canceled`,
  `/feedback`, and `/admin/dashboard` frontend routes.
- Added frontend API helpers for checkout, billing portal, feedback, and admin stats.
- Added Supabase and Stripe env templates for frontend and backend.

### Verification
- `cd service-prospecting-frontend && npm run typecheck`
- `cd service-prospecting-frontend && npm run lint`
- `cd service-prospecting-frontend && npm run build`
- `cd service-prospecting-frontend && npm audit --omit=dev` returned `found 0 vulnerabilities`
- `cd service-prospecting-backend && .venv/bin/python -m compileall -q .`
- `cd service-prospecting-backend && .venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
- `GET http://127.0.0.1:8000/health` returned `{"status":"ok","service":"prospecting-api"}`
- `GET /auth`, `/prospecting`, `/upgrade`, `/feedback`, and `/admin/dashboard`
  returned HTTP 200 from the local Next.js dev server.

### External Setup Still Required
- Create Supabase project and `users` table/RLS policy.
- Create DynamoDB `usage_logs`, `search_history`, and `feedback` tables.
- Create Stripe products, price IDs, and webhook endpoint.
- Add real Supabase and Stripe values to local and production environment variables.

---

## [2026-07-15 03:58 EDT] — feat: add SaaS prospecting frontend

**Files Added:** `service-prospecting-frontend/`

**Files Modified:** `README.md`, `.gitignore`, `CHANGELOG.md`

### Summary
Added the Phase 2 Next.js frontend for the Service Business Prospecting SaaS
MVP, ready for local use and Netlify deployment.

### Behavior
- Added a TypeScript Next.js app at `service-prospecting-frontend/`.
- Added a `/prospecting` workspace with ZIP, radius, and category controls.
- Added a typed Axios API client pointed at `NEXT_PUBLIC_LAMBDA_URL`.
- Added a responsive prospects table using the backend's `distance_miles` field.
- Added PapaParse CSV export for current search results.
- Added persistent local guest user IDs for MVP deduplication.
- Added modular form, result, and UI components with folder barrel exports.
- Added local `.env.local` for development and `.env.example` for deployment setup.
- Pinned patched frontend dependencies and added a PostCSS override after audit.

### Verification
- `npm run typecheck`
- `npm run lint`
- `npm run build`
- `npm audit --omit=dev` returned `found 0 vulnerabilities`
- `npm run dev -- --hostname 127.0.0.1 --port 3000`
- `GET http://127.0.0.1:3000/prospecting` returned HTTP 200

---

## [2026-07-15 03:41 EDT] — feat: scaffold SaaS prospecting backend

**Files Added:** `service-prospecting-backend/main.py`,
`service-prospecting-backend/lambda_handler.py`,
`service-prospecting-backend/dynamodb_service.py`,
`service-prospecting-backend/README.md`,
`service-prospecting-backend/.env.example`,
`service-prospecting-backend/requirements.txt`,
`service-prospecting-backend/prospecting/`,
`service-prospecting-backend/tests/test_search_preparation.py`

**Files Modified:** `README.md`, `.gitignore`, `CHANGELOG.md`

### Summary
Added the Phase 1 FastAPI and AWS Lambda backend scaffold for the Service
Business Prospecting SaaS MVP while keeping the existing Google Sheets CLI
unchanged.

### Behavior
- Added `POST /api/prospects` for one ZIP/radius/category search per request.
- Added `GET /api/prospects/{user_id}` and `DELETE /api/prospects/{user_id}/{place_id}`.
- Packaged Google Places discovery, category filtering, dedupe, scoring, and
  search preparation under `service-prospecting-backend/prospecting/`.
- Added DynamoDB helpers using `user_id` and `place_id` keys.
- Converted numeric values to `Decimal` before DynamoDB writes.
- Added a Mangum Lambda handler for AWS Lambda deployment.
- Added backend env and dependency templates.

### Verification
- `python3 -m compileall -q service-prospecting-backend`
- `cd service-prospecting-backend && .venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
- `cd service-prospecting-backend && .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000`
- `GET http://127.0.0.1:8000/health` returned `{"status":"ok","service":"prospecting-api"}`

---

## [2026-07-07 18:57 EDT] — feat: add standalone place id research script

**Files Added:** `research_by_place_id.py`

**Files Modified:** `README.md`, `CHANGELOG.md`

### Summary
Added a standalone Place ID research script that fetches Google Places details
directly and generates a Claude brand brief without requiring Google Sheets.

### Behavior
- Added `research_by_place_id.py` with direct Place Details lookup by Place ID.
- Converts Place Details into the existing research agent prospect format.
- Filters returned Google reviews to five-star reviews before prompting Claude.
- Writes a clean brand brief JSON file in the project root.
- Documented when to use the standalone script versus `run_pipeline.py`.

### Verification
- `python3 -m py_compile research_by_place_id.py`

---

## [2026-07-07 18:52 EDT] — docs: document research brief pipeline usage

**Files Modified:** `README.md`, `CHANGELOG.md`

### Summary
Added README instructions for using `run_pipeline.py` to generate a single
prospect research brief after the prospect exists in Google Sheets.

### Behavior
- Documented the normal `main.py` then `run_pipeline.py` workflow.
- Added examples for `--place-id` and optional `--sheet-id` usage.
- Listed required environment variables and the generated brief output path.

### Verification
- Documentation-only change; local project verification was not applicable.

---

## [2026-06-30 16:59 EDT] — feat: organize scraper configs

**Files Added:** `scrape_configs/batch_6_northeast_southeast.json`,
`scrape_configs/batch_7_midwest_southwest.json`,
`scrape_configs/batch_8_west_secondary.json`

**Files Moved:** `batch_1_west.json`, `batch_2_south_tx.json`,
`batch_3_south_atlantic.json`, `batch_4_midwest.json`,
`batch_5_mountain.json`, `scrape_config.json`, `scrape_config_1.json`
into `scrape_configs/`

**Files Modified:** `run_scraper_parallel.py`, `setup_triggers.py`,
`tests/test_parallel_launcher.py`, `README.md`, `CHANGELOG.md`

### Summary
Added batches 6-8 and organized all scraper config JSON files into a dedicated
`scrape_configs/` folder.

### Behavior
- Added Northeast/Southeast, Midwest/Southwest, and West secondary-market batch
  configs.
- Moved all existing batch and ad hoc scrape configs into `scrape_configs/`.
- Updated the parallel launcher default config path to
  `scrape_configs/scrape_config.json`.
- Updated launcher config loading so relative paths resolve from the project
  directory.
- Updated scheduled trigger setup paths for the moved batch 1-5 configs.
- Updated README examples for the new config paths and batch 6-8 commands.

### Verification
- `python3 -m py_compile run_scraper_parallel.py setup_triggers.py tests/test_parallel_launcher.py`
- `python3 -m json.tool` for every JSON file in `scrape_configs/`
- `python3 -m unittest tests/test_parallel_launcher.py`
- `python3 run_scraper_parallel.py --help`

---

## [2026-06-30 16:40 EDT] — fix: add safe placeholder email username filters

**Files Modified:** `pipeline/email_validation.py`, `tests/test_email_validation.py`,
`CHANGELOG.md`

### Summary
Added explicit rejection for `your@`, `youremail@`, and `yourname@`
placeholder email usernames while preserving legitimate generic business
mailboxes.

### Behavior
- Added `your`, `youremail`, and `yourname` to the always-placeholder username
  filter list.
- Kept `info@` acceptance dependent on the domain so real business addresses
  such as `info@grimascleaningservice.com` remain valid.
- Extended email validation tests to cover the new placeholder usernames and
  the existing legitimate `info@` behavior.

### Verification
- `python3 -m py_compile pipeline/email_validation.py tests/test_email_validation.py`
- `python3 -m unittest tests/test_email_validation.py`

---

## [2026-06-30 15:55 EDT] — feat: add weekly scraper trigger setup

**Files Added:** `batch_1_west.json`, `batch_2_south_tx.json`,
`batch_3_south_atlantic.json`, `batch_4_midwest.json`,
`batch_5_mountain.json`, `setup_triggers.py`

**Files Modified:** `CHANGELOG.md`

### Summary
Added five weekday batch config files and a Claude Code Remote trigger setup
script for autonomous weekly prospect scraping.

### Behavior
- Added Monday-Friday batch configs covering 27 metro ZIP codes across West
  Coast, South TX/Southwest, South Atlantic, Midwest, and Mountain/additional
  metros.
- Added `setup_triggers.py` to create one scheduled Claude Code Remote trigger
  per batch at 9 AM on weekdays.
- Anchored each remote trigger script to this project directory before running
  `run_scraper_parallel.py --config ...`.
- Added setup validation so missing batch files or scraper launcher files are
  caught before remote triggers are created.

### Verification
- `python3 -m py_compile setup_triggers.py`
- `python3 -m json.tool batch_1_west.json`
- `python3 -m json.tool batch_2_south_tx.json`
- `python3 -m json.tool batch_3_south_atlantic.json`
- `python3 -m json.tool batch_4_midwest.json`
- `python3 -m json.tool batch_5_mountain.json`
- `setup_triggers.py` was not executed locally because it would create live
  Claude Code Remote scheduled triggers.

---

## [2026-06-30 15:00 EDT] — feat: filter fake scraper emails

**Files Added:** `pipeline/email_validation.py`, `tests/test_email_validation.py`

**Files Modified:** `pipeline/social.py`, `pipeline/__init__.py`, `main.py`, `CHANGELOG.md`

### Summary
Added source-level email validation so the scraper rejects fake, placeholder,
file-like, platform, and automated email addresses before saving prospect data.

### Behavior
- Added centralized email validation helpers and thread-safe run counters.
- Updated email extraction to collect mailto/body candidates, reject fake
  candidates, and continue through homepage plus contact/about fallback pages
  until a legitimate business email is found.
- Preserved legitimate generic business mailboxes such as
  `info@grimascleaningservice.com` while rejecting placeholder-domain examples
  such as `info@mysite.com`.
- Added email validation stats to the human run summary and `SCRAPING_STATS`
  payload.

### Verification
- `python3 -m py_compile main.py pipeline/social.py pipeline/email_validation.py tests/test_email_validation.py`
- `python3 -m unittest tests/test_email_validation.py`
- `python3 -m unittest tests/test_email_validation.py tests/test_parallel_launcher.py tests/test_dynamic_schema.py`

---

## [2026-06-25 18:51 EDT] — feat: add aggregate reporting to parallel scraper

**Files Modified:** `main.py`, `run_scraper_parallel.py`, `tests/test_parallel_launcher.py`, `README.md`, `CHANGELOG.md`

### Summary
Added machine-readable per-run stats from `main.py` and aggregate final
reporting in `run_scraper_parallel.py` after all scraper instances complete.

### Behavior
- `main.py` now emits a `SCRAPING_STATS:` JSON line to stderr after the normal
  run summary.
- Stats include total new prospects, electrician/HVAC/plumber breakdowns,
  email counts/rates, and Instagram counts/rates.
- The parallel launcher parses each successful child process's stats, sums the
  results, recalculates capture percentages, and prints one final all-instances
  summary.
- Missing or malformed stats are logged as warnings without hiding the child
  process completion result.
- Category reporting normalizes internal plural names such as `electricians`
  and `plumbers` into the singular report keys expected by the launcher.

### Verification
- `python3 -m py_compile main.py run_scraper_parallel.py tests/test_parallel_launcher.py`
- `python3 -m unittest tests/test_parallel_launcher.py tests/test_dynamic_schema.py`
- `python3 run_scraper_parallel.py --help`
- Full live parallel scrape was not run in this verification pass because it
  would perform real Google API calls and append live rows to the production
  sheet.

---

## [2026-06-25 17:52 EDT] — feat: add parallel scraper launcher

**Files Added:** `scrape_config.json`, `run_scraper_parallel.py`, `tests/test_parallel_launcher.py`

**Files Modified:** `README.md`, `CHANGELOG.md`

### Summary
Added a simple JSON-driven launcher that starts multiple `main.py` scraper
instances in parallel using shared radius and category settings.

### Behavior
- Added `scrape_config.json` with `default_radius`, `default_categories`, and a
  flat `zip_codes` list.
- Added executable `run_scraper_parallel.py`.
- The launcher reads config, validates radius/categories/ZIPs, starts each ZIP
  with `subprocess.Popen()`, waits until all instances are launched, then
  summarizes completion by ZIP.
- Added a 1-second delay between launches to reduce startup pressure.
- Added `--config` and safe `--help` support.
- Subprocesses run from the project directory and use the current Python
  interpreter.
- Existing `google_sheets.py` file locking protects final sheet appends.

### Verification
- `python3 -m py_compile run_scraper_parallel.py tests/test_parallel_launcher.py`
- `python3 -m unittest tests/test_parallel_launcher.py tests/test_dynamic_schema.py`
- `python3 run_scraper_parallel.py --help`
- Unit tests verified a mocked 3-ZIP parallel launch path where all scraper
  processes are launched before waiting for completion.
- Unit tests verified `subprocess.Popen()` usage, captured stdout/stderr,
  launch delay calls, config loading, command construction, and config
  validation.
- Full live parallel scrape was not completed in this verification pass because
  it would perform real Google API calls and append live rows to the production
  sheet.

---

## [2026-06-25 17:13 EDT] — fix: serialize Google Sheets writes with a file lock

**Files Modified:** `config.py`, `google_sheets.py`, `README.md`, `tests/test_dynamic_schema.py`, `CHANGELOG.md`

### Summary
Added a cross-process file lock around Google Sheets prospect appends so
multiple prospecting runs can execute in parallel without racing on the final
dedupe-and-append step.

### Behavior
- Added explicit `SHEET_ID`, `CREDENTIALS_PATH`, and `SHEET_NAME` constants in
  `config.py`, sourced from `.env` with the shared service-account path fallback.
- Added `get_lock_file()`, `acquire_sheet_lock()`, and `release_sheet_lock()`
  in `google_sheets.py`.
- `append_prospects()` now acquires the lock before it refreshes schema, reads
  existing Place IDs, appends rows, and reapplies dropdown validation.
- Lock acquisition logs when a process is waiting, when it acquires the lock,
  and when it releases the lock, along with the target spreadsheet ID and tab
  name for the write.
- Lock acquisition times out after 30 seconds instead of hanging indefinitely.

### Verification
- `python3 -m py_compile config.py google_sheets.py tests/test_dynamic_schema.py`
- Added local test coverage for:
  - lock wrapping around `append_prospects()`
  - timeout behavior when the lock cannot be acquired
  - cross-process blocking using a second Python subprocess
- Local parallel lock demo output:
  - `[Lock acquired] path=/tmp/moreclientsco_sheet_write.lock waited=0.00s`
  - `Terminal 1: inside critical section`
  - `[Lock released] path=/tmp/moreclientsco_sheet_write.lock`
  - `[Waiting for lock] path=/tmp/moreclientsco_sheet_write.lock`
  - `[Lock acquired] path=/tmp/moreclientsco_sheet_write.lock waited=1.03s`
  - `Terminal 2: inside critical section`
  - `[Lock released] path=/tmp/moreclientsco_sheet_write.lock`
- Full `unittest` execution remains blocked in this environment because
  `googleapiclient` is not installed.

---

## [2026-06-25 17:04 EDT] — feat: auto-populate Date Added for new prospects

**Files Modified:** `google_sheets.py`, `main.py`, `README.md`, `tests/test_dynamic_schema.py`, `config/PROSPECTS_SCHEMA.json`, `CHANGELOG.md`

### Summary
Reintroduced `Date Added` as a first-class prospect field and now stamps new
prospects with the run date before appending them to the Google Sheet.

### Behavior
- Added `Date Added` to the canonical `SHEET_COLUMNS` layout at column B.
- Added `date_added` to the dynamic prospect field-to-column map.
- Added an existing-sheet guard that inserts a missing `Date Added` column at B
  without overwriting existing cells.
- `main.py` now prints `Adding date_added field to prospects: YYYY-MM-DD` and
  writes that same ISO date to each accepted new prospect.
- Confirmed there is no `_LAST_COL` variable in the current dynamic schema
  implementation; append ranges are calculated from live headers.

### Verification
- `python3 -m unittest tests/test_dynamic_schema.py`
- `python3 -m py_compile main.py google_sheets.py tests/test_dynamic_schema.py`
- Live header check confirmed `Date Added` exists in column B.
- `python3 main.py --zip 11375 --radius 5` completed successfully, found 354
  businesses, skipped 325 duplicates, and appended 29 new prospects.
- Live sheet search found 29 rows with `Date Added = 2026-06-25`.
- Sample verified rows:
  - Jamaica 26 Dentistry → `2026-06-25`
  - Metropolitan Smiles → `2026-06-25`
  - Allure Dental → `2026-06-25`
  - A & A Events → `2026-06-25`
  - Campbell Events → `2026-06-25`
- Existing rows were not overwritten; 1,423 prior rows still have empty
  `Date Added` cells, while 17 prior rows already had non-empty dates.
- The live sheet still reports existing schema drift: `Last Contact Date` is
  missing.

---

## [2026-06-25 16:29 EDT] — fix: use Google address components for prospect addresses

**Files Modified:** `google_places.py`, `main.py`, `google_sheets.py`, `pipeline/__init__.py`, `README.md`, `tests/test_dynamic_schema.py`, `config/PROSPECTS_SCHEMA.json`, `CHANGELOG.md`

**Files Removed:** `pipeline/address.py`

### Summary
Replaced formatted-address string parsing with direct Google Places
`address_components` extraction for `Street`, `City`, `State`, and `ZIP`.

### Behavior
- `get_place_details()` now requests `address_components`.
- Discovered prospects now carry the raw Google `address_components` array.
- `main.py` extracts:
  - `street_number` + `route` → `Street`
  - `locality` → `City`
  - `administrative_area_level_1.short_name` → `State`
  - `postal_code` → `ZIP`
- Removed the redundant `pipeline/address.py` formatted-address parser.
- Updated README and tests to reflect API-component-based address extraction.
- Refreshed `config/PROSPECTS_SCHEMA.json` from the live sheet. The live sheet
  currently places `Street`, `City`, `State`, and `ZIP` directly after
  `Address`, while `Email` is column 24; dynamic header mapping writes to the
  correct cells.

### Verification
- `python3 -m unittest tests/test_dynamic_schema.py`
- `python3 -m py_compile main.py google_places.py google_sheets.py tests/test_dynamic_schema.py pipeline/__init__.py`
- Live header check confirmed `Street`, `City`, `State`, and `ZIP` exist in the
  Google Sheet at columns 5-8.
- `python3 main.py --zip 11385 --radius 5` completed successfully, found 359
  businesses, skipped 325 duplicates, and appended 34 new prospects.
- Live spot-check of the last five appended rows confirmed populated address
  components:
  - PureGym Gates Avenue → `1002 Gates Ave`, `Brooklyn`, `NY`, `11221`
  - Vibe Fitness BQE → `26-50 Brooklyn Queens Expy W`, `Woodside`, `NY`, `11377`
  - Liberty Dental → `127-06 Liberty Ave`, `South Richmond Hill`, `NY`, `11419`
  - Atlas Park Dental → `80-28 Cooper Ave #207`, `Glendale`, `NY`, `11385`
  - New Image Dental → `3-41 St Nicholas Ave #3`, `Ridgewood`, `NY`, `11385`
- The live sheet still reports existing schema drift: `Last Contact Date` is
  missing.

---

## [2026-06-25 16:16 EDT] — feat: add scraper contact extraction toggles

**Files Modified:** `main.py`, `README.md`, `tests/test_dynamic_schema.py`, `CHANGELOG.md`

### Summary
Added CLI flags to control whether the main prospect scraping pipeline extracts
emails, Instagram URLs, both, or neither from new prospect websites.

### Behavior
- Added `--skip-email` and `--skip-instagram` to `main.py`.
- Default scraping still attempts both extractors.
- Email-only runs can use `--skip-instagram`.
- Instagram-only runs can use `--skip-email`.
- Google-data-only runs can use both flags to skip the contact extraction
  executor entirely.
- The summary now prints whether each extractor was enabled or disabled.

### Verification
- `python3 -m unittest tests/test_dynamic_schema.py`
- `python3 -m py_compile main.py tests/test_dynamic_schema.py`
- `python3 -B main.py --help`

---

## [2026-06-25 16:09 EDT] — feat: add contact backfill toggles and Instagram extraction

**Files Modified:** `backfill_emails.py`, `pipeline/social.py`, `README.md`, `tests/test_dynamic_schema.py`, `CHANGELOG.md`

### Summary
Expanded the existing backfill script from email-only enrichment to configurable
contact enrichment for both `Email` and `Instagram URL`.

### Behavior
- Added `--skip-email` and `--skip-instagram` flags.
- Default backfill now attempts both missing emails and missing Instagram URLs.
- Queue building checks the live `Email` and `Instagram URL` columns and only
  targets empty cells for the selected fields.
- Writes remain non-destructive: populated cells are skipped and never
  overwritten.
- Checkpointing is now target-specific, so an email attempt does not cause a
  later Instagram-only resume to skip that row.
- Improved website extraction robustness for bare domains, common contact/about
  pages, HTML entity decoding, and obvious asset-file false positives.

### Verification
- `python3 -m unittest tests/test_dynamic_schema.py`
- `python3 -m py_compile backfill_emails.py pipeline/social.py tests/test_dynamic_schema.py`

---

## [2026-06-25 15:53 EDT] — feat: add category-filtered prospect scraping

**Files Modified:** `main.py`, `categories.py`, `README.md`, `tests/test_dynamic_schema.py`, `CHANGELOG.md`

### Summary
Added a `--categories` CLI parameter so prospecting runs can target only
specific business types instead of scraping every configured category.

### Behavior
- Added comma-separated category filtering such as
  `--categories electrician,hvac,plumber`.
- Category matching now accepts canonical names, Google Places query names,
  singular forms, and case/spacing variants.
- Unknown category filters fail fast with a clear list of available categories.
- `main.py` now passes only the selected categories to Google Places discovery,
  reducing API searches and preventing unrelated categories from being appended.

### Verification
- `python3 -m unittest tests/test_dynamic_schema.py`
- `python3 -m py_compile main.py google_places.py categories.py tests/test_dynamic_schema.py`

---

## [2026-06-23 23:06 EDT] — feat: add parsed address columns to prospecting pipeline

**Files Modified:** `google_sheets.py`, `main.py`, `pipeline/__init__.py`, `README.md`, `tests/test_dynamic_schema.py`, `CHANGELOG.md`

**Files Added:** `pipeline/address.py`

### Summary
Added address component parsing so new prospects now populate separate `Street`,
`City`, `State`, and `ZIP` fields in addition to the original full `Address`.

### Behavior
- Added `pipeline/address.py` with `parse_address()` for Google Places formatted
  addresses such as `6079 Myrtle Ave, Ridgewood, NY 11385, USA`.
- Added the parsed address columns after `Email` in the canonical PROSPECTS
  schema and row serialization map.
- Added a narrow existing-sheet migration that appends missing parsed address
  headers without reordering existing columns.
- Updated `main.py` to parse each accepted new prospect before append.
- Parse failures log a warning and return empty component fields without
  interrupting the run.

### Verification
- `python3 -m unittest tests/test_dynamic_schema.py`
- `python3 -m py_compile main.py google_sheets.py pipeline/address.py`
- `python3 main.py --zip 11385 --radius 5` completed successfully, found 360
  businesses, skipped 324 duplicates, and appended 36 new prospects.
- The live sheet reported existing schema drift: `Last Contact Date` is missing.

---

## [2026-06-10 19:49 EDT] — fix: add dynamic prospects schema mapping

**Files Modified:** `google_sheets.py`, `backfill_emails.py`, `README.md`, `CHANGELOG.md`

**Files Added:** `config/PROSPECTS_SCHEMA.json`, `tests/test_dynamic_schema.py`

### Summary
Added a dynamic PROSPECTS schema system that reads row 1 on every run, builds a
header-to-index mapping, compares it to `config/PROSPECTS_SCHEMA.json`, and
updates the cache when columns are rearranged, added, or removed.

### Behavior
- Refactored prospect row serialization to place values by header name instead
  of fixed list positions.
- Refactored append-time Place ID dedupe to read the live Place ID column.
- Refactored dropdown validation to use mapped `Status` and `Last Outcome`
  column indexes.
- Refactored email backfill to use the same `SheetSchema` mapping and shared
  column-letter conversion, including columns beyond `Z`.
- Missing expected columns now log warnings and skip only the affected fields
  or validations.

### Verification
- Added local `unittest` coverage for rearranged columns, deleted columns,
  backfill queue mapping, default cache shape, and column letters beyond `Z`.

---

## [2026-06-10 19:41 EDT] — fix: update prospect sheet append schema

**Files Modified:** `google_sheets.py`, `main.py`, `config.py`, `README.md`

### Summary
Updated the prospecting assistant to write the new PROSPECTS schema with
`Last Contact Date` and `Last Outcome`, removed the old exported `Date Added`
column, and kept new rows append-only with `Status = New` by default.

### Sheets Behavior
- Added append-time Place ID checks inside `append_prospects()` so duplicate
  Place IDs are skipped even if the upstream dedupe pass is bypassed.
- Added non-strict dropdown validations for `Status` and `Last Outcome` on
  rows 2-10000.
- Added one-time schema normalization for older sheets so existing rows are
  reshaped into the new column order without moving old notes into outcome
  fields.

### Verification
- `python3 -m py_compile google_sheets.py main.py config.py`
- Local mocked Sheets client check confirmed duplicate Place IDs are skipped
  and the serialized row uses the new 21-column order.

---

## [2026-06-08] — fix: handle backfill batch timeouts gracefully

**Files Modified:** `backfill_emails.py`

### Summary
Patched `extract_batch()` so `as_completed(..., timeout=_BATCH_TIMEOUT)` no
longer crashes the script when a batch has unfinished futures. Timed-out batches
now log unfinished row index, business name, and website, cancel unfinished
futures where possible, and return partial completed results.

### Additional Guard
Wrapped `extract_email()` calls in a killable process-level timeout so a wedged
website parse cannot keep a worker thread alive forever after the batch timeout
path runs.

### Verification
- `python3 -m py_compile backfill_emails.py`
- Local synthetic timeout test confirmed the expected message:
  `Batch timeout: 3 unfinished futures. Skipping unfinished websites.`
- The requested live `python3 backfill_emails.py --dry-run` and
  `python3 backfill_emails.py` commands could not be completed because the
  escalated network run was blocked by the platform usage limit.

---

## [2026-06-08] — docs: diagnose backfill_emails.py hang report

**Files Added:** `backfill_diagnosis.txt`

### Summary
Investigated the reported `backfill_emails.py` hang around row 300 without
changing the backfill implementation. No live stuck process or `backfill_debug.log`
was available, so the exact START-without-END URL could not be identified.

### Findings
- Read the live sheet row window around rows 290–320.
- Tested the row-300 candidate (`https://newyorkcityelectricianss.com/`) with
  `requests.get(timeout=4)` and with `socket.setdefaulttimeout(4)`; both returned
  quickly.
- Probed the row-window URLs with `requests.get(timeout=4)`; none hung during
  the diagnostic run.
- Confirmed current `backfill_emails.py` already contains the prior anti-hang
  safeguards from commit `106833f`: socket timeout, batch processing, per-batch
  timeout, per-future timeout, checkpointing, and fresh Sheets clients.

### Output
Full findings were written to `backfill_diagnosis.txt`.

---

## [2026-06-06] — fix: rewrite backfill_emails.py to prevent hangs at high volume

**Files Modified:** `backfill_emails.py`

### Root Cause
The original script submitted all futures (up to 1100+) to one `ThreadPoolExecutor`
at once and waited for them under a single 10-minute ceiling. When slow or hanging
sites accumulated, the OS exhausted its socket quota and new connections stalled
indefinitely. The `requests` timeout parameter controls read/write timeouts but
does not reliably cancel an SSL handshake that never completes — so individual
workers hung without triggering the Python-level timeout, eventually blocking the
entire executor.

### Fix 1 — Socket-level timeout (`socket.setdefaulttimeout(5)`)
Added at module level, before any network calls. This catches connection hangs
that occur at the SSL handshake stage before `requests` even takes over. Acts as
a hard OS-level safety net regardless of what the HTTP layer does.

### Fix 2 — Reduced workers from 10 → 5
Fewer concurrent workers means fewer simultaneous open sockets, which reduces
the chance of hitting OS-level socket exhaustion on a large backfill run.

### Fix 3 — Batch processing (BATCH_SIZE = 50)
Instead of submitting all rows at once, the script now processes 50 rows per
`ThreadPoolExecutor` context. Each batch has its own `as_completed(timeout=60)`
and `future.result(timeout=5)` double guard:
- `as_completed(timeout=60)` — entire batch must complete in 60 seconds
  (1.2 seconds average per site).
- `future.result(timeout=5)` — individual future result() call safety cap.
- On `TimeoutError`, remaining futures in the batch are marked as attempted
  (empty string) and the loop continues with the next batch.

### Fix 4 — Write immediately after each batch
The original script collected all results then wrote at the very end. If it
hung, all collected emails were lost. Now `write_batch_results()` is called
after every batch of 50, so at most 50 rows' results can be lost on interrupt.
Each write call creates a fresh `GoogleSheetsClient` to prevent stale SSL
connections from accumulating over a long multi-batch run.

### Fix 5 — Checkpoint + `--resume` flag
A JSON checkpoint file (`backfill_checkpoint.json`) is saved after every
successful batch write. It stores the set of all attempted row indices
(both found and not-found). `--resume` loads this file and filters the
enrichment queue to skip already-processed rows, so the script can be
interrupted with Ctrl+C and restarted from where it stopped.

### New constants
| Name | Value | Purpose |
|---|---|---|
| `CHECKPOINT_FILE` | `backfill_checkpoint.json` | Persists progress across runs |
| `BATCH_SIZE` | `50` | Rows per executor context |
| `_MAX_WORKERS` | `5` | Parallel threads per batch |
| `_BATCH_TIMEOUT` | `60` | Seconds ceiling per batch |
| `_FUTURE_TIMEOUT` | `5` | Per-future `result()` cap |

### New functions
- `load_checkpoint(resume: bool) → set[int]` — reads checkpoint file when `--resume` is passed
- `save_checkpoint(completed_rows: set[int])` — writes checkpoint file after each batch
- `extract_batch(batch) → dict[int, str]` — runs one batch with all timeout guards
- `write_batch_results(results, email_col, config) → int` — writes one batch; fresh client per attempt
- `_make_sheets_client(config)` — creates a fresh `GoogleSheetsClient` (used by write and read)

### Run commands
```
python3 backfill_emails.py             # fresh run
python3 backfill_emails.py --dry-run   # preview only, no writes
python3 backfill_emails.py --resume    # continue from checkpoint
```

### Expected performance for 1105 rows
- ~22 batches × ~60s max per batch = under 22 minutes worst case
- Typical (most sites respond in < 4s): 5–10 minutes total
- Checkpoint saves after every batch — safe to Ctrl+C and resume at any point

---

## [2026-06-06] — feat: add backfill_emails.py — parallel email enrichment for existing sheet rows

**Files Added:** `backfill_emails.py`

### What This Script Does
One-shot enrichment tool for the existing Google Sheet. Reads all prospect rows,
identifies rows where the Website column is populated but the Email column is empty,
runs `extract_email()` on all matching websites in parallel, and writes the results
back to the sheet in a single batch API call.

### Script Structure

**`parse_args()`**
- Accepts one optional flag: `--dry-run`.
- Dry-run mode runs the full extraction but prints what would be written instead
  of sending any API write calls.

**`read_all_rows()`**
- Uses `sheets_client.service.spreadsheets().values().get()` with `A:Z` range so
  it captures all columns regardless of sheet width.
- Exits cleanly with a printed error message on any `HttpError` or unexpected
  exception — never crashes with a raw traceback.

**`find_column_indices()`**
- Dynamically resolves `"Website"` and `"Email"` column indices from the live
  header row, so the script continues to work correctly if columns are reordered
  or new columns are added.
- Exits with a clear error if either column is missing.

**`build_enrichment_queue()`**
- Pads short rows to the full header width before index access (avoids
  `IndexError` on rows with trailing empty cells).
- Returns only rows where `website` is non-empty AND `email` is empty —
  never overwrites existing email values.
- `row_index` is the correct 1-based Sheets row number (`i + 2`:
  +1 for the header row, +1 for 0-based list index).

**`extract_emails_parallel()`**
- `ThreadPoolExecutor(max_workers=10)` — up to 10 sites in flight at once.
- Hard 10-minute ceiling via `as_completed(timeout=600)`. On `TimeoutError`,
  the executor is shut down without waiting and partial results are returned —
  never hangs the terminal.
- Prints progress every 10 rows so the user can see it's working.

**`build_batch_payload()`**
- Converts `row_index → email` results into Sheets `batchUpdate` data format.
- Uses `string.ascii_uppercase[email_col]` to derive the column letter (Email
  is column W, index 22 — safely within the A–Z range).
- Only includes rows with a non-empty email so no blank cells are written.

**`write_batch()`**
- Sends one `batchUpdate` API call for all results — O(1) API calls regardless
  of how many rows are updated.
- Retries once on failure with a 2-second pause before the second attempt.
- Returns `True`/`False` so the caller can print an appropriate message.

**`print_summary()`**
- Prints total prospects, prospects with website, skipped count, emails found,
  success rate, and still-empty count.
- Appends `(DRY RUN)` to the header line when applicable.

### Run Commands
```
cd ~/growth_agency/internal-tools/service-business-prospecting-assistant
source .venv/bin/activate

python3 backfill_emails.py            # live run
python3 backfill_emails.py --dry-run  # preview only
```

### What Is Not Overwritten
- Rows that already have an email in column W are excluded from the queue
  before any network calls are made.
- Rows with no website are skipped entirely.
- The batch payload only contains entries where `extract_email()` returned a
  non-empty string — blank results are never written.

### Verification Steps
1. Run `--dry-run` first to confirm the queue size and preview emails.
2. Run live and confirm the console shows `Wrote N emails to sheet`.
3. In the Google Sheet, spot-check column W for several rows:
   - Rows with a website and previously empty email → populated.
   - Rows without a website → unchanged.
   - Rows that already had an email → unchanged.
4. Row numbers in column W must match the correct business rows — no off-by-one.

---

## [2026-06-06] — feat: add parallel email extraction to prospecting pipeline

**Files Modified:** `pipeline/social.py`, `google_sheets.py`, `main.py`

### What Changed

**pipeline/social.py — new `extract_email()` function**
- Added `extract_email(website_url: str) -> str` directly below `extract_instagram_url()`.
- Two-pass strategy: fetches the homepage first, then `/contact` as a fallback.
- Within each page, checks `mailto:` href links before falling back to plain-text
  email-pattern scanning — mailto links are the most authoritative signal.
- Filters out framework/platform emails via `_IGNORE_EMAIL_DOMAINS` list:
  `sentry.io`, `wixpress.com`, `squarespace.com`, `wordpress.com`, `example.com`,
  `googleapis.com`, `schema.org`, `w3.org`.
- Skips `noreply@` and `no-reply@` prefixes — never a business contact.
- Hard 4-second timeout per HTTP request (`_EMAIL_TIMEOUT = 4`) shared with
  `_USER_AGENT` already defined in the module.
- Never raises exceptions — all errors are caught and logged at WARNING level;
  empty string returned on any failure.
- Updated module docstring to describe both extractors and note thread-safety.

**google_sheets.py — Email column added (W)**
- Appended `"Email"` to the end of `SHEET_COLUMNS` (position 23, column W).
- Updated `_LAST_COL` from `"V"` to `"W"` (23 columns total: A through W).
- Updated module docstring column layout table to include column W with description.
- Added `prospect.get("email", "")` to the end of `prospect_to_sheet_row()`.

**main.py — Parallel extraction replacing sequential stub**
- Added `import logging`, `import time`, and
  `from concurrent.futures import ThreadPoolExecutor, as_completed` at the top.
- Added `logger = logging.getLogger(__name__)` at module level.
- Removed `enriched["instagram_url"] = ""` stub from the deduplication loop.
- After the loop, new parallel extraction block:
  - Filters to `prospects_with_sites` (those with a `website` field).
  - Defines `enrich_prospect()` — calls both `extract_email()` and
    `extract_instagram_url()` for one prospect; import kept inline to avoid
    circular-import issues.
  - Runs with `ThreadPoolExecutor(max_workers=10)` — up to 10 sites in flight
    at once, bounded by `as_completed(timeout=180)`.
  - Hard 3-minute ceiling (`EXTRACTION_TIMEOUT = 180`): if elapsed time exceeds
    the ceiling, logs a warning, shuts the executor down without waiting, and
    breaks — partial results are kept and written to the sheet.
  - Fallback loop sets `email = ""` and `instagram_url = ""` on any prospect
    that wasn't reached before the ceiling.
  - Logs summary counts on completion: `emails: N, instagram: N`.
- `print_summary()` updated:
  - Docstring updated to list the new "Contact data extraction results" section.
  - New "Contact Data Extraction" block printed between Website Coverage and
    Lead Score Distribution showing:
    `Emails found: X / Y prospects with websites`
    `Instagram URLs: X / Y prospects with websites`

### Column Safety
- Columns A through V are completely unchanged — all existing rows are unaffected.
- Column W (`Email`) will be empty for all existing rows; new prospects
  auto-populate it when the website has a publicly listed contact email.

### Why Parallel
Per-prospect HTTP fetches ran sequentially in the previous Instagram extractor,
adding 0–5 seconds per site and causing SSL timeout failures at scale (60+ prospects).
This implementation runs both extractors concurrently with a hard ceiling so the
total pipeline time grows by at most 3 minutes regardless of prospect count.

### Verification Steps
```
cd ~/growth_agency/internal-tools/service-business-prospecting-assistant
source .venv/bin/activate
python3 main.py --zip 11375 --radius 5
```
Confirm:
1. Pipeline completes in under 5 minutes total.
2. No hanging or indefinite waits — each request caps at 4 seconds.
3. New column W header `Email` appears in Google Sheet.
4. Businesses with publicly listed emails populate column W.
5. Console report shows `Contact Data Extraction` section with counts.
6. All other columns (A–V) and pipeline stages are unaffected.

---

## [2026-05-27] — chore: disable Instagram URL extraction; preserve column for manual entry

**Files Modified:** `main.py`, `pipeline/social.py`

### What Changed

**main.py — Extraction block removed**
- Removed the conditional `if enriched.get("website")` block that called
  `extract_instagram_url()` and its inline `from pipeline.social import` statement.
- Replaced with a single unconditional assignment: `enriched["instagram_url"] = ""`.
  The field is still written to every prospect dict so the Google Sheet column (V)
  continues to receive a value on every row — it is just always empty.

**main.py — `print_summary()` Instagram section removed**
- Removed the "Instagram URL Coverage" section (count and percentage block) that
  would always show 0 / 0.0% with extraction disabled. The Website Coverage and
  Lead Score sections are unaffected.

**pipeline/social.py — Disable comment added**
- Added a four-line comment block immediately after the module docstring explaining
  that extraction is disabled, why (performance impact at scale), and exactly how
  to re-enable it (import and call `extract_instagram_url()` in `main.py`).
- The file, function, and all implementation code are fully preserved.

### What Was Kept
- `pipeline/social.py` — file intact, function intact, ready to re-enable.
- `"Instagram URL"` column V in `google_sheets.py` — unchanged; rows will have an
  empty string written automatically, which keeps the column present and available
  for manual entry in the sheet.
- All other pipeline functionality — unchanged.

### Why
Per-prospect HTTP fetches added 0–5 seconds per site at the tail of each enrichment
loop iteration. At scale (60+ prospects per run) this caused SSL timeout errors and
significantly slowed pipeline completion. The column is preserved so high-priority
prospects can have Instagram URLs entered manually after the run.

### Verification Steps
```
cd ~/growth_agency/internal-tools/service-business-prospecting-assistant
source .venv/bin/activate
python3 main.py --zip 07032 --radius 15
```
Confirm:
1. Pipeline completes without SSL timeout errors.
2. Console report has no "Instagram URL Coverage" section.
3. Google Sheet column V (`Instagram URL`) exists with empty cells for new rows.
4. All other columns (A–U) populate correctly.

---

## [2026-05-27] — feat: add Instagram URL extraction to prospecting pipeline

**Files Added:** `pipeline/social.py`
**Files Modified:** `google_sheets.py`, `main.py`, `pipeline/__init__.py`

### What Changed

**pipeline/social.py — New file**
- New module `extract_instagram_url(website_url: str) -> str` that fetches a business
  website and scans the HTML for any `href` containing `instagram.com/`.
- Uses `requests` with a 5-second timeout and a realistic `User-Agent` header to reduce
  bot-detection blocks.
- Extracts the matched URL, prepends `https://` if no scheme is present, and strips
  trailing slashes for consistent formatting.
- Returns empty string on any exception (timeout, connection error, HTTP error) —
  never propagates an error into the main pipeline.
- Logs `WARNING`-level messages when a site is unreachable or times out.

**google_sheets.py — Column layout (A–U → A–V)**
- Appended one new column to the END of `SHEET_COLUMNS` (position 22, column V):
  `"Instagram URL"` — extracted from the business website; auto-populated on creation.
- Updated `_LAST_COL` from `"U"` to `"V"` (22 columns total: A through V).
- Updated module docstring column layout table to include column V with description.
- Added `prospect.get("instagram_url", "")` to the end of `prospect_to_sheet_row()`.

**main.py — Instagram extraction in the enrichment loop**
- After `enrich_with_score()`, conditionally calls `extract_instagram_url()` for each
  new prospect that has a `website` field.
- Prospects without a website get `instagram_url = ""` without any network call.
- Import of `pipeline.social` is kept inline (inside the loop) to avoid circular-import
  issues during module initialization.

**main.py — `print_summary()` Instagram coverage block**
- Added an "Instagram URL Coverage" section between Website Coverage and Lead Score
  Distribution, showing count and percentage of new prospects with an Instagram URL.

**pipeline/__init__.py**
- Updated module list docstring to include `social.py`.

### Column Safety
- Columns A through U are completely unchanged — all existing rows are unaffected.
- Column V will be empty for all existing rows; new prospects auto-populate it when
  a website is present and the site links to Instagram.

### Verification Steps
```
cd ~/growth_agency/internal-tools/service-business-prospecting-assistant
source .venv/bin/activate
python3 main.py --zip 11375 --radius 5
```
Confirm:
1. New column V header `Instagram URL` appears in Google Sheet.
2. Businesses with websites that link Instagram show the URL in column V.
3. Businesses without a website show an empty string in column V.
4. Console report includes "Instagram URL Coverage" section.
5. Pipeline runtime is not significantly slower (5-second cap per site).

### Anything To Watch
- Best-effort only: not every business links Instagram from their homepage.
- Sites using JavaScript-rendered links (React/Vue SPAs) will not have the link
  in the initial HTML response — `extract_instagram_url` only parses the raw response body.
- The 5-second timeout means slow sites are skipped rather than stalling the run.
- Businesses with no website will always return empty — this is intentional.

---

## [2026-05-21] — feat: add search params, date tracking columns, and expanded status options

**Files Modified:** `google_sheets.py`, `main.py`

### What Changed

**google_sheets.py — Column layout (A–Q → A–U)**
- Appended four new columns to the END of `SHEET_COLUMNS` (positions 18–21, columns R–U):
  - `"Search ZIP Code"` (R) — ZIP code used in the discovery run, auto-populated from CLI args
  - `"Search Radius (mi)"` (S) — radius used in the discovery run, auto-populated from CLI args
  - `"Date Contacted"` (T) — date of first outreach attempt; left empty on creation, manual entry only
  - `"Follow-Up Date"` (U) — date of next intended follow-up; left empty on creation, manual entry only
- Updated `_LAST_COL` from `"Q"` to `"U"` (21 columns total: A through U)
- Updated column layout docstring at the top of the file to reflect the full A–U layout with column letters and descriptions

**google_sheets.py — `prospect_to_sheet_row()`**
- Appended four new fields at the end of the return list, matching the new SHEET_COLUMNS order exactly:
  `search_zip`, `search_radius`, `date_contacted`, `follow_up_date`
- Added `# --- Manually updated fields ---` comment block above these four lines explaining auto-populate vs. manual-entry intent

**google_sheets.py — `STATUS_OPTIONS`**
- Replaced the previous 10-option list with an expanded 18-option list covering the full outreach lifecycle:
  `New → Reviewed → Good Fit / Not Fit → Called → Contacted → FollowUp 1/2/3 → Interested → Demo Booked → Proposal Sent → Negotiating → Meeting Booked → Client`
  Dead-end statuses: `Not Interested`, `Ghosted`, `Do Not Contact`
- Updated the STATUS_OPTIONS docstring to show the full stage progression

**main.py — Search parameter tagging**
- Inside the deduplication loop, added two lines BEFORE `enrich_with_score()` to tag each prospect with the run's CLI parameters:
  `prospect["search_zip"] = args.zip_code` and `prospect["search_radius"] = args.radius`
- `date_contacted` and `follow_up_date` are intentionally NOT set here — manual entry only

### Column Safety
- Columns A through Q are completely unchanged — existing 341 rows are unaffected and not shifted
- Columns R–U will be empty for all existing rows; new prospects auto-populate R and S; T and U remain empty on creation

### Verification Steps
```
cd ~/growth_agency/internal-tools/service-business-prospecting-assistant
source .venv/bin/activate
python3 main.py --zip 11375 --radius 5
```
Confirm in Google Sheets:
1. Columns A–Q unchanged and aligned for all existing rows
2. Column headers R → `Search ZIP Code`, S → `Search Radius (mi)`, T → `Date Contacted`, U → `Follow-Up Date`
3. New prospect rows show correct ZIP and radius in R and S; T and U empty
4. Status dropdown on all rows shows the full 18-option list

### Anything To Watch
- The `ensure_header()` call will rewrite the header row if it detects a mismatch (R–U headers will be added on first run)
- The `apply_status_dropdown()` call is idempotent — it updates the validation rule on every run without resetting existing cell values
- Existing rows with old status values (`"Followed Up"` → replaced by `"FollowUp 1/2/3"`) will show a validation warning in Sheets until manually updated; they are not corrupted

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
