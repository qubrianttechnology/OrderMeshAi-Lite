# Operations and deployment

## Environments

- **Development:** SQLite or PostgreSQL, localhost HTTP, configurable registration,
  local extraction. SQLite does not provide the PostgreSQL row-lock guarantee.
- **Staging:** PostgreSQL, separate migration/runtime credentials, HTTPS,
  synthetic test data, browser tests plus PostgreSQL isolation/concurrency tests.
- **Production:** same staging topology with managed secrets, backups, a reverse proxy,
  restricted network access and monitored operations. Set `APP_ENV=production`,
  `APP_ORIGIN=https://your-domain`, `ALLOW_REGISTRATION=false` unless onboarding
  controls have been completed. API startup rejects SQLite, insecure origin,
  superuser/BYPASSRLS connections and missing FORCE RLS policies on the ten
  tenant-owned business tables.

Next.js receives only a server-side `API_BASE_URL`. Its `/api/*` rewrite forwards the
cookie and tenant selector. FastAPI accepts mutations only with `X-OrderMesh: 1` and
a matching Origin when present; cross-site fetch metadata is rejected. No permissive
CORS policy is installed. Keep the backend private in production. Set a 64 KiB HTTP
body limit and appropriate timeouts at the ingress. Limit requests per authenticated
user/organization and per source IP at the gateway. The in-process auth throttle is
only a baseline; behind the Next.js proxy its client address may be shared, so do not
rely on it as the production rate-limit strategy.

## PostgreSQL / Supabase provisioning

1. Create a dedicated database/project. Do not reuse a production project for tests.
2. Run the migration using a migration account with schema ownership.
3. Create a separate `ordermesh_app` login with NOSUPERUSER, NOBYPASSRLS,
   NOCREATEDB and NOCREATEROLE. Assign its password via your secret-management flow.
4. Grant CONNECT on the target database, USAGE on `public`, and
   SELECT/INSERT/UPDATE/DELETE on the application's tables. Runtime does not need
   CREATE, TRUNCATE, REFERENCES, schema ownership or access to `alembic_version`.
5. Confirm all ten tenant-owned business tables have ENABLE and FORCE RLS. Confirm
   browser roles `anon`, `authenticated` and PUBLIC have no privileges on auth,
   routing or business tables. Do not expose these tables through Supabase
   PostgREST/GraphQL. The application uses custom session auth, not Supabase Auth;
   do not mix token systems.
6. Configure `DATABASE_URL=postgresql+psycopg://...` with the runtime account and
   TLS (`sslmode=require` or a stricter certificate-verifying configuration).
   URL-encode credentials. Do not use the database-owner or Supabase service role
   as the application runtime identity. Set `MIGRATION_DATABASE_URL` separately
   to the migration-only owner connection when running Alembic. In production,
   Alembic requires this separate URL; it never falls back to the runtime role.
   The migration job may set its `DATABASE_URL` to the migration URL as well;
   do not inject the runtime credential into a privileged migration job merely
   for comparison. When both URLs are available, credentials may differ but the
   backend checks that they target the same database. If runtime and migration
   endpoints differ (such as a Supabase pooler and direct endpoint), provide
   `DATABASE_TARGET_ID` and `MIGRATION_DATABASE_TARGET_ID` from the same
   non-secret project/environment configuration. The backend rejects mismatched
   backends, database names, endpoint mismatches without matching target labels,
   and disagreeing labels. It does not log URLs or credentials.
7. Tune `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` and `DB_POOL_TIMEOUT` to the runtime
   connection limit. Psycopg automatic prepared statements are disabled to support
   transaction-pooling proxies. Migrations should use a direct/session-pool URL.
8. Start the API, verify health and role checks, then deploy the Next.js build.

Prefer a direct/session-pool connection for migrations. Transaction-pool suitability
must be verified with your provider. Tenant context uses transaction-local
`set_config`; it is never stored as global connection state. All business access
goes through membership authorization before that context is set.

### Supabase development setup and verification (Windows PowerShell)

1. Create a **new development-only Supabase project**. Never run migrations or
   tests against production. Record its region and PostgreSQL settings from
   Supabase **Connect**.
