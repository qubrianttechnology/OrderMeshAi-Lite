# 31 October 2026: profile, basic settings and inbox management

Settings now starts with a personal profile (name, phone and private JPG/PNG/WebP profile photo) and owner/admin business basics (workspace name, contact email/phone and address). Photos are validated, resized and stored privately. Sign-in email, actual business type, currency and report timezone are informational. Business Intelligence remains a dedicated section; the business setup shortcut opens it. Existing subscription setup remains under Business workflow & subscription.

Settings > Your dashboard > Layout offers Recommended or Full business dashboard. Qubriant's software/service workflow differs from the wholesale demo by design. Full layout exposes sales/profit charts, inventory and operations alongside service requests without changing business type or AI extraction workflow. Existing workspace layout choices were not changed automatically.

WhatsApp inbox supports Active/Unread/Archived/All views, pin/unpin, archive/unarchive and mark read/unread, preserving existing category/search/reply/customer-linking controls. Background polling does not clear unread markers. New incoming messages reopen archived chats. Inbox management is scoped to the current workspace and owner/admin/staff; viewers cannot manage chats.

Migration 0015 was applied to the local development database after SQLite backup. Existing user/workspace/product/conversation/message counts were preserved; local API and dashboard health returned HTTP 200. No new public tunnel, real outbound WhatsApp send, production-mode switch or external chatbot data sharing was introduced.

Validation: 181 backend tests passed; 3 PostgreSQL-only tests skipped. Five distinct Edge browser workflows passed across final targeted runs: profile/photo/basic settings/full layout; inbox management; category filters/search; WhatsApp order approval/local chatbot settings; service-business profile/catalog/layout. Frontend lint, TypeScript and production build passed. Desktop/mobile settings preview loaded, with no horizontal page overflow at 390px. Screenshots: `.local/account-settings-desktop.png`, `.local/account-settings-mobile.png`.

# Dashboard performance charts — 30 October 2026

Added five actual-data Overview panels: gross profit breakdown, low-stock list, profit versus posted sales, top-selling products and staff performance. Period choices are 7/30/90 days; financial amounts use LKR, tax/returns and known cost snapshots. Unknown costs remain incomplete. Financial access is owner/admin only. Tools remain directly accessible below the performance area and from the sidebar. See docs/DASHBOARD_CHARTS.md for definitions and validation (178 backend passed, 3 PostgreSQL skipped; 3 targeted browser cases passed).

# Dashboard tool visibility and product access — 30 October 2026

Existing updates are now discoverable through an Overview tool directory and direct sidebar links to POS, Purchases, Warehouses, Returns, Credit & payments, Reports & expenses, Delivery and Team. Product businesses show Products & inventory, with barcode-aware search, 50-row pagination and selected-workspace context. Catalog data loads even when analytics or another independent request fails. Product-business owners can reopen a hidden catalog using its menu entry; service-business saved visibility remains respected. Navigation preserves the selected feature across reloads; the POS quick action consistently opens POS.

Validation: four existing browser workflows passed (commerce, wholesale products, general workflow, service-business settings); the new navigation/partial-failure/pagination/hidden-catalog recovery/mobile check passed on its final run. ESLint/TypeScript and isolated production build passed. Live local preview confirmed all 3,000 demo products, 50 visible rows, catalog-wide search, direct Purchasing and reload persistence. Screenshots: `.local/dashboard-tools.png` and `.local/dashboard-products.png`. Sample products remain exclusively in OrderMesh Demo Wholesale; no sample catalog was copied into another workspace.

# 30 October 2026: wholesale operations and isolated demo

POS, barcode search, wholesale pricing/MOQs, supplier purchase orders/GRN, warehouse balances/transfers, credit limits/aging, returns/refunds, expenses/profit reports, delivery and team permissions are implemented. Notification centre now has per-user read tracking and optional sound/desktop alerts. Local migrations 0013–0014 were backed up/applied; real inventory was allocated to Main without changing quantities. A separate demo owner/workspace has 3,000 synthetic products and no WhatsApp connection. Local multilingual and one synthetic live `gpt-6-luna` extraction passed; real chatbot data export remains disabled. See [workflow and limits](docs/COMMERCE_WORKFLOWS.md). Validation: 176 backend tests passed; 3 PostgreSQL-only tests skipped because no disposable PostgreSQL test database is configured. All 19 Edge browser tests passed. Backend Ruff, frontend lint/TypeScript and the isolated production build passed. A further migration-preservation run passed all 4 migration/seed tests.

