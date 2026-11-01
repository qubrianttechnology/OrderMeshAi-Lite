# Service request workflow

Project: `D:\OrderMesh Ai Lite`. Implemented 27 October 2026.

## Use it

1. In Settings, complete the business profile and document for the actual business.
   Include offerings/aliases, requirements to ask for, budget/currency, deadlines,
   appointment date/time/time zone, delivery and the approval process.
2. Select services, software or agency for service-first message handling. Hybrid
   workspaces route catalog-matched untracked services to this flow; tracked goods
   continue through order extraction. Mixed goods/service messages need human review.
3. Open **Service requests** in the dashboard. Paste a customer message and select
   **Extract service request**, or review eligible incoming WhatsApp inquiries.
4. Review the original message and the extracted requirements, budget, deadline,
   appointment preference and contact. Missing fields remain blank. Confirm missing
   information with the customer; relative dates are not converted automatically.
5. Edit the fields, check the human-review acknowledgement and accept or reject.
   Accepted requests can be edited or marked completed. Closed requests are read-only.
   Reloading preserves the reviewed fields, notes and status.

Accepting records a team decision. It does not send a quote, charge a customer,
reserve a calendar slot, create an invoice/order or change stock. Agreed orders
are created separately. The API rejects using a service request as an order draft.

## Example

Customer message:

    We need a website with online booking;
    Budget: LKR 150,000;
    Deadline: 30 November;
    Meeting: Friday 2pm;
    Email: client@example.com

The request stores the stated requirements and original budget/date/contact text.
An agency project can include a meeting preference without becoming an appointment
booking. Never treat an unspecified year, currency or time zone as confirmed.

## Automatic WhatsApp processing

- Business relevance is checked locally using the business profile/document/catalog.
- Service businesses create request drafts from business orders, inquiries and support.
- Personal, spam and uncertain messages remain in the inbox without automatic drafts.
- Team members can correct a category to business inquiry/order/support to requeue an
  eligible message after adding the relevant profile details. An existing draft is
  not duplicated or overwritten by a retry.
- Expired subscriptions retain read access; creation/review requires active access.
- Real WhatsApp delivery still requires the remaining Meta connection configuration.

## Extraction and review safeguards

When AI_PROVIDER=openai, the configured model receives only the customer message
and workspace business type for service extraction. Business documents and the
customer database are not sent by this adapter. Structured output is validated:
requirements and extracted optional fields must be exact quotes from the source.
Missing/invalid/ungrounded/refused/failed model output falls back to local rules,
with ai_provider_fallback recorded and the actual provider shown on the draft.
Local rules are conservative and do not claim general language understanding.

The replacement OpenAI key passed model access (HTTP 200) on 27 October 2026.
One synthetic software request used openai-structured-v1 without fallback, extracting
budget, deadline and appointment details. Mocked provider validation and local
end-to-end processing also pass. No real customer message was used for this check.

Drafts use the existing tenant-protected extraction storage. The original extraction
and source remain unchanged when humans edit reviewed fields. Role checks, tenant
scoping, audit events and revision conflict checks protect review updates. An old
browser revision receives 409 instead of overwriting another review.
