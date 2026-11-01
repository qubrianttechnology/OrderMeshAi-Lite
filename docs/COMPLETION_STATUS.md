# Dashboard performance charts — 30 October 2026

Added five actual-data Overview panels: gross profit breakdown, low-stock list, profit versus posted sales, top-selling products and staff performance. Period choices are 7/30/90 days; financial amounts use LKR, tax/returns and known cost snapshots. Unknown costs remain incomplete. Financial access is owner/admin only. Tools remain directly accessible below the performance area and from the sidebar. See docs/DASHBOARD_CHARTS.md for definitions and validation (178 backend passed, 3 PostgreSQL skipped; 3 targeted browser cases passed).

# Dashboard tool visibility and product access — 30 October 2026

Existing updates are now discoverable through an Overview tool directory and direct sidebar links to POS, Purchases, Warehouses, Returns, Credit & payments, Reports & expenses, Delivery and Team. Product businesses show Products & inventory, with barcode-aware search, 50-row pagination and selected-workspace context. Catalog data loads even when analytics or another independent request fails. Product-business owners can reopen a hidden catalog using its menu entry; service-business saved visibility remains respected. Navigation preserves the selected feature across reloads; the POS quick action consistently opens POS.

Validation: four existing browser workflows passed (commerce, wholesale products, general workflow, service-business settings); the new navigation/partial-failure/pagination/hidden-catalog recovery/mobile check passed on its final run. ESLint/TypeScript and isolated production build passed. Live local preview confirmed all 3,000 demo products, 50 visible rows, catalog-wide search, direct Purchasing and reload persistence. Screenshots: `.local/dashboard-tools.png` and `.local/dashboard-products.png`. Sample products remain exclusively in OrderMesh Demo Wholesale; no sample catalog was copied into another workspace.

# 30 October 2026: wholesale operations and isolated demo

POS, barcode search, wholesale pricing/MOQs, supplier purchase orders/GRN, warehouse balances/transfers, credit limits/aging, returns/refunds, expenses/profit reports, delivery and team permissions are implemented. Notification centre now has per-user read tracking and optional sound/desktop alerts. Local migrations 0013–0014 were backed up/applied; real inventory was allocated to Main without changing quantities. A separate demo owner/workspace has 3,000 synthetic products and no WhatsApp connection. Local multilingual and one synthetic live `gpt-6-luna` extraction passed; real chatbot data export remains disabled. See [workflow and limits](COMMERCE_WORKFLOWS.md). Validation: 176 backend tests passed; 3 PostgreSQL-only tests skipped because no disposable PostgreSQL test database is configured. All 19 Edge browser tests passed. Backend Ruff, frontend lint/TypeScript and the isolated production build passed. A further migration-preservation run passed all 4 migration/seed tests.

Earlier updates below are historical; their statements about unavailable POS/credit/warehouse features are superseded by this update.

# OrderMesh completion status

Latest checks 30 October 2026 in `D:/OrderMesh Ai Lite`.

## Verified application workflows

- Account registration, session authentication and workspace isolation.
- Google sign-in entry point works before browser JavaScript loads; backend OAuth flow is covered with simulated Google responses.
- Business profiles, document upload and service businesses without stock.
- Customers, products, inventory adjustments and order review.
- Sinhala/English/Tamil and mixed-language text extraction, uncertain-detail review and explicit order confirmation.
- Personal/spam/business message routing and tenant-scoped inbox API tests.
- Service request extraction, editing and completion without creating a product order.
- Order fulfillment/cancellation, totals and stock handling.
- Downloadable invoices with bundled Sinhala/Tamil/English fonts and text shaping; synthetic Sinhala PDF visually reviewed.
- WhatsApp number-first connection, PIN fallback, grant validation, webhook processing and reply paths under simulated provider responses.
- Website navigation, interactive demonstrations and desktop/mobile layouts.

## Current checks

| Check | Result |
| --- | --- |
| Full API test suite | 163 passed, 3 PostgreSQL-only tests skipped locally |
| Playwright (Edge) | 17 passed in the full suite; final approval UI check also passed |
| Production Next.js build | Passed, all routes generated |
| Frontend ESLint | Passed |
| Backend Ruff | Passed |

PostgreSQL tests require a disposable PostgreSQL server. CI now explicitly sets
`TEST_POSTGRES_DISPOSABLE=YES` for its dedicated service so those tests execute
rather than silently skipping. This change has not been run in remote CI here.

## Still needs real provider or hosting verification