Earlier updates below are historical; their statements about unavailable POS/credit/warehouse features are superseded by this update.

# Latest update - 30 October 2026: direct Business Intelligence answers

Users can answer business questions directly in the dashboard, without downloading or uploading documents. Guided groups, review/save, validation, prefilled saved answers and an all-questions edit view are implemented. Legacy document import is optional and collapsed. Six focused Edge checks and final lint/TypeScript passed, with production build validation; mobile layout/screenshot reviewed. No backend schema changes or external AI processing were added. See docs/BUSINESS_INTELLIGENCE.md and docs/COMPLETION_STATUS.md.

# Latest update - 30 October 2026: WhatsApp order approval and local chatbot

Orders now shows pending WhatsApp requests with availability, owner/admin approval and rejection. Notifications and visible-dashboard data refresh about every 15 seconds. Approval validates stock/prices and deducts stock once; a durable reply queue handles availability, confirmation and delivery uncertainty. Settings offers an opt-in local chatbot with saved business FAQs. The owner declined OpenAI chatbot conversation data sharing, so no generative conversation integration was added. Enabled chatbot workflows keep WhatsApp text local and send audio/images to manual review. Migration 0012 applied after backup. Backend 163 passed/3 PostgreSQL-only skipped; Edge 17 passed, plus final approval UI verification; build/lint/type checks passed. Live outbound replies still need recipient allowlist setup and acceptance testing. See docs/WHATSAPP_ORDER_APPROVAL.md.

# Latest update - 30 October 2026: wholesale/distributor focus

New workspaces default to wholesale. The home/signup pages target wholesalers and distributors. Product categories and inventory category filtering cover electronics, fashion, beauty, grocery, household, packaging, stationery, hardware and vehicle parts. Primary business category and SKU/alias/part-number search are supported; existing workspace types/data are preserved. Migration 0011 applied after a local backup. Backend 153 passed/3 PostgreSQL-only skipped; 16 Edge cases passed across the full run and marketing assertion rerun; build/lint/type checks passed. See docs/WHOLESALE_AND_DISTRIBUTORS.md and docs/COMPLETION_STATUS.md for scope and remaining acceptance work.

> Business Intelligence update, 28 October 2026: document suggestions, target-client context, private/spam examples and classification preview are implemented. Current evidence: docs/BUSINESS_INTELLIGENCE.md and docs/COMPLETION_STATUS.md.

> Business dashboard update, 28 October 2026: business-specific sections and labels, owner/admin module preferences, and service-request summaries are implemented. See docs/BUSINESS_DASHBOARDS.md and docs/COMPLETION_STATUS.md.

> Update, 28 October 2026: this document contains the historical audit below.
> Current image extraction is implemented in the dashboard and WhatsApp worker;
> see docs/IMAGE_EXTRACTION.md and docs/COMPLETION_STATUS.md for current test
> evidence and live-provider limitations. Voice and Tamil were also added after
> the original audit. Local tests do not establish live provider approval/accuracy.

# OrderMesh AI Lite — Project Audit

**Audit date:** 23 October 2026  
**Scope:** Existing implementation and available local checks. This is an
implementation audit, not a penetration test, production certification, or review
of a live Supabase project.

## Executive summary

OrderMesh AI Lite is an implemented Phase 1 application, not just a landing-page
mockup. It has a Next.js/TypeScript web app and a FastAPI/SQLAlchemy API with
working authentication, organization membership checks, catalog and stock
operations, human-reviewed order extraction, order confirmation, invoices and
analytics. The automated SQLite-backed API tests and real-browser workflows pass.

Phase 3 foundations are implemented and locally verified against SQLite. Alembic
now supports a separate migration URL, the Postgres test suite is gated behind an
explicit disposable-database opt-in, the Inbox reports configuration/role
diagnostics, and the AI flow has structured unit/delivery-instruction fields plus
a local fallback. Live Supabase/PostgreSQL, Meta, and AI provider connectivity
remain unverified because no credentials or external test services were provided.