2. Create distinct migration and runtime logins. The runtime role must be
   `NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE`; grant it database connect,
   schema usage and table DML only. Keep both URLs in the ignored
   `services/api/.env`; do not paste credentials into chat, source, screenshots
   or logs. Do not expose application tables through PostgREST. The app continues
   using its own session cookies, not Supabase Auth.
3. Use direct/session-pool TLS connections for migrations with
   `sslmode=require` or stronger. Set `MIGRATION_DATABASE_URL` to the migration
   identity. The API receives only the runtime `DATABASE_URL`; the isolated
   migration job can set both URL variables to the migration URL so it never
   receives runtime credentials. For differing runtime/migration endpoints,
   provide matching `DATABASE_TARGET_ID` and `MIGRATION_DATABASE_TARGET_ID`
   labels from the same deployment configuration. Do not use a transaction pool
   URL for migrations.
4. From `services\api`, run
   `..\..\.venv\Scripts\python.exe -m alembic upgrade head` and then
   `..\..\.venv\Scripts\python.exe -m alembic current`.
5. PostgreSQL integration tests create/drop a random test schema and role. Run
   them only against a separate disposable database using a test admin that can
   create roles. The URL is entered as a hidden PowerShell prompt and is not
   saved into repository files:

   ```powershell
   $secure = Read-Host "Disposable PostgreSQL test URL" -AsSecureString
   $env:TEST_POSTGRES_URL = [System.Net.NetworkCredential]::new("", $secure).Password
   $env:TEST_POSTGRES_DISPOSABLE = "YES"
   ..\..\.venv\Scripts\python.exe -m pytest tests\test_postgres.py -q
   Remove-Item Env:\TEST_POSTGRES_URL
   Remove-Item Env:\TEST_POSTGRES_DISPOSABLE
   ```

   The explicit safety flag is mandatory. Never set it for production or any
   database containing customer data. Tests assert the assumed runtime role is
   neither superuser nor RLS-bypass.

## Release procedure

1. Run API tests, PostgreSQL tests, migration/model comparison, frontend typecheck,
   production build and browser workflow tests in staging.
2. Take a backup and verify a recent restore. Review migration changes separately.
3. Run migrations once using migration credentials, then deploy API and frontend.
4. Confirm sign-in, organization isolation, draft extraction without an order,
   human confirmation, stock deduction, fulfillment, cancellation and PDF download.
5. Monitor error rate, authentication failures, latency, DB connections, stock
   conflicts, provider failures and quota rejections. Never log passwords, cookies,
   provider keys or raw customer messages. SQLAlchemy hides query parameters.
6. Roll back application artifacts only if compatible with the schema. The initial
   migration's downgrade drops tables; do not use it as a production rollback.

## Data handling and invoices

Back up PostgreSQL regularly, encrypt backups, restrict access, and rehearse restore
to an isolated environment. Retention periods and customer deletion/export workflows
must be decided before live customer data is collected. Expired sessions and old
extraction source text need a scheduled retention job; no job scheduler is installed.
Audits identify action, entity and actor, but are not cryptographically tamper-evident.

PDF invoices snapshot customer name/address and line names/prices. The invoice
identifier is the UUID order ID. No VAT/SVAT/tax calculation or legal invoice compliance
is claimed. Sinhala/English/Tamil invoices use the bundled Noto Sans Sinhala and Tamil fonts (SIL
Open Font License, included in `app/fonts/OFL.txt` and `app/fonts/OFL-Tamil.txt`) and HarfBuzz shaping. No local
font installation or environment setting is required. `INVOICE_FONT_PATH` optionally
overrides the bundled font; the file must exist and cover every printable character
in customer names, addresses, product names and delivery instructions. Unsupported
characters fail explicitly rather than printing missing-glyph boxes. Automated tests
cover Sinhala PDF generation, embedded fonts, wrapping and unsupported characters.

## External integrations

No keys are committed. AI is off by default. If enabled, choose a structured-output
capable model, review privacy/cost controls, set provider-side spend limits, evaluate
Sinhala/English samples, then enable in staging. The adapter sends `store=false`;
this is not a claim of zero provider retention. Document your account's applicable
data controls. Limit concurrent extraction requests at the gateway.