1. Meta: the last owner-reported popup stopped after Facebook login without a WhatsApp account selection. A real number has not yet been verified as connected. Check the Embedded Signup configuration and complete the business/number flow, then send a real inbound message and test a reply.
2. Meta: owner reports Business Verification is now In review (28 October). The latest provided status screenshot shows Integrity cleared and App Review/Access Verification incomplete. Wait for the verification decision and complete remaining provider requirements. This does not establish the sole cause of the Facebook-only popup.
3. Google: complete one real sign-in on the final HTTPS domain with its authorized callback. Simulated OAuth tests do not establish that the current external settings work.
4. Payments: PayHere code is tested with simulated responses; live merchant setup and a real payment/refund acceptance check remain separate.
5. Database: run migrations, tenant-isolation and concurrency checks against a disposable PostgreSQL server before production.
6. Hosting: no domain or hosting account has been selected. The owner requested feature completion before deployment. No production deployment was performed.

## Scope limits

WhatsApp voice transcription and Tamil/mixed-language extraction are now implemented; see `VOICE_AND_LANGUAGES.md`. Live voice verification is currently blocked by exhausted OpenAI credits. Image text extraction is implemented with dashboard upload and WhatsApp image handling; see IMAGE_EXTRACTION.md. Real image recognition accuracy remains unverified. Service
requests remain human-reviewed. Existing WhatsApp chat history is not automatically
imported. Invoices have no VAT/tax calculation or payment-receipt certification.

These are the remaining external acceptance steps; passing local tests does not
mean Meta onboarding, live payments or production hosting is complete.

Voice/Tamil update: backend 128 passed; focused browser tests passed for voice retry/Tamil transcripts, the existing order/invoice workflow and two website behavior checks. Production build, Ruff and dependency check passed. Live synthetic speech request was blocked by exhausted OpenAI API credits; see VOICE_AND_LANGUAGES.md.

Image feature update: full backend regression 137 passed plus final image-specific tests 11 passed; focused browser checks 5 passed. Build/lint passed and local migration 0010 applied after backup. Live acceptance still requires API credits and actual sample review.

## Latest complete regression, 28 October 2026

- API: 139 passed; 3 PostgreSQL-only checks skipped because no disposable server is configured locally.
- Browser (Microsoft Edge): all 13 tests passed in 2.6 minutes, including mobile/desktop layouts, orders/invoice, service requests, image review, voice/Tamil display and both WhatsApp PIN connection simulations.
- Production build: compilation, TypeScript and all routes passed.
- Frontend ESLint and backend Ruff passed.
- No application test failure was found in this run. No live provider request or production deployment was made.

## Remaining completion order

1. Restore OpenAI API credits, then verify synthetic voice and image extraction with Sinhala, English and Tamil samples. The last live voice check returned credit_balance_exhausted; current billing was not rechecked during this regression.
2. Finish Meta verification/review and diagnose the Facebook-only Embedded Signup response. Connect the owner's Business app number through an eligible Coexistence flow, then verify a real inbound message and an explicit dashboard reply. Do not disconnect/delete the existing Business app account as a troubleshooting shortcut.
3. Verify real Google sign-in on the final HTTPS origin.
4. Run the three PostgreSQL checks in the dedicated disposable CI database (remote CI has not been executed here).
5. Configure PayHere live merchant credentials and perform an agreed payment/refund acceptance check if paid launch includes live checkout.
6. Select hosting/domain, set stable callbacks, deploy, and verify backup/restore and production smoke tests.

## Business dashboard update, 28 October 2026

Business-specific module recommendations, persistent owner/admin customization, tenant-scoped service summaries, service/catalog labels and salon/repair/restaurant/online-store types are implemented. See BUSINESS_DASHBOARDS.md for setup and scope. Sidebar scrolling was fixed so Settings remains reachable on short viewports.

Final backend regression: 145 passed, 3 PostgreSQL checks skipped; Ruff and dependency checks passed. Complete Edge browser suite: 13 passed after adding layout persistence, recommendations reset and role-aware business navigation coverage. Production build/TypeScript and frontend ESLint passed after the final service catalog and form-label polish. The last UI polish is additionally checked by the focused business setup browser test.

Meta/live AI/payment/hosting acceptance items above remain outstanding; this feature does not add a booking calendar, courier integration or POS.

## Business Intelligence update, 28 October 2026

Added a dedicated dashboard entry, target-client context, local PDF/DOCX/TXT/Markdown document suggestions, explicit business/private/spam examples, manual-review topics and a read-only classification preview. Structured negative example sections no longer contaminate positive business keywords; mixed private/catalog context is reviewed. See BUSINESS_INTELLIGENCE.md for setup and conservative matching limits.