The production PostgreSQL path, FORCE RLS policies and concurrent order tests are
implemented, but **were not executed in this audit**: Docker is not installed and
`TEST_POSTGRES_URL` is not configured. Supabase is supported as a PostgreSQL
connection target, but no Supabase project, Supabase Auth, or live external service
is configured. A successful local SQLite test run is not evidence that PostgreSQL
is production-ready.

The Phase 1 audit also restricted `APP_ENV` to the documented values
(`development` or `production`) so a typo such as `prod` cannot silently avoid
production configuration checks.

## Project structure and implemented modules

Generated/build/dependency folders such as `.next`, `.next-e2e`, `node_modules`,
and `.venv` are not application source.

| Path | Implemented responsibility |
|---|---|
| `apps/web/app/` | Next.js App Router pages for landing, sign-in, sign-up and dashboard; shared layout; landing, dashboard and global styles. |
| `apps/web/components/` | Marketing page/carousel, API-backed authentication, assistant, order dialogs, integration-status panel, and shared UI components. |
| `apps/web/lib/` | Same-origin API client, pagination, currency/date formatting, and TypeScript API types. |
| `apps/web/tests/` | Playwright marketing/auth route and authenticated business-workflow tests. |
| `apps/web/public/images/` | Local image assets used by the marketing slideshow. |
| `services/api/app/` | FastAPI routes, configuration, SQLAlchemy database setup/models, Pydantic schemas, session/tenant authorization, extraction providers, seed utility and PDF invoices. |
| `services/api/alembic/` | Versioned schema migration and migration environment. |
| `services/api/tests/` | API, authentication, tenant/role, order, extraction/provider, schema, migration, seed, and optional PostgreSQL RLS/concurrency tests. |
| `infra/` | PostgreSQL runtime-role initialization SQL. |
| `compose.yaml`, Dockerfiles | Local container topology for PostgreSQL, migration, API and Next.js. |
| `.github/workflows/ci.yml` | CI definition for PostgreSQL tests, frontend checks/build and Playwright. Remote CI was not run as part of this audit. |
| `docs/` | Architecture, schema, operations, and prior verification record. |

## Feature status

| Area | Status and evidence |
|---|---|
| Landing page and authentication UI | Implemented. Marketing image carousel is functional; sign-in/sign-up pages call the API. E2E tests cover routes, carousel controls and mobile navigation. |
| Authentication | Implemented: Argon2 password hashes, opaque random sessions stored as token hashes, expiry/revocation, and HttpOnly/SameSite cookies. E2E and API tests cover registration/login/logout. |
| Tenant membership and roles | Implemented: each organization selector is checked against live membership; roles restrict write operations; tenant filters, composite foreign keys and PostgreSQL RLS are present. SQLite isolation tests pass; PostgreSQL RLS tests were skipped locally. |
| Customers and products | API-backed create/update/archive and paginated reads; product SKU validation, aliases and server-owned price/stock fields. Browser workflow creates customers/products and changes stock. |
| Inventory | API-backed stock adjustments and stock-movement ledger; negative/oversized stock is rejected. |
| Order assistant | Deterministic local Sinhala/English catalog matching runs without external AI. It stores a draft, not an order. Humans must review and explicitly confirm. |
| Optional OpenAI extraction | Structured outputs, tenant-catalog validation, grounded-unit/delivery fields, safe failure handling and local fallback are implemented and mock-tested. No API key/model is configured and no live provider call or accuracy benchmark was performed. |
| Orders | Server-calculated totals, stale-price checks, idempotency, quota/subscription checks, transactional stock deduction, fulfillment and cancellation/restoration. Browser workflow passes on SQLite. PostgreSQL locking/concurrency tests remain unrun here. |
| Invoices | PDF endpoint and browser download are tested. Sinhala glyph shaping/rendering requires a configured licensed font and has not been visually verified. Tax/VAT compliance is not claimed. |
| Analytics and dashboard | Metrics and activity are read from API data; dashboard includes responsive navigation and theme controls. Business workflow runs through the dashboard in E2E. |
| Integrations and pricing | Incoming WhatsApp webhook foundation, simulator, tenant-scoped inbox, configuration diagnostics and draft review are implemented. Live Meta delivery/outbound messaging remain unconfigured; voice, Tamil and billing are not implemented. Subscription fields do not constitute payment processing. |
| Social profiles | Facebook/Instagram icons are visual indicators only; profile URLs were not supplied, so no destination links are fabricated. |

