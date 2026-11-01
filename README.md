# OrderMesh AI Lite

A tenant-aware business operations application for **Qubriant Technologies**.
Next.js + TypeScript + Tailwind, FastAPI + Python, SQLAlchemy + PostgreSQL/Supabase.
Local SQLite mode works without external accounts. Default extraction is offline.

Start with [architecture and implementation roadmap](docs/ARCHITECTURE.md),
[database schema](docs/SCHEMA.md), and [operations](docs/OPERATIONS.md).

Browser-verified screenshots: [desktop overview](docs/screenshots/dashboard-desktop.png)
and [mobile inventory](docs/screenshots/dashboard-mobile.png).

## Current restoration status

The original green/white dashboard and the later business-profile, non-stock service,
message-category and LKR 7,400/month / 15-day trial requirements are implemented.
PayHere checkout/renewal/cancellation has provider-mocked tests and requires live
configuration. See [current verification](docs/LOCAL_SETUP_STATUS.md) and the
[ordered restoration checklist](docs/FEATURE_RESTORE_CHECKLIST.md).

## Phase 1 delivered

- Responsive dashboard, seven-day order-value chart, customers, inventory, stock watch and audit activity.
- Argon2 password hashing, HttpOnly session cookies, logout revocation, organization membership and role enforcement.
- Customer/product create, edit and archive; stock adjustments with a ledger.
- Atomic order confirmation, server pricing, stale-price rejection, stock deduction,
  idempotency, fulfillment and cancellation with stock restoration.
- Downloadable PDF invoices with immutable line/customer snapshots; LKR integer minor units.
- Sinhala/English text extraction into typed JSON, unresolved-line/confidence flags,
  editable review and **mandatory human confirmation**. No extraction creates an order.
- Offline rules fallback plus an opt-in OpenAI structured-output adapter. Mocked tests
  validate provider output and safe fallback; no live model call has been verified.
  Model output is revalidated against the requesting tenant's catalog.
- Tenant-scoped queries, composite foreign keys and PostgreSQL FORCE RLS; subscription
  state and monthly order allowance enforcement. PayHere billing is implemented; live credentials and gateway verification are required.
- PostgreSQL/Supabase URL normalization to Psycopg 3 with bounded server-side connection pooling;
  separate `MIGRATION_DATABASE_URL` and runtime `DATABASE_URL` settings are supported;
  SQLite remains available for local development. Production requires an explicit
  PostgreSQL/TLS URL; production Alembic runs require a separate migration URL,
  and mismatched runtime/migration targets are rejected.
- Official WhatsApp webhook foundation: raw-body Meta HMAC verification, tenant phone-number
  routing, deduplicated database persistence, a retryable processing queue, synthetic simulator,
  tenant-scoped inbox APIs and authenticated SSE updates. Sender identity is matched only by an
  exact international customer number; unassigned senders require an explicit team-member link.
- WhatsApp text messages can create extraction drafts only. Every order still uses the existing
  product/customer review and explicit human-confirmation flow.
- Alembic migrations, opt-in sample workspace, tests, CI, Dockerfiles and environment examples.

The backend supports a server-configured single-number Meta Cloud API test sender,
allowlisted recipients, authenticated inbox replies within WhatsApp's 24-hour
customer-service window, and delivery-status callbacks. Live Meta delivery and
Supabase PostgreSQL remain **unconfigured and unverified**. The simulator uses
synthetic local messages; it does not send through Meta. Tamil extraction and voice
notes remain unsupported. There are no fake successful integration calls.

## Start the configured local workspace

After completing setup, run `.\Start-OrderMesh.ps1` from the repository root
It runs pending migrations, starts the API and web
app in the background, and verifies both the sign-in page and API proxy. Open
**http://localhost:3000/sign-in**. Logs are in `.local/`.

After editing `services/api/.env`, run `.\Start-OrderMesh.ps1 -Restart` to reload
configuration. The launcher restarts only the processes it previously recorded.
It uses existing data and does not seed a sample account.

See [current local verification and remaining setup](docs/LOCAL_SETUP_STATUS.md).

## Local setup (Windows PowerShell)

Prerequisites: Python 3.13 and Node.js 24. Commands start at the repository root.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services\api\requirements.lock
Copy-Item services\api\.env.example services\api\.env
Copy-Item apps\web\.env.example apps\web\.env.local
Set-Location services\api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
# Optional: prompts for a password you choose; no default credentials.
..\..\.venv\Scripts\python.exe -m app.seed --email owner@example.com
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal at the repository root:

```powershell
Set-Location apps\web
npm ci
npm run dev
```

Open **http://localhost:3000**. Use the sample account you created or choose
**Create an account** to initialize an empty private workspace.
Use `localhost`, matching `APP_ORIGIN`; `127.0.0.1` is a different origin.
Development API documentation: http://127.0.0.1:8000/api/docs.

### Google sign-in