Final full regression: API 150 passed, 3 PostgreSQL checks skipped; Edge browser 14 passed. Production build/TypeScript and both lint checks passed. Live Meta/AI/payment/hosting acceptance remains as listed above.


## Wholesale/distributor update - 30 October 2026

Home/signup positioning and new workspace defaults now target wholesalers and distributors. Catalog products have validated categories: electronics, fashion, beauty, grocery, household, packaging, stationery, hardware, vehicle_parts and other. Business profile supports a primary category; inventory supports category filtering and SKU/name/alias/part-number search, with price shown per selling unit. Vehicle part fitment and pack conversions require human review; no compatibility database, price tiers, MOQ enforcement or credit ledger was added. See WHOLESALE_AND_DISTRIBUTORS.md.

Local SQLite was backed up before additive migration 0011. Alembic check reported no drift, API health returned 200, and no existing business catalog was seeded or reclassified. Backend 153 passed/3 PostgreSQL-only skipped; all 16 Edge browser cases passed across the full run and a marketing assertion rerun; build, frontend lint/TypeScript and backend Ruff passed. Desktop/mobile and the vehicle-parts catalog screenshots were reviewed.

Live test update: the Meta test number received a real incoming message and a service inquiry produced an OpenAI-backed pending-review draft. Real outgoing reply, production client onboarding, Google acceptance on a stable origin and live payment verification remain separate acceptance work. The dashboard remains localhost-only; the authorized temporary public tunnel exposes only the existing WhatsApp webhook.


## WhatsApp owner approval and local chatbot - 30 October 2026

Implemented opt-in local chatbot controls, saved-business FAQ replies, deterministic catalog/stock availability replies, a durable tenant-scoped outbound queue, pending WhatsApp requests in Orders, in-app notification counts, owner/admin approval/rejection and 15-second visible-dashboard refresh. Approval reuses locked stock/current-price validation and idempotent order creation; stock is reduced once only after approval. Bot sends respect the recipient test allowlist, service window and real-number credential ownership. Unknown provider outcomes are not automatically resent. Simulator events never send chatbot replies.

The owner declined the proposed AI conversation data sharing and selected local workflow only. The rejected OpenAI chatbot conversation adapter was not implemented. When the chatbot is enabled, WhatsApp text extraction is local and audio/images require manual review. Other existing application AI tools remain separate. See WHATSAPP_ORDER_APPROVAL.md for activation, data boundaries, retry semantics and limits. No generative AI chatbot is claimed active.

Final checks: backend 163 passed, 3 PostgreSQL-only tests skipped; full Edge suite 17 passed plus final focused owner approval check; production build, lint/TypeScript and Ruff passed. Local migration 0012 applied after SQLite backup; migration alignment and rollback checks passed. API/dashboard returned HTTP 200. Owner approval screenshot reviewed. No production settings changed or new public routes/tunnels started. Chatbot is off by default; no local business workspace has been auto-activated. Live outbound WhatsApp replies remain unverified; test recipient allowlist configuration is still required.


## Direct business answers - 30 October 2026

Business Intelligence and Settings now use a guided in-dashboard questionnaire as the primary business setup flow. Five question groups cover business/offerings, customers/orders, payment/delivery, hours/review and message examples, followed by review/save. Saved answers prefill, Back/Next preserve in-progress values, Show all questions supports direct editing, and required-answer validation prevents incomplete saves even if the user skips to review. Answers persist through the existing owner/admin tenant-scoped business-profile API; no document or external AI request is required. Unsaved answers remain in-memory until final Save; this is explained in the UI.

Document download/upload is retained in a collapsed optional import section. Legacy document suggestions and profile save behavior were regression-tested. Narrow-screen header breadcrumb and form sizing were fixed after the mobile check detected horizontal overflow.

Validation: six focused Edge cases passed across questionnaire, optional document intelligence, existing business setup, wholesale category editing and desktop/mobile design. Saved answers were verified after reload; no document endpoint was called by the direct-answer flow. Final TypeScript and ESLint passed; production build validated. Backend code/schema unchanged in this update; the prior full backend result remains 163 passed/3 PostgreSQL-only skipped. The prior full Edge suite was 17 cases, before adding this questionnaire case; no claim of a new full 18-case run is made. Mobile screenshot visually reviewed. See BUSINESS_INTELLIGENCE.md for the new setup instructions.