## Frontend, backend, database and authentication verification

- **Frontend:** Next.js `16.4.2`, React `19.3.1`, TypeScript, Tailwind CSS 4 and
  `lucide-react`. `npm ls --depth=0` found the declared top-level dependencies
  installed with no missing dependency reported. `npm audit` reported **0
  vulnerabilities**.
- **Backend:** FastAPI, SQLAlchemy 2, Pydantic Settings, Alembic, Psycopg 3,
  Argon2, ReportLab and HTTPX. `pip check` reported **no broken requirements**.
- **Local database:** SQLite mode is configured by
  `services/api/.env.example`; the local Alembic revision is `0003 (head)`.
  All three migrations apply and Alembic reports no model/schema drift.
- **PostgreSQL:** PostgreSQL URL support, migration-time RLS setup, tenant-local
  transaction context, FORCE RLS policies and a restricted runtime role are
  implemented. The PostgreSQL tests were skipped because `TEST_POSTGRES_URL` is
  unset. Docker Compose was not run because the Docker CLI is unavailable.
- **Supabase:** Can be used as a PostgreSQL host when configured with a suitable
  direct/session connection and restricted runtime role. It is not a configured
  or verified Supabase deployment. The app uses its own session authentication;
  it does not use Supabase Auth or expose tables through PostgREST.
- **Secrets:** API keys/database credentials are environment configuration, the
  OpenAI key is represented as `SecretStr`, and `.env`/`.env.local` files are
  ignored. No local root/API/frontend environment file was present during the
  audit. The checked-in examples contain placeholders, not usable credentials.

## Audit checks and actual results

| Check | Result |
|---|---|
| `python -m pytest tests -q` in `services/api` | **56 passed, 3 skipped**, 1 non-failing Starlette `TestClient`/HTTPX deprecation warning (latest complete run). |
| `python -m alembic upgrade head` / `current` | **Passed** — local SQLite database is at **`0003 (head)`**. |
| `python -m alembic check` | **Passed** — no new upgrade operations/schema drift. |
| `python -m pip check` | **Passed** — no broken requirements. |
| `npm run lint` | **Passed** — ESLint reports no issues after Phase 3 UI updates. |
| `npm run typecheck` | **Passed** after Phase 3 UI updates. |
| `npm run build` | **Passed** — Next.js production build generated all routes including `/dashboard/inbox`. |
| `npm run test:e2e` with `E2E_BROWSER_CHANNEL=chromium` | **2 passed** after Phase 3 diagnostics UI updates; covers marketing/auth, the inbox diagnostics, and simulator-to-order browser workflow on isolated SQLite. |
| `npm audit` | **0 vulnerabilities** reported for installed frontend dependency tree. |
| Ruff `check app tests` | **Passed**. |
| Prettier check on frontend source/styles/tests | **Passed**. |
| PostgreSQL RLS/concurrency tests | **3 skipped** — no disposable PostgreSQL URL/opt-in was supplied; these are not counted as passed. |
| Docker Compose / container startup | **Not run** — Docker CLI is not installed. |
| Live OpenAI, Supabase, WhatsApp or billing integration | **Not configured/tested**. |

The project virtual environment initially lacked `pip`. It was restored with
`ensurepip`, after which dependency consistency and the API suite passed. This was
an environment/tooling issue, not a missing runtime library in the application.

## Security review observations

### Controls present and locally tested

- Authentication uses Argon2 and opaque random session tokens; only a digest is
  stored in the session table. Cookies are HttpOnly, SameSite strict and Secure
  when `APP_ENV=production`.
- Mutating API requests require the custom `X-OrderMesh` header and matching Origin
  when supplied; cross-site fetch metadata is rejected. No permissive CORS policy
  is installed.
- Organization IDs from the browser are selectors, not proof of access. Each
  tenant request checks membership and role; business queries are tenant-scoped.
