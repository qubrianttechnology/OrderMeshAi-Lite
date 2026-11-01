# 31 October 2026: profile, basic settings and inbox management

Settings now starts with a personal profile (name, phone and private JPG/PNG/WebP profile photo) and owner/admin business basics (workspace name, contact email/phone and address). Photos are validated, resized and stored privately. Sign-in email, actual business type, currency and report timezone are informational. Business Intelligence remains a dedicated section; the business setup shortcut opens it. Existing subscription setup remains under Business workflow & subscription.

Settings > Your dashboard > Layout offers Recommended or Full business dashboard. Qubriant's software/service workflow differs from the wholesale demo by design. Full layout exposes sales/profit charts, inventory and operations alongside service requests without changing business type or AI extraction workflow. Existing workspace layout choices were not changed automatically.

WhatsApp inbox supports Active/Unread/Archived/All views, pin/unpin, archive/unarchive and mark read/unread, preserving existing category/search/reply/customer-linking controls. Background polling does not clear unread markers. New incoming messages reopen archived chats. Inbox management is scoped to the current workspace and owner/admin/staff; viewers cannot manage chats.

Migration 0015 was applied to the local development database after SQLite backup. Existing user/workspace/product/conversation/message counts were preserved; local API and dashboard health returned HTTP 200. No new public tunnel, real outbound WhatsApp send, production-mode switch or external chatbot data sharing was introduced.

Validation: 181 backend tests passed; 3 PostgreSQL-only tests skipped. Five distinct Edge browser workflows passed across final targeted runs: profile/photo/basic settings/full layout; inbox management; category filters/search; WhatsApp order approval/local chatbot settings; service-business profile/catalog/layout. Frontend lint, TypeScript and production build passed. Desktop/mobile settings preview loaded, with no horizontal page overflow at 390px. Screenshots: `.local/account-settings-desktop.png`, `.local/account-settings-mobile.png`.

# 31 October 2026: Hell Mart confirmed as real business target

Hell Mart is an existing non-demo workspace with no catalog or WhatsApp connection yet. The owner confirms no verified real WhatsApp number is available. The configured Meta test credentials currently fail read-only authentication (HTTP 401). Live WhatsApp activation is pending real-number verification, valid credentials and an authorized HTTPS signup origin. Test-send restrictions and payment sandbox were preserved. See [Hell Mart live setup](HELL_MART_LIVE_SETUP.md). No demo catalog was copied into real business data.

# Dashboard tool visibility and product access — 30 October 2026

Existing updates are now discoverable through an Overview tool directory and direct sidebar links to POS, Purchases, Warehouses, Returns, Credit & payments, Reports & expenses, Delivery and Team. Product businesses show Products & inventory, with barcode-aware search, 50-row pagination and selected-workspace context. Catalog data loads even when analytics or another independent request fails. Product-business owners can reopen a hidden catalog using its menu entry; service-business saved visibility remains respected. Navigation preserves the selected feature across reloads; the POS quick action consistently opens POS.

Validation: four existing browser workflows passed (commerce, wholesale products, general workflow, service-business settings); the new navigation/partial-failure/pagination/hidden-catalog recovery/mobile check passed on its final run. ESLint/TypeScript and isolated production build passed. Live local preview confirmed all 3,000 demo products, 50 visible rows, catalog-wide search, direct Purchasing and reload persistence. Screenshots: `.local/dashboard-tools.png` and `.local/dashboard-products.png`. Sample products remain exclusively in OrderMesh Demo Wholesale; no sample catalog was copied into another workspace.

# 30 October 2026: wholesale operations and isolated demo

POS, barcode search, wholesale pricing/MOQs, supplier purchase orders/GRN, warehouse balances/transfers, credit limits/aging, returns/refunds, expenses/profit reports, delivery and team permissions are implemented. Notification centre now has per-user read tracking and optional sound/desktop alerts. Local migrations 0013–0014 were backed up/applied; real inventory was allocated to Main without changing quantities. A separate demo owner/workspace has 3,000 synthetic products and no WhatsApp connection. Local multilingual and one synthetic live `gpt-6-luna` extraction passed; real chatbot data export remains disabled. See [workflow and limits](COMMERCE_WORKFLOWS.md). Validation: 176 backend tests passed; 3 PostgreSQL-only tests skipped because no disposable PostgreSQL test database is configured. All 19 Edge browser tests passed. Backend Ruff, frontend lint/TypeScript and the isolated production build passed. A further migration-preservation run passed all 4 migration/seed tests.

Earlier updates below are historical; their statements about unavailable POS/credit/warehouse features are superseded by this update.

> Latest verification, 28 October 2026: full API 139 passed (3 PostgreSQL checks skipped), full Edge browser suite 13 passed, production build and lint passed. Meta Business Verification is owner-reported In review. See [current completion checklist](COMPLETION_STATUS.md); older provider checks below are historical.

# OrderMesh local status

Updated 27 October 2026. Project: `D:\OrderMesh Ai Lite`.
The older PROJECT_STATUS.md is a dated audit, not the current feature checklist.

## Open the application