For a live AI trial, set `AI_PROVIDER=openai`, `OPENAI_API_KEY` and
`OPENAI_MODEL` only in the API environment/secret manager, then restart the API.
Provider failures fall back to local rules and add an `ai_provider_fallback`
draft flag. Mocked provider tests and this fallback are not proof of a live
provider request. Review customer-data and provider retention terms before
enabling. Human review remains mandatory.

### WhatsApp Cloud API foundation

The API accepts Meta webhook verification on `GET /webhooks/whatsapp` and signed
events on `POST /webhooks/whatsapp`. Configure `WHATSAPP_VERIFY_TOKEN` and
`META_APP_SECRET` only in the API environment. GET verification follows Meta's
standard `hub.mode`, `hub.verify_token` and `hub.challenge` contract. POST uses
HMAC-SHA256 over the unmodified raw request body, a one-megabyte input limit,
message-ID deduplication and a database-backed retry queue. The backend maps the
Meta `phone_number_id` to an owner/admin-registered organization. Text messages
may create extraction drafts; orders are never created without the existing
human-review and confirmation flow. Inbox updates use authenticated SSE and
recheck organization membership while the stream is open.

Customer routing uses the WhatsApp sender's normalized international number, never
the mutable WhatsApp profile name. A single exact active `customers.phone` match is
accepted on arrival; otherwise the thread remains unassigned. In Inbox, an authorized
team member can link the sender to the correct customer once. That creates a
tenant-unique saved WhatsApp identity, so later messages from that sender route to the
same customer. An ambiguous number is deliberately left unassigned.

At `/dashboard/inbox`, owners/admins register the Meta phone-number identifier.
Team members can use the simulator to persist synthetic test messages and exercise
draft review without a live Meta account. Simulator messages do not go to WhatsApp.

Live Meta delivery is **not configured or verified**. The backend supports a
single configured Cloud API sender, allowlisted test recipients, authenticated
tenant-scoped replies, the 24-hour free-text window, signed inbound webhook
processing, and idempotent/monotonic delivery-status updates. Template messages,
consent/opt-out workflows, media downloads and retention automation are not
implemented. Never claim live messaging until end-to-end verification succeeds.

For a Meta test number, create a Meta developer app with the WhatsApp product,
complete the dashboard's test-number recipient allow-list/verification steps,
then configure a public HTTPS callback at `https://your-api-host/webhooks/whatsapp`.
In the Meta App Dashboard, choose WhatsApp > Configuration > Webhooks, enter the
callback and verification token, and subscribe to the WhatsApp messages field.
Set `WHATSAPP_VERIFY_TOKEN`, `META_APP_SECRET`, `WHATSAPP_ACCESS_TOKEN`,
`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_GRAPH_API_VERSION`,
`WHATSAPP_ALLOWED_TEST_RECIPIENTS` and `WHATSAPP_TEST_MODE=true` only in the API
secret environment. Format allowed recipients as international E.164 numbers,
restart the API, and register the same phone-number ID to the development workspace.
Meta access tokens and app secrets must never reach the browser.

From the authenticated Inbox, send only to an allow-listed recipient who has
messaged within the previous 24 hours. Outside that window, an approved message
template is required, but template sending is not implemented. Verify inbound
persistence and status updates, human-reviewed extraction drafts and replies using
a real test recipient. Synthetic tests and the simulator do not prove live Meta
connectivity.

Tamil extraction and voice are unsupported. Do not route messages to order creation
directly; persist drafts for human review.

Billing fields enforce allowance/subscription state but do not take payment. Future
billing requires signed, idempotent webhooks and server-only plan changes. No public
endpoint permits users to increase their allowance or activate a subscription.

## Remaining product boundaries

Verified invitations, email verification, account recovery, password change, MFA and
membership management UI are not implemented. Public signup creates a new isolated
organization only. There are no purchase orders, returns, delivery tracking,
multi-warehouse reservations, payment reconciliation or fractional-unit conversions.
Catalog and order list endpoints paginate; the Phase 1 UI retrieves pages into memory,
so server-side interactive search should precede large-scale catalog deployment.