- Pydantic schemas reject extra fields and constrain lengths, enum choices,
  quantities, prices and identifiers. Order totals/prices and stock changes are
  checked server-side.
- PostgreSQL migrations enable and force RLS on tenant-owned business and inbox
  tables; runtime startup checks for a non-superuser/non-BYPASSRLS role and
  required RLS in production. These PostgreSQL controls still require execution
  against a disposable PostgreSQL instance before launch.
- Error responses avoid returning database integrity/provider response details.
  SQLAlchemy hides SQL parameters.

### Risks and production gates

1. **PostgreSQL is not locally certified.** Run the PostgreSQL RLS and concurrent
   stock tests against a disposable PostgreSQL 17 database and confirm role grants
   with the actual deployment identity before handling customer data.
2. **Authentication throttling is process-local.** Behind the Next.js proxy,
   requests may share an API source address; the current in-process login/signup
   throttle is not a distributed production control. Add gateway rate limits by
   source and account/organization before public launch.
3. **Self-service registration defaults to enabled.** Set
   `ALLOW_REGISTRATION=false` in production unless onboarding controls are approved.
   Email verification, account recovery, password change, MFA, invitations and
   membership-management UI are not implemented.
4. **Data retention is not automated.** Expired session records and extraction
   source text need an approved retention/deletion policy and scheduled cleanup.
   Audit events are not cryptographically tamper-evident.
5. **External AI requires a privacy decision.** If enabled, order text and active
   tenant product catalog details are sent to the provider. Review data handling,
   spend limits and language accuracy before enabling.
6. **Deployment controls remain necessary.** Production needs HTTPS, private API
   and database networking, managed secrets, request/body limits, monitoring,
   backups and tested restore procedures. No penetration/load test or production
   backup drill was performed.
7. **Python dependency vulnerability scan was not run.** `pip check` validates
   dependency consistency, not known-vulnerability advisories. Run the
   organization-approved Python package audit tool in CI.

The audit rejected unknown `APP_ENV` values instead of allowing a typo such as
`prod` to bypass the production HTTPS/PostgreSQL checks. Regression tests cover the
environment enum and production requirements.

## Exact local startup commands (Windows PowerShell)

Prerequisites: Python 3.13 and Node.js 24. These commands use SQLite and the local
text extractor; no Supabase account or external AI key is needed.

### One-time setup from the repository root

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install -r services\api\requirements.lock
Copy-Item services\api\.env.example services\api\.env
Copy-Item apps\web\.env.example apps\web\.env.local
Set-Location apps\web
npm ci
```

Keep local `.env` files private. If you already have one, do not overwrite it with
the copy command.

### Terminal 1 — API and database migration

From the repository root after setup:

```powershell
Set-Location services\api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The API loads `services/api/.env` relative to this working directory. Local docs
are at `http://127.0.0.1:8000/api/docs`.

### Terminal 2 — Next.js frontend

```powershell
Set-Location apps\web
npm run dev
```

Open `http://localhost:3000`. The browser sends same-origin `/api` requests and
Next.js proxies them to the API. If needed, create a workspace through Sign up.
For a pre-populated development workspace, run the seed utility with an email and
a password you choose from the API directory:

```powershell
..\..\.venv\Scripts\python.exe -m app.seed --email owner@example.com
```

### Local quality checks

```powershell
# Terminal working directory: services\api
..\..\.venv\Scripts\python.exe -m pytest tests -q
..\..\.venv\Scripts\python.exe -m ruff check app tests
..\..\.venv\Scripts\python.exe -m alembic check
..\..\.venv\Scripts\python.exe -m pip check

# Terminal working directory: apps\web
npm run lint
npm run typecheck
npm run build
$env:E2E_BROWSER_CHANNEL = "chromium"
npm run test:e2e
npx prettier --check app components lib tests
```

### Optional PostgreSQL Compose setup (not verified in this audit)

Docker must be installed first. Copy `.env.example` to `.env`, set independent
random `POSTGRES_PASSWORD` and `DB_APP_PASSWORD` values, then run from the root:

```powershell
docker compose up --build
```

The Compose API/database ports are private to the Compose network; the web service
publishes port 3000 on loopback. Do not run PostgreSQL concurrency tests against
production data.