http://localhost:3000/sign-in

```powershell
.\Start-OrderMesh.ps1
# Reload saved API environment changes:
.\Start-OrderMesh.ps1 -Restart
```

Existing accounts and business data are preserved. No sample data is seeded by
the launcher. Logs and tracked processes are in ignored `.local/` files.

## Service request update

Services, software and agency requests now extract requirements, budget, deadline,
appointment preferences and contact into a separate human-review workflow. The
**Service requests** dashboard supports editing, acceptance/rejection and completion,
with persistent review notes, original evidence, role/tenant checks and stale-update
protection. Eligible WhatsApp inquiries use this flow; personal/spam messages do not.
Hybrid catalogs keep tracked product orders separate. No booking/invoice/stock change
is made by accepting a service request. See [workflow guide](SERVICE_REQUEST_WORKFLOW.md).

OpenAI key replaced and rechecked on 27 October: model access HTTP 200. A synthetic
software request used openai-structured-v1 without fallback and extracted budget,
deadline and appointment details. OPENAI_MODEL restored to gpt-6-luna after it was blank.

## Features restored and implemented

1. Original OrderMesh green/white dashboard restored; dark mode is optional.
2. Retail/wholesale/service/software/agency/hybrid business profiles and adaptive
   navigation. Non-stock services can be ordered and cancelled without changing stock.
3. Business-document template, TXT/Markdown/text-PDF/DOCX upload and an editable
   business workflow with required description, offerings, customers, hours,
   payment policy and delivery process. Documents are processed locally.
4. WhatsApp webhook/inbox/SSE and review-before-order workflow retained.
5. Local business/personal/spam/support/inquiry/review categories, inbox filtering
   and manual correction. Non-order messages are retained without creating drafts.
6. LKR 7,400/month plan and server-enforced 15-day trial. Existing records remain
   readable after expiry; payment renewal and business-profile setup remain accessible.
7. PayHere recurring checkout, consent, server-generated hash, signature checking,
   independent payment retrieval, replay-safe renewals, cancellation and removal of
   entitlements for gateway-confirmed refunds/chargebacks. Provider lifecycle tests
   use mocks; no real payment was made.

See [the ordered checklist from this chat](FEATURE_RESTORE_CHECKLIST.md) for the
next item and a distinction between implementation and live-provider verification.

## Verification

- Backend: **99 passed, 3 PostgreSQL tests skipped** without a disposable test target.
- Frontend: TypeScript, lint and production build pass.
- Browser: **5 workflows passed** using installed Edge (landing/auth; agency
  onboarding/service catalog; service extraction/edit/accept/reload/complete;
  mocked Meta SDK authorization/number selection/explicit consent;
  customers, stock, Sinhala extraction, orders, invoices and WhatsApp simulator).
- Database: migration **0008**, model/schema drift and foreign-key checks are verified
  as part of the final local checks. Existing SQLite data is backed up before migration.
- Source before restoration: `.local/restore-backups/`.
- Database backups: `services/api/ordermesh.before-0006-*.db` and
  `services/api/ordermesh.before-0007-*.db`.

## Owner configuration still required

Enter secrets only in `services/api/.env`, then restart the launcher.

- **Google:** Client ID/secret are configured. Redirect to Google, callback URL,
  PKCE and state cookie passed local checks. Complete a real login to verify consent
  and token exchange. Redirect URI: `http://localhost:3000/api/auth/google/callback`.
- **OpenAI:** `gpt-6-luna` is configured. Replacement key passed model access (HTTP
  200) and one synthetic service extraction without fallback. Real customer-message
  accuracy still needs business-specific review; every draft requires human confirmation.
- **Meta:** the supplied screenshot shows Integrity cleared. App ID
  `1609244170127322` and Embedded Signup Configuration ID `1450204687306079`
  are saved in the API environment. App Secret is also configured (presence checked
  without exposing its value). Graph API version
  is pinned to v26.0 and a private verification token has been generated; public
  HTTPS dashboard/callback and Meta domain/webhook setup remain incomplete. Client self-service Embedded Signup is implemented and tested with mocks;
  saving these identifiers alone does not connect a number. Business Verification
  and App Review/Access Verification were incomplete in the supplied screenshot.
- **PayHere:** set `PAYHERE_MERCHANT_ID`, `PAYHERE_MERCHANT_SECRET`, `PAYHERE_APP_ID`,
  `PAYHERE_APP_SECRET`, `PAYHERE_SANDBOX` and a public HTTPS `PAYHERE_NOTIFY_URL` ending
  in `/api/billing/payhere/notify`. Merchant API permissions and live server-IP approval
  must be confirmed with PayHere. Start with sandbox credentials and an actual
  end-to-end test. The browser return URL never activates a subscription.
- **Supabase:** the running app currently uses local SQLite. Production needs
  restricted runtime/migration PostgreSQL roles for the same database, RLS/concurrency
  tests against a disposable target and deployment/backup verification.
- **Hosting/domain:** last, as requested.

## Current limits

