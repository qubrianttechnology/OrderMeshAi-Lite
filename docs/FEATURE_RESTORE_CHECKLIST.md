# OrderMesh feature restoration checklist

Source: the user requests visible in this chat, including changes made after the
23 October planning PDF. Later user instructions take priority over draft PDF pricing.
Project: `D:\OrderMesh Ai Lite`. No changes belong to the removed BizSi project.

| #   | User requirement                                              | Implementation and current verification                                                                                                                                                                                                                                                                                      |
| --- | ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Restore the previous OrderMesh design                         | Green/white light dashboard restored from the saved screenshot; dark mode remains optional. Screenshot and browser checks available.                                                                                                                                                                                         |
| 2   | Work for retailers, software companies, services and agencies | Business type in Settings; service navigation/catalog, non-stock orders, safe cancellation and separate service request extraction/review lifecycle implemented and tested. Hybrid workspaces can mix tracked products and services.                                                                                                                                |
| 3   | Collect a business document and tell clients what to include  | Template download, TXT/Markdown/PDF/DOCX upload, editable business profile, workflow/hours/payments/delivery fields. Local processing; no automatic document export. Tested.                                                                                                                                                 |
| 4   | Receive WhatsApp messages and update the dashboard            | Existing signed webhook, tenant phone routing, persistent inbox, processing queue, SSE and draft review retained. Simulator/browser workflow tested; real delivery awaits Meta configuration.                                                                                                                                |
| 5   | Separate business messages from personal/spam                 | Local catalog/profile matching, inquiry/support/personal/spam/review categories, inbox filter and manual category correction. Non-order messages are retained without order drafts. Tests pass.                                                                                                                              |
| 6   | LKR 7,400 monthly, 15-day free trial                          | Pricing and Settings screens updated. Server checks trial/paid expiry; read access and billing renewal remain available after expiry. Tested.                                                                                                                                                                                |
| 7   | PayHere                                                       | Recurring checkout, explicit payment consent, server-generated hash, signed notification and independent gateway reconciliation, replay protection, cancellation and chargeback entitlement removal implemented. Mocked lifecycle tests pass. Live payment testing needs merchant/API credentials and public HTTPS callback. |
| 8   | Client connects their own number simply from dashboard        | Dashboard Embedded Signup, session-bound exchange, Meta-verified phone selection, encrypted tenant credentials, coexistence/Cloud API handling and per-number replies implemented. API/browser mocks pass. Public HTTPS and Meta domain/webhook verification remain; no live connection is claimed.                                                                                                                                   |
| 9   | Google Sign-In                                                | Backend integration and Google redirect were verified earlier; owner must finish a real consent/login to prove token exchange.                                                                                                                                                                                               |
| 10  | OpenAI Luna                                                   | gpt-6-luna remains configured. Replacement key passed model access (HTTP 200) and synthetic service extraction without fallback on 27 October. Existing order-text extraction and local fallback are retained. Business-document filtering stays local. Service request AI extracts grounded requirements/budget/deadline/appointment/contact, with visible local fallback and human review. Current key access recheck: HTTP 200; live synthetic extraction passed.                                                                                                          |
| 11  | Domain and hosting last                                       | Preserved as requested. App currently uses local SQLite; PostgreSQL/RLS and production deployments remain verification gates.                                                                                                                                                                                                |

## Checks completed so far

- Backend: 99 passed, 3 PostgreSQL tests skipped without a disposable test target.
- Restored design/order/invoice/inbox workflow: browser test passed.
- Agency document onboarding and service catalog: browser test passed.
- Frontend typecheck, lint and production build pass. All five browser workflows pass (installed Edge); service request review survives reload.
- A backup of the prior source is in `.local/restore-backups/`.

## Definitions used in this checklist

Implemented means code exists and has local checks. It does not mean a provider's
live account, payments, consent or permissions have been verified. Credentials are
entered only in `services/api/.env`, never into chat or the browser bundle.

Service request usage and provider limits: [workflow guide](SERVICE_REQUEST_WORKFLOW.md).

WhatsApp connection setup: [guide](WHATSAPP_EMBEDDED_SIGNUP.md).