## Recommended next steps

1. Run CI's PostgreSQL 17 migration, RLS isolation and concurrent oversell tests
   against a disposable database; verify the actual restricted runtime role and
   Compose initialization.
2. Configure Meta credentials in a secret manager, a public HTTPS callback and
   a registered real Phone Number ID; verify GET handshake and an inbound message.
3. Add Python dependency vulnerability scanning to CI and resolve the current
   Starlette/HTTPX deprecation on a tested dependency upgrade.
4. Decide onboarding policy and implement approved account recovery/email
   verification, plus invitations/role management if multi-user workspaces are
   needed.
5. Define retention and deletion/export requirements for sessions, drafts and
   customer records; automate cleanup after approval.
6. Complete deployment security, HTTPS/gateway limits, monitoring and backup/
   restore drills before accepting production data.
7. If desired, configure a dedicated Supabase/PostgreSQL staging project using
   migration and runtime roles separately, then evaluate the optional AI adapter
   with approved Sinhala/English samples. Voice, Tamil and billing remain future
   phases.

## Phase 2 implementation update

### Completed in the current implementation

- PostgreSQL connection URLs in `postgres://` and `postgresql://` form are
  normalized to the installed Psycopg 3 driver. Bounded `DB_POOL_SIZE`,
  `DB_MAX_OVERFLOW` and `DB_POOL_TIMEOUT` settings are wired into the engine;
  SQLite behavior remains separate. Production configuration requires PostgreSQL,
  HTTPS and a TLS `sslmode`.
- Added Alembic revision `0002` for tenant-scoped WhatsApp conversations, messages
  and durable webhook queue events, plus a backend-only registered phone-number
  routing table. The three tenant tables have ENABLE/FORCE RLS policies, and
  composite foreign keys constrain messages/drafts/conversations to their tenant.
- Added Meta's standard GET webhook verification contract and POST raw-body
  HMAC-SHA256 validation, bounded payload reading, registered phone ID routing,
  message-ID deduplication, sanitized persistence and retryable processing.
  Incoming text can create an existing `ExtractionDraft` only; it cannot create
  an order.
- Added authenticated inbox conversation/message APIs, read/unread updates and an
  SSE stream that rechecks organization membership. The `/dashboard/inbox` page
  includes phone registration, a synthetic simulator, live updates and draft
  review through the existing `OrderDialog`/human-confirmation path.
- Added ESLint with TypeScript/React Hooks rules, Ruff with import/unused checks,
  and CI lint steps. Existing unused imports/import sorting were corrected; one
  pre-existing invoice lambda was changed to an equivalent local function to
  satisfy Ruff.

### Phase 2 limitations and remaining work

- No PostgreSQL server, Docker, `TEST_POSTGRES_URL` or Supabase credentials were
  available. The migration was verified on an isolated SQLite database, but
  PostgreSQL migrations, RLS for the new tables, pool behavior and concurrency
  have not been run locally. PostgreSQL tests remain skipped and must not be
  counted as passes.
- No Meta App Secret, verification token, WABA/Phone Number ID or public HTTPS
  endpoint was configured. Live webhook verification and real message delivery
  are unverified. The simulator creates synthetic records only.
- Outbound WhatsApp messages, Meta delivery/status callbacks, non-text media
  downloads, consent/opt-out workflows, and retention cleanup are not implemented.
  SSE uses short database polls and is not a substitute for a managed message
  broker at higher scale.
- Inbound text may be sent to OpenAI only if the existing optional provider is
  deliberately configured; default local extraction makes no external calls.
  Review the existing customer-data policy before enabling an external provider.

### Phase 2 local commands and configuration

From the repository root in PowerShell, start the API after installing pinned
requirements and copying `services/api/.env.example` to `services/api/.env`:

```powershell
Set-Location services\api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Start the web app in another terminal:

```powershell
Set-Location apps\web
npm ci
npm run dev
```

Phase 2 API environment variables are `DATABASE_URL`, `DB_POOL_SIZE`,
`DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `WHATSAPP_VERIFY_TOKEN` and
`META_APP_SECRET`. SQLite remains a local option; production PostgreSQL needs
`sslmode=require` or stricter. Keep database URLs and both Meta secrets in the API
environment only. To connect Meta, provision separate migration/runtime database
roles, apply migrations, configure an HTTPS callback at
`https://your-api-host/webhooks/whatsapp`, enter the same verification token in
Meta, subscribe to `messages`, register the real Phone Number ID for its tenant,
and verify a real inbound message end-to-end.

