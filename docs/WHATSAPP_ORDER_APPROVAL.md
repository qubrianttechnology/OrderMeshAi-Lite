# WhatsApp requests, local chatbot and owner approval

## Current mode and consent

The owner chose local workflow only on 30 October 2026 and declined the proposed OpenAI conversation export (current message, scoped business history, business profile and catalog). That AI conversation integration was not applied. No bot_ai adapter exists. This chatbot uses deterministic local rules and database facts; do not present it as an active generative AI chatbot.

The new chatbot is opt-in per workspace in Settings. When enabled, its WhatsApp text extraction uses local rules, including service requests; audio and images stay for manual review rather than external AI media processing in that workflow. Other previously configured application AI tools are separate. Uploaded business documents are not exported by the chatbot.

## Order flow

- Incoming business order/inquiry text is classified, extracted into a review draft and shown in Orders under Awaiting owner approval. Private/spam messages do not receive automated replies. Simulator requests are clearly marked and never generate outgoing chatbot jobs.
- The chatbot can acknowledge the request with catalog-grounded availability. Requested units must match the catalog unit, combined repeated product lines are checked together, unknown items/quantities/units require review, and untracked stock is not claimed available. Availability is rechecked at send time. Nothing reserves or reduces stock at this stage.
- Notifications show pending WhatsApp approvals. Dashboard data refreshes about every 15 seconds while visible, pauses automatic refresh during a review dialog, and refreshes immediately after approval. Owners/admins can open the original request, review all flags and select/link a customer before confirmation. Staff cannot convert a WhatsApp draft into an approved order.
- Order confirmation uses the existing tenant transaction, locked catalog, current stock/price checks, monthly limits and idempotency protection. Successful approval creates the order and reduces stock once with ledger records. Insufficient stock or changed prices blocks approval. Rejected drafts cannot later be confirmed through the same request.
- A confirmation reply is queued in the successful order transaction if the chatbot is enabled. Rejections can also queue a team-review reply. Pending availability replies are cancelled if the request has already been approved/rejected; a queued confirmation is cancelled if its order was cancelled.

## Chatbot activation and delivery

Settings > WhatsApp chatbot > Activate WhatsApp chatbot > Save chatbot settings. A connected number, valid token, Meta subscription, provider permissions and open 24-hour service window are required. Test mode requires WHATSAPP_ALLOWED_TEST_RECIPIENTS in services/api/.env. Configuration defaults are not broadened automatically. The local test recipient allowlist was empty at implementation time, so live outbound delivery is not claimed verified.

Opening-hours/delivery/payment answers use saved profile fields and supported local question keywords. Availability/approval wording supports English, Sinhala and Tamil; profile information uses the owner's saved wording. Unknown questions remain with the team. Rules do not supply general conversational intelligence or product fitment guarantees.

A durable tenant-scoped outbox records queued/sending/accepted/blocked/unknown/cancelled states. Accepted means Meta accepted the API request, not final delivery; delivery receipts remain in Inbox. Known pre-send blocks can be retried by an owner/admin after fixing settings. Timeouts or crashes with uncertain delivery are not automatically resent. Disabling the bot cancels its queued work. No exactly-once external delivery guarantee is made.

## Data and verification

Migration 0012 adds the reply outbox with composite tenant foreign keys and forced PostgreSQL RLS. The local SQLite database was backed up before migration; no stock/order data was seeded or auto-approved for this feature. Backend 163 passed/3 PostgreSQL-only skipped, all 17 Edge cases passed, and final owner approval UI verification passed. Production build, frontend lint/TypeScript, backend Ruff, migration alignment/rollback and local HTTP health checks passed. The pending approval screenshot was visually reviewed. Outbound tests use a mocked Meta send adapter; live customer replies require a separate acceptance check.
