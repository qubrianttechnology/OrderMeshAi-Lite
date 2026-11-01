# Business Intelligence

Implemented in D:/OrderMesh Ai Lite, 28 October 2026.

## Owner setup - direct dashboard answers

Open Dashboard -> Business Intelligence. Answer the guided questions directly; downloading or uploading a document is not required. Settings retains the same questionnaire for existing users.

1. Your business: choose business type and main product category; describe the business and offerings.
2. Customers and orders: describe target customers, order workflow and required details.
3. Payments and delivery: enter actual payment terms, delivery process and service areas.
4. Hours and team review: enter working hours, review topics and exclusions.
5. Message examples: optionally provide genuine, private and spam examples, one per line.
6. Review the answers and choose Save business profile. Required-answer validation returns to the incomplete step. Back/Next and Show all questions preserve current answers. Previously saved answers prefill for editing; unsaved answers are held only while this questionnaire is open, and the UI explains that final Save is required.

Use Test message filtering with a sample after saving. It uses the saved profile and workspace catalog, creating no message, order or reply. The direct-answer flow uses the existing owner/admin-only tenant-scoped profile API and does not call an external AI provider.

### Optional document import

Already have a document? Import it here (optional) is collapsed beneath the questionnaire. Existing TXT/Markdown/text PDF/DOCX upload, template download and Review document suggestions remain available. Imported suggestions initialize answers for review; they are applied to structured profile fields only after saving. Limits remain 2 MB, 20 PDF pages and 20-30,000 extracted characters. Scanned PDFs require a text layer/OCR. Original file bytes are not retained.

## Classification behavior

- Categories: business_order, business_inquiry, support, personal, spam and needs_review.
- Known credential/scam phrases are flagged as spam even when present in positive examples.
- Saved private/spam examples match whole messages after Unicode, case and spacing normalization. Conflicting examples go to needs_review. This is not semantic model training or guaranteed matching of future variants.
- Explicit review topics use escaped phrase matching and route to needs_review.
- Catalog matches and positive business context follow the existing conservative classifier. Target-client descriptions inform relevance, not authentication or customer eligibility.
- Mixed personal/catalog messages go to needs_review instead of generating a product draft.
- Negative example sections in structured documents are excluded from positive keyword context.
- Classified private/spam/uncertain messages stay in the inbox and do not produce automatic extraction drafts. The existing inbox category dropdown lets the team filter messages and correct a category. Changing an already-processed message category does not erase an existing draft/order; deleting or confirming business records remains a separate explicit action.
- Genuine client examples imply an inquiry, not automatic acceptance, pricing or order confirmation.

Business documents are parsed locally and are not sent to OpenAI. Matching does not execute instructions written in an uploaded document. Voice/image handling may independently require provider processing as documented in VOICE_AND_LANGUAGES.md and IMAGE_EXTRACTION.md.

Business profile editing and upload remain owner/admin only, tenant-scoped and audited. Authenticated members can use the read-only preview within their workspace. Existing product/service extraction and order confirmation requirements remain in force. Service area and required-details fields are team guidance, not a booking system or automatic quote validator.

## Verification

- Full backend regression: 150 passed; 3 PostgreSQL-only checks skipped locally.
- Full Edge browser suite: 14 passed, including document suggestions, save/reload, examples and classification preview.
- Production build/TypeScript, frontend ESLint and backend Ruff passed.
- PDF extraction, private-example handling through the inbox worker path, tenant isolation, conflicting examples, mixed catalog/private text and read-only preview are covered by regression tests.
- Live WhatsApp provider acceptance is still pending Meta setup/review; no claim of perfect classification or live connection follows from these checks.


## Inbox category filters (2026-10-30)

The inbox Filter messages menu filters both the conversation list and the open thread. Business messages combines orders, business inquiries and customer support. Other choices include Private messages, Spam and Needs review; unclassified inbound messages appear in Needs review. Outbound replies remain visible for conversation context. Filtered chat previews use the latest matching inbound message. Search includes older message text as well as customer name/phone. Changing a message category refreshes the conversation list. These are display filters, not deletion or authorization rules; classification can require manual correction.

Validation: 14 focused backend checks passed, including tenant isolation, older-text search and mixed-category preview handling. Two Edge browser tests passed for inbox filters and existing voice review behavior. Frontend lint/TypeScript and backend Ruff passed. No live outbound WhatsApp message was sent for these checks.