## Phase 3 implementation and external verification status

### Implemented locally

- Alembic uses `MIGRATION_DATABASE_URL` when set and otherwise falls back to the
  runtime URL only outside production. Production requires explicit PostgreSQL
  runtime configuration and an explicit migration URL for Alembic; URL targets
  are checked without logging credentials. Compose migrations use the migration
  identity and the API container uses the restricted app identity.
- Added migration `0003` for optional, human-reviewed delivery instructions on
  orders and invoices. Migration tests apply/rollback all three revisions and
  compare the final SQLite schema against SQLAlchemy metadata.
- PostgreSQL RLS tests now require `TEST_POSTGRES_DISPOSABLE=YES` as well as a
  test URL before they create temporary schemas/roles. Tests run operations under
  an asserted non-superuser, `NOBYPASSRLS` role. They still require a dedicated
  disposable PostgreSQL database with admin permissions and were not executed.
- Added owner/admin-only Inbox diagnostics for database backend/role attributes,
  webhook secret configuration, registered phone count, AI configuration and
  explicit human-confirmation status. No secret values are returned; the panel
  states that diagnostics do not contact providers. SSE connection state is
  shown separately.
- The OpenAI structured output schema accepts a catalog-grounded product,
  quantity, stated unit and source-grounded delivery instruction. Existing
  tenant product IDs are revalidated; foreign/unknown IDs and invalid/unproven
  fields are cleared/flagged. Provider failures fall back to local extraction
  with an `ai_provider_fallback` flag. The order dialog keeps the delivery note
  editable; order confirmation remains explicitly human-approved. Mock
  transport tests verify bearer authentication, schema behavior, and fallback.
- Compose exposes optional AI environment variables to the backend; the default
  remains local/offline. No live AI provider credentials were configured.

### Current verification and limitations

- Latest complete backend result: **56 passed, 3 skipped** with one non-failing
  Starlette/HTTPX deprecation warning. PostgreSQL skips are not passes.
- Focused AI provider tests: **6 passed**. Ruff, ESLint, TypeScript and Prettier
  passed after the related code edits. Final build, full browser tests and fresh
  Alembic upgrade/check are the remaining local verification steps for this
  phase.
- No `TEST_POSTGRES_URL`, Supabase project, Meta App Secret, webhook verify
  token, public HTTPS callback, OpenAI key/model, or live customer message was
  available. No live integration is claimed.
- PostgreSQL RLS/concurrency, Meta inbound delivery and real-model Sinhala/
  English quality must be verified using dedicated development services before
  production. Provider output quality is not guaranteed by schema validation;
  users must inspect flags, units, delivery notes, customer selection and prices.
- Meta outbound messaging, message status callbacks, media, opt-out/consent,
  retention automation and production billing remain out of scope. AI use incurs
  provider token costs and sends customer message text plus active tenant
  catalog details to the selected provider; provider retention and regional
  processing terms need review.

### Environment variables

