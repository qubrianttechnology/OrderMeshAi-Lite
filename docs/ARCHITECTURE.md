# OrderMesh AI Lite — Phase 1 architecture

Qubriant Technologies · Sri Lankan wholesale operations · LKR · Asia/Colombo

## Runtime and trust boundaries

Next.js App Router + TypeScript + Tailwind provides a responsive operations console.
Same-origin `/api/*` requests proxy to FastAPI. Only FastAPI talks to PostgreSQL
(a Supabase PostgreSQL connection is also supported; Supabase Auth is not used).
No database credentials or session tokens are exposed to browser JavaScript.
Local development can use SQLite, but production requires PostgreSQL.

Authentication uses Argon2 hashes and opaque, expiring, revocable sessions stored
as SHA-256 hashes. HttpOnly/SameSite cookies and a required custom write header
with Origin validation protect mutations. Registration creates an organization and
owner atomically. Every tenant request verifies live membership; organization IDs
from the browser are selectors, never authorization. Owner/admin manage catalog
and stock; staff also create/process orders; viewers only read. Public registration
is configurable. Account recovery, email verification, invitations and MFA are later
work; do not deploy public self-service onboarding until that work is approved.

SQLAlchemy queries explicitly filter organization ID. Composite foreign keys prevent
cross-tenant relationships. PostgreSQL adds FORCE RLS on business tables using a
transaction-local tenant context set only after membership verification. Deploy with
a non-superuser/non-BYPASSRLS runtime role; migration credentials are separate.
Auth/membership tables are private backend-only tables, never exposed via PostgREST.

## Schema

`users → sessions`; `users ↔ memberships ↔ organizations`.
`organizations → customers, products, orders, extraction_drafts, stock_movements,
audit_events`. `orders → order_lines`. Organizations carry plan, subscription state
and monthly order limits. Billing is not activated; limits are enforced server-side.
Products contain on-hand stock, aliases, SKU, unit, reorder point and integer LKR
minor-unit pricing. Orders snapshot customer name and line names/prices. Totals
are calculated by the server. Stock is deducted at confirmation and restored once
on cancellation. Fulfillment is terminal. No tax compliance claims are made.

Orders and stock adjustments lock the organization then products in a deterministic
order. Quota, stock, lines, draft confirmation and audit events commit atomically.
An organization-scoped idempotency key prevents duplicate submissions; reusing a
key with different content returns a conflict. Order states: confirmed → fulfilled
or cancelled. Referenced master records are archived rather than deleted.

## Extraction and confirmation

Phase 1 ships an honest deterministic Sinhala/English text baseline, requiring no
external AI credentials. It recognizes catalog names/aliases and numeric quantities
in one item per line. It returns typed JSON, heuristic confidence, source text and
validation flags. It is NOT an LLM and confidence is not calibrated probability.
Unknown/ambiguous lines remain visible; no guessing product IDs or prices. A provider
protocol includes an opt-in OpenAI Responses structured-output adapter; generated
content always remains untrusted input. Local mode makes no external calls. The
adapter is transport-mock tested, not live-credential tested. Refusals, incomplete
responses and invalid output fail closed. Tenant product IDs are revalidated and
names come from the catalog, never model output. Tamil, audio and WhatsApp adapters
return explicit unsupported errors.

Extraction persists a tenant-owned draft; it never writes an order. The review UI
requires a customer, editable validated lines, explicit acknowledgement of flags and
a human confirmation checkbox. The order endpoint independently enforces confirmation,
draft ownership, active products, quantities, prices, stock and duplicate prevention.
No automated webhook can bypass this boundary in Phase 1.

## Repository

```text
apps/web/              Next.js dashboard and same-origin API proxy
services/api/app/     FastAPI auth, models, services, extraction and invoices
services/api/alembic/ Versioned schema and PostgreSQL RLS migration
services/api/tests/   API, authorization, workflow and extraction regression tests
docs/                 Architecture, rollout and operational guidance
.github/workflows/    Repeatable CI including PostgreSQL integration tests
```

## Implementation sequence and acceptance

1. Foundation: schema, migration, configuration; test constraints and migrate an empty DB.
2. Auth and catalog: register/login/logout, membership checks, customer/product CRUD,
   stock ledger; test unauthenticated, foreign-tenant and role-denied requests.
3. Orders and extraction: parser, review, quota, idempotency, stock transactions,
   transitions, PDF and analytics; test negative and success paths.
4. Console: responsive overview, catalog forms, order review, invoices, settings;
   typecheck, production build and browser workflow tests where available.
5. Delivery: opt-in sample data, environment examples, Docker, CI and runbook.

## Roadmap beyond Phase 1

Phase 2: verified invitations/recovery/MFA, calibrated LLM extraction benchmark for
Sinhala/English, Tamil evaluation, purchase orders, returns, tax templates and
multi-warehouse stock. Phase 3: approved WhatsApp Business onboarding/webhook
verification, consent and retention controls, voice transcription evaluation,
payment-provider webhooks and billing reconciliation. Phase 4: load/security testing,
operational SLOs, backup restore drills, billing launch and production rollout.

## Deployment gates

Use HTTPS, private API/database networking, separate runtime/migration DB roles,
secret injection, automated backups and tested restores, centralized request/error
metrics, gateway distributed rate limiting and a data retention policy. Built-in
rate limiting is process-local and is not a substitute for a gateway. PDF rendering
needs a configured Unicode font for Sinhala names. No external integration is
assumed configured. See README for precisely what was verified locally.

## Reference decisions

- [Next.js installation](https://nextjs.org/docs/app/getting-started/installation)
- [FastAPI password hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [PostgreSQL RLS and owner bypass](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