Google sign-in uses this API's existing database-backed session, not Supabase Auth.
Create a **Web application** OAuth client in Google Cloud and configure its exact
authorized redirect URI as `http://localhost:3000/api/auth/google/callback` for
local development. Add the client credentials only to `services/api/.env`:

```dotenv
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:3000/api/auth/google/callback
```

For production, use an HTTPS `APP_ORIGIN` and the matching HTTPS callback URI.
The callback verifies Google profile data server-side, requires a verified email,
and then issues the same OrderMesh HttpOnly session as password sign-in. New Google
users complete the business-name step after returning from Google. Do not put the
client secret in the Next.js environment.

The inbox is at **http://localhost:3000/dashboard/inbox**. An owner/admin can register
a Meta Phone Number ID there and exercise the inbox with a synthetic message. For real
Meta webhook verification and message ingestion, set `WHATSAPP_VERIFY_TOKEN` and
`META_APP_SECRET` in `services/api/.env`, make the API reachable at an HTTPS URL, and
configure Meta's callback as `https://your-api-host/webhooks/whatsapp` with the same
verification token and subscribed `messages` field. Keep both secrets exclusively on
the API. Meta verification uses its standard `hub.mode`, `hub.verify_token`, and
`hub.challenge` query parameters; incoming POST signatures are checked against the
exact raw request body. To enable test replies, also set `WHATSAPP_ACCESS_TOKEN`,
`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_GRAPH_API_VERSION`,
`WHATSAPP_ALLOWED_TEST_RECIPIENTS` (comma-separated international E.164 recipients)
and `WHATSAPP_TEST_MODE=true` in the API environment. Add only Meta-approved test
recipients and register the same sender ID to the development workspace. Free-text
replies are blocked outside the 24-hour customer-service window; template sending is
not implemented. Subscribe to Meta's WhatsApp messages webhook field to receive
both inbound-message and delivery-status events. Never put Meta credentials in the
Next.js/browser environment, and do not claim live messaging until a real end-to-end
test succeeds.

## Local demo setup (isolated sample data)

For a demo, use a dedicated local SQLite database and synthetic WhatsApp messages.
This keeps demo data separate from Supabase. The sample seeder refuses non-SQLite
databases. The following configuration selects local extraction and disables the
WhatsApp sender; it uses no real Meta or OpenAI credentials.

```powershell
# Terminal 1 — run from the repository root
Set-Location services\api
$env:APP_ENV = "development"
$env:APP_ORIGIN = "http://localhost:3000"
$env:DATABASE_URL = "sqlite:///./ordermesh-demo.db"
$env:MIGRATION_DATABASE_URL = "sqlite:///./ordermesh-demo.db"
$env:DATABASE_TARGET_ID = "local-demo"
$env:MIGRATION_DATABASE_TARGET_ID = "local-demo"
$env:AI_PROVIDER = "local"
$env:OPENAI_API_KEY = "local-demo-disabled"
$env:OPENAI_MODEL = "local-demo-disabled"
$env:WHATSAPP_VERIFY_TOKEN = "local-demo-disabled"
$env:META_APP_SECRET = "local-demo-disabled"
$env:WHATSAPP_ACCESS_TOKEN = "local-demo-disabled"
$env:WHATSAPP_PHONE_NUMBER_ID = "local-demo-disabled"
$env:WHATSAPP_GRAPH_API_VERSION = "disabled"
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m app.seed --email demo@example.com
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The seed command prompts for a demo password. Choose a temporary password with at
least 12 characters; do not reuse a real account password. Keep Terminal 1 running.
In a second PowerShell terminal:

```powershell
Set-Location apps\web
$env:API_BASE_URL = "http://127.0.0.1:8000"
$env:NEXT_TELEMETRY_DISABLED = "1"
npm run dev
```

Open **http://localhost:3000** and sign in with the email and temporary password
you chose. The seeded workspace has sample customers, products, inventory and
historical orders. Suggested flow: dashboard/low-stock items → review a Sinhala
or English extraction draft → explicitly confirm the order → download its invoice
→ open WhatsApp Inbox and use the simulator. Simulator messages are synthetic and
marked as such. The disabled sender settings prevent real WhatsApp requests.
The SQLite file is `services\api\ordermesh-demo.db` and is ignored by Git. Stop the
API with Ctrl+C. To reset this dedicated demo database, stop the API and remove
only that exact file; do not remove or overwrite another database.

To route a conversation to the right customer, add that customer with their international
number (for example `+94770001122`) before the message arrives. If there is exactly one
matching active customer, OrderMesh links the thread automatically. Otherwise it shows
**Needs customer link** in Inbox; a staff member selects the customer once, and the sender's
WhatsApp identity is saved for future messages. Profile names received from WhatsApp are never
used to select a customer.

If a restricted Windows environment blocks `ensurepip`, an existing host pip can
bootstrap the venv with:

```powershell
python -m pip --python .venv\Scripts\python.exe install -r services\api\requirements.lock
```

On Linux/macOS use `.venv/bin/python` instead of `.venv/Scripts/python`, `cp` for
`Copy-Item`, and `cd` for `Set-Location`. Run Alembic and Uvicorn from `services/api`.
The API reads `.env` in its current working directory. Next.js reads `apps/web/.env.local`.

## Walk through the working flow

1. Add a customer. Add a product with an integer unit (bags, packs, bottles, units).
2. Add English/Sinhala aliases, then use **Adjust stock** to record opening stock.
3. In **Order assistant**, paste one product and numeric quantity per line:

   ```text
   Rice 2
   සීනි 3
   ```

4. Review matched and unmatched lines. Select the customer, resolve or remove
   unmatched products, verify units, acknowledge flags and check confirmation.
5. Create the order, download its invoice, then fulfill or cancel it from **Orders**.

The sample seed includes aliases for the example above. The baseline supports
numeric integer quantities and known aliases; it does not understand arbitrary prose,
spoken numbers, unit conversions, or all Sinhala grammar. Low confidence is a signal
to correct the draft, never permission to create an order automatically.

## PostgreSQL with Docker Compose

Docker is optional for local development but was **not available on the implementation
machine**. The Compose configuration has not been run locally.

1. Copy root `.env.example` to root `.env`.
2. Generate two independent passwords, for example with
   `python -c "import secrets; print(secrets.token_hex(32))"`. Put them in
   `POSTGRES_PASSWORD` and `DB_APP_PASSWORD`. Use hex to avoid URL-escaping issues.
3. Run `docker compose up --build`.
4. Open http://localhost:3000 and register. To add sample data interactively:
   `docker compose exec api python -m app.seed --email owner@example.com`.

Compose initializes a limited runtime role, runs migrations with a separate admin
connection, and keeps the database and API off published host ports. The web port
binds to loopback. Initialization SQL runs only for a new volume; changing environment
passwords does not rotate passwords in an existing volume. Do not delete a data volume
to rotate credentials. See the operations guide for production deployment.

## Optional AI model

Default `AI_PROVIDER=local` makes no network requests. To opt into model extraction,
set these server-only values in `services/api/.env` and restart the API:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=
OPENAI_MODEL=
```