Backend-only values: `DATABASE_URL` (runtime), optional
`MIGRATION_DATABASE_URL` (Alembic identity), `DB_POOL_SIZE`,
`DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `WHATSAPP_VERIFY_TOKEN`,
`META_APP_SECRET`, `AI_PROVIDER` (`local` by default or `openai`),
`OPENAI_API_KEY` and `OPENAI_MODEL`. Keep credentials in ignored local
environment files or a secret manager, never in the web bundle or source.

### Windows PowerShell startup

Local SQLite (run Alembic/API in one terminal and web in a second; setup requires
the dependency installation documented above):

```powershell
Set-Location services\api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
Set-Location apps\web
npm run dev
```

For Supabase, put the runtime URL in `DATABASE_URL` and a separate schema-owner
URL in `MIGRATION_DATABASE_URL` inside the ignored `services/api/.env`. Use a
dedicated development project, direct/session TLS URLs, `sslmode=require` or
stronger, and a runtime role with `NOSUPERUSER NOBYPASSRLS NOCREATEDB
NOCREATEROLE`. Start the API from `services\api`; `alembic upgrade head`
connects via the migration URL while FastAPI uses the runtime URL. Never point
test commands at production.

To safely run the destructive-to-test-schema PostgreSQL checks, use a disposable
database only, at a PowerShell prompt from `services\api`:

```powershell
$secure = Read-Host "Disposable PostgreSQL test URL" -AsSecureString
$env:TEST_POSTGRES_URL = [System.Net.NetworkCredential]::new("", $secure).Password
$env:TEST_POSTGRES_DISPOSABLE = "YES"
..\..\.venv\Scripts\python.exe -m pytest tests\test_postgres.py -q
Remove-Item Env:\TEST_POSTGRES_URL
Remove-Item Env:\TEST_POSTGRES_DISPOSABLE
```

### Meta setup and genuine end-to-end acceptance

1. Create/configure a Meta developer app with the WhatsApp product and a
   development/test number. Follow Meta's test recipient allow-list and
   verification steps.
2. Expose the API webhook over public HTTPS at
   `https://<api-host>/webhooks/whatsapp`. Enter that callback and a random
   verification token in Meta's webhook configuration, subscribe to `messages`,
   then set the same token as `WHATSAPP_VERIFY_TOKEN` and the Meta App Secret as
   `META_APP_SECRET` in the API's secret environment. Restart the API and verify
   Meta's GET handshake succeeds.
3. In the authenticated Inbox, register the Meta test `phone_number_id` under
   the intended development organization. Diagnostics only report that secrets
   are set; they do not prove a Meta connection.
4. Send a real message from an allow-listed recipient. Confirm one authentic
   message appears in PostgreSQL and Inbox, SSE updates, AI/local extraction
   creates only a draft, a human edits and confirms the draft, stock changes
   once, and an invoice downloads. Correlate the external message ID and order
   ID without logging message contents or secrets.
5. Report the real test separately from synthetic webhook-signature, simulator,
   local provider-mock, and SQLite checks. Live success requires this complete
   sequence; none has been executed yet.

## Meta WhatsApp Cloud API test sender — implementation update

**Updated:** 23 October 2026. This section supersedes the earlier WhatsApp
implementation status above; it does not supersede the external-service
verification limits.

- Implemented a server-only Cloud API text sender using the configured Graph API
  version, bounded HTTP timeouts, safe provider errors, and no credential or
  provider-payload logging.
- Added authenticated, tenant-scoped replies limited to the configured registered
  phone number. Test mode is enabled by default and fails closed unless the
  recipient is in the normalized E.164 allowlist. Free text requires an inbound
  message within the previous 24 hours; templates are not implemented.
- Extended signed webhook processing to update matching outbound delivery states
  monotonically and idempotently, including failed status details. The inbox now
  shows outbound statuses and identifies simulator messages as synthetic.
- Added reversible Alembic revision `0004` for delivery status, error details and
  request idempotency. **Revision `0004` has not been applied to Supabase or any
  configured database.** Review it before applying it in a development environment.
- **Backend:** `pytest tests -q` — **61 passed, 3 skipped**. The skipped tests are
  the opt-in PostgreSQL tests; `TEST_POSTGRES_URL` was not configured. WhatsApp
  send requests use an in-process mocked HTTP transport. Migration upgrade/
  downgrade comparison ran only against temporary SQLite within the unit test.
- **Backend lint:** `ruff check app tests` — passed.
- **Frontend:** ESLint, TypeScript typecheck and Next.js production build — passed.
- No live Meta API request, Supabase connection, PostgreSQL migration, or
  end-to-end WhatsApp test-number message was performed. Live integration remains
  unverified until the Meta Dashboard/webhook and API secrets are configured and
  an approved test recipient completes the real inbound/reply/status flow.

Required API-only configuration names: `WHATSAPP_ACCESS_TOKEN`,
`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_GRAPH_API_VERSION`,
`WHATSAPP_ALLOWED_TEST_RECIPIENTS`, `WHATSAPP_TEST_MODE`,
`WHATSAPP_VERIFY_TOKEN`, and `META_APP_SECRET`.

