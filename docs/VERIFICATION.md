# Verification record

Verified locally on 23 October 2026 using Python 3.13.12, Node.js 24.13.0,
Next.js 16.4.2 and installed Chrome on Windows.

| Check | Result |
|---|---|
| API/unit/security/provider/migration/sample-data suite | **36 passed** |
| PostgreSQL RLS and concurrency tests | **2 skipped** — no PostgreSQL server or Docker installed |
| Alembic upgrade on local SQLite | Passed |
| Immutable migration upgrade/downgrade and model comparison | Passed in automated tests |
| `alembic check` | Passed — no schema drift |
| TypeScript typecheck | Passed |
| Next.js production build | Passed |
| Playwright real-browser workflow | **1 passed**, desktop and 390px mobile |
| npm dependency install audit | 0 vulnerabilities reported at installation |
| Live external model, Supabase, WhatsApp or billing | Not configured; no live calls made |
| Docker Compose / Linux container build | Not run — Docker unavailable |
| Sinhala PDF typography | Not verified; requires configured font and visual acceptance |

The API tests cover authentication, cookie flags, session hash storage and revocation,
CSRF/origin guards, throttling, live role/membership checks, cross-tenant reads/writes,
foreign-key and stock constraints, catalog validation, order idempotency, cancellation,
stock rollback, quota/subscription enforcement, explicit human confirmation, stale
prices, extraction flags, unsupported adapters, model refusals/malformed output,
foreign model product IDs, PDF signatures, analytics, migration round trips, seed
non-overwrite behavior and timezone conversion.

The browser test registers a new organization, adds a customer and product, records
stock, extracts Sinhala text, checks that confirmation starts disabled, acknowledges
flags, confirms the order, downloads an invoice, fulfills it, checks the mobile layout,
verifies remaining stock and signs out. It uses a fresh isolated SQLite database and
synthetic records. Test servers are stopped by Playwright afterward.

During QA, fixes included explicit form-label associations, mobile grid minimum widths,
off-canvas navigation visibility, and positioning the table's screen-reader label inside
its scroll container. Earlier failures were rerun successfully after correction.

One dependency deprecation warning remains: Starlette's TestClient warns that its
httpx integration will migrate to httpx2. It does not fail current tests. Browser
runner color-environment warnings are also non-failing.

CI provisions a disposable PostgreSQL 17 service, runs migrations and the two database
tests, then typecheck/build/Playwright. The workflow has been authored but **not run
on a remote CI service**. Passing SQLite tests does not certify PostgreSQL RLS or
concurrent stock behavior. Run CI or the documented PostgreSQL test command before launch.

Tests are regression evidence, not a penetration test, load test or Sinhala language
accuracy benchmark. See [operations and release gates](OPERATIONS.md).