Supply your own key and a model available to your account that supports Responses
API structured outputs. No model is silently selected. In model mode, the submitted
message and active tenant catalog identifiers/names/aliases/units are sent to OpenAI;
customer records, passwords, stock and prices are not included separately. The message
itself may contain personal data. Enable only after choosing the appropriate data policy.
Requests use `store=false`, a timeout, output limits and a strict JSON schema.
Refusals, timeouts, incomplete or malformed output fail closed. No silent local fallback.
Tests mock the HTTP transport; credentials, provider access and language accuracy
must be validated before launch. See [official structured-output documentation](https://developers.openai.com/api/docs/guides/structured-outputs).

## Tests and build

From `services/api`:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests -q
..\..\.venv\Scripts\python.exe -m alembic check
..\..\.venv\Scripts\python.exe -m ruff check app tests
```

PostgreSQL isolation/concurrency tests run when `TEST_POSTGRES_URL` points to a
**disposable PostgreSQL test database** with a test admin able to create roles.
They create and clean a random schema and role; never use a production database.
Without the variable, those tests are explicitly skipped. CI provisions PostgreSQL.

From `apps/web`:

```powershell
npm run lint
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

If Chrome is already installed, use `$env:E2E_BROWSER_CHANNEL='chrome'` before
`npm run test:e2e` instead of installing Chromium. Tests start isolated API and frontend
servers on ports 8100/3100, migrate a unique SQLite DB under `.e2e/`, and shut the servers
down afterward. No real workspace data is used. Screenshots and failure traces go to
`apps/web/test-results/`. `PYTHON` can override the test Python executable.

For a local production frontend build: `npm run build`, then `npm start`. The API
must still be running. `API_BASE_URL` is embedded in the proxy rewrite during build;
rebuild when its destination changes. `APP_ENV=production` is a separate API setting
that requires PostgreSQL, HTTPS and a restricted database role.

See [verification results](docs/VERIFICATION.md) for completed checks and limits.

## Scope and launch gates

This is a production-oriented foundation, **not a production certification**.
Before launch, complete PostgreSQL tests, verify a Supabase/PostgreSQL deployment,
configure and verify real Meta webhook delivery, complete deployment security review, backup/restore
drills, HTTPS/gateway rate limits, account recovery and verified onboarding. Invitations,
password recovery, MFA, payments, returns, taxes, multi-warehouse stock, template-based WhatsApp messages and live external-channel
connections are roadmap work. PDF exports use Latin fonts by default; Unicode
exports require `INVOICE_FONT_PATH`, and Sinhala shaping needs visual acceptance testing.
SQLite is not suitable for concurrent production order processing.