Profile-based categorization is a conservative local rule system, not a proven
AI classifier. Uncertain messages remain visible for human review. Business
documents are not automatically sent to OpenAI. Existing opt-in AI order extraction
continues to require a valid key and explicit human confirmation of every order.
Scanned/image-only documents need OCR before upload; voice and Tamil remain outside
the current implemented workflow. Live payments, real WhatsApp traffic, Embedded
Signup and production PostgreSQL are not claimed as verified by local tests.

Dashboard Meta connection details and remaining owner steps: [guide](WHATSAPP_EMBEDDED_SIGNUP.md).
Owner explicitly approved temporary public HTTPS. Tunnel is running; public sign-in/API/webhook and auth denial checks passed. New public registrations are disabled during this test. Stop and restore local settings with Stop-OrderMeshHttps.ps1.

Temporary sign-in URL: https://descending-readers-objects-expression.trycloudflare.com/sign-in
Meta domain allow list and webhook subscription must still be completed in the Meta console.

Google HTTPS callback configured and public start redirect verified (303, state cookie, S256).
Owner must add https://descending-readers-objects-expression.trycloudflare.com/api/auth/google/callback to the existing Google Web OAuth client authorized redirect URIs. Stop script restores localhost configuration.

Google login follow-up: observed invalid_oauth_state and blocked Next dev-domain resources.
Launcher now allowlists only the configured APP_ORIGIN hostname and prints its sign-in URL.
Localhost Google start redirects to the configured HTTPS origin before setting state.
Google login is a normal anchor so it works before client JS hydration.
An isolated public browser check verified state storage/matching and the cross-site callback cookie; Google pages were mocked and no real account was accessed.

Meta exchange follow-up: live provider diagnostics identified HTTP 400/code 100/subcode 36008. The official SDK was inspected in an isolated, unsigned-in browser: its popup uses a dynamic staticxx.facebook.com/x/connect/xd_arbiter callback. The frontend now preserves that exact URI from the synchronous SDK popup call and restores window.open immediately; the server validates the official host/path and passes the URI unchanged during exchange. Provider HTTP 400 errors now return application HTTP 422 so validation details are preserved. Eight Meta backend tests passed, including exact binding and untrusted callback rejection. A fresh owner authorization remains necessary to verify the fix with a real Meta code. No authorization codes or tokens were logged.


Latest WhatsApp connection update: number-first entry, automatic Meta launch,
completion WABA hint capture and server-authoritative requested-number matching.
A single verified Business App number connects and opens the inbox; Cloud API PIN
registration remains an explicit extra step. The live missing-WABA-metadata error
is addressed by verifying the SDK-selected account with the actual Meta grant.
The temporary HTTPS origin remains configured. The owner reported saving webhook
settings; live connection and inbound customer delivery still require a fresh test.
Existing chat history is not automatically imported. No secrets were printed.

Final regression checks: backend 105 passed; 3 PostgreSQL-only checks skipped
because this local environment uses SQLite. TypeScript, ESLint and Ruff passed.
Restarted API/dashboard and verified public /api/health and /sign-in return HTTP 200.
Browser connection checks: 2 passed in Edge (automatic Business App connection
and Cloud API registration PIN fallback), using synthetic Meta responses.


Google login recovery: the temporary Cloudflare tunnel expired (provider logs:
Unauthorized: Tunnel not found), and its hostname stopped resolving. Stopped only
the recorded process after PID/start-time/path verification and restored saved
local settings with Stop-OrderMeshHttps.ps1. API and dashboard restarted.
Current sign-in: http://localhost:3000/sign-in
Current Google callback: http://localhost:3000/api/auth/google/callback
Live start check: HTTP 303 to accounts.google.com, localhost callback, OAuth
state cookie, and S256 PKCE verified. A fresh owner Google login is still required;
the callback must remain authorized in the Google Cloud Web OAuth client.
WhatsApp public webhooks require a new stable public endpoint before live testing.


WhatsApp final preparation: new approved tunnel origin is
https://ought-puzzles-darwin-optimization.trycloudflare.com . Server Meta setup
ready=True, but active connected numbers=0. Popup reservation and SDK callback
updated; normal client flow separate from collapsed developer tools. Backend
WhatsApp/Meta checks: 25 passed. Browser connection/PIN/order checks: 3 passed.
Public health/sign-in=200, invalid webhook token=403; real token verified locally.
The real-token public diagnostic was rejected by auto-review and not executed.
Owner still must save new Meta/Google domain settings, authorize the business
number, and send a real inbound message. These steps prevent claiming live success.


Origin/CSRF follow-up: reproduced localhost POST=403 while the configured HTTPS
origin passed the CSRF guard (unauthenticated request correctly returns 401).
Added Next proxy for local GET/HEAD browser pages to the fixed configured HTTPS
origin; API/webhook requests and POST requests are not redirected. Launcher passes
the complete configured origin and uses the local API health endpoint for readiness.
Live check: localhost sign-in 307 to the configured HTTPS sign-in, public page 200,
trusted POST reaches authentication, untrusted origin still 403. Owner must reload
old local tabs and sign in on the HTTPS hostname before connecting WhatsApp.

