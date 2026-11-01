# Image-to-draft extraction

Implemented 28 October 2026 in the existing OrderMesh checkout.

## Supported flow

- Dashboard: Order assistant > Order image > Read order image. Preview the local
  original, then compare the extracted text before reviewing/confirming the draft.
- WhatsApp: signed incoming image messages retain media ID/checksum/caption
  metadata. The queue downloads the image with the workspace phone credential,
  reads its text, combines any explicit caption, classifies it and prepares the
  existing product-order or service-request draft when relevant.
- Sinhala, English, Tamil and mixed-script text are requested in their original
  language. Typed and handwritten order text is attempted. Blurred/illegible text
  is marked uncertain; accuracy on actual handwriting requires acceptance samples.
- Only explicit visible text/captions establish requested details. Product photos
  without readable order details do not establish products or quantities.
- Every image draft carries image_text_requires_review; uncertain readings also
  carry image_text_uncertain. Catalog IDs, prices, stock and human confirmation
  remain controlled by existing server validation. Reading an image never creates
  an order, changes stock or records a payment.

## Configuration

Uses AI_PROVIDER=openai and OPENAI_API_KEY. IMAGE_EXTRACTION_ENABLED defaults true.
OPENAI_VISION_MODEL is optional; when empty the existing OPENAI_MODEL is used.
A vision-capable model and available API credits are required. No text model was
silently changed. The existing Luna setting remains the default when configured.

Apply Alembic migration 0010 and install locked requirements. The local database
was backed up, migrated and checked for schema drift during implementation.

## Bounds and privacy

Only single-frame JPEG, PNG and WebP inputs, up to 8 MB, 12 megapixels and 6000
pixels per side are accepted. Actual bytes are decoded; MIME/filename claims are
not sufficient. Images are oriented and re-encoded, removing EXIF/location and
other original metadata before sending pixels to the OpenAI Responses endpoint
with store=false. Provider-side processing/retention terms still apply; this is
not a zero-retention guarantee. Original bytes are not stored on the app server.
Only extracted text, review flags and WhatsApp metadata persist.

WhatsApp downloads preserve host/checksum/size/redirect checks and tenant-owned
credentials. Viewer roles cannot trigger paid uploads. Staff/admin/owners can retry
failed image reading from the inbox. A saved OCR result is reused on subsequent
extraction retries. Provider credit errors stay actionable rather than fabricated
local OCR output.

## Verification

- Full backend regression before final privacy/role additions: 137 passed,
  3 PostgreSQL-only tests skipped locally.
- Final image-specific tests: 11 passed, covering Sinhala/English/Tamil results,
  no automatic order/stock changes, catalog prices, tenant isolation, invalid/large
  files, metadata removal, quota errors, role enforcement and WhatsApp deduplication.
- Browser: 5 passed (image upload/preview/review, voice transcript retry, full
  order/invoice flow and two website behavior checks).
- Next production build, ESLint and Ruff passed. Alembic check: no schema drift.

Actual image recognition quality is not established by simulated provider tests.
The earlier real OpenAI speech test returned credit_balance_exhausted. No real
client images were sent in this implementation. Top up API credits and review real
Sinhala/English/Tamil typed/handwritten samples before claiming live accuracy.

Official reference: https://developers.openai.com/api/docs/guides/images-vision
