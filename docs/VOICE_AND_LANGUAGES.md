# Voice notes and languages

Sinhala, English, Tamil and mixed-script customer text now share the reviewed
order/service workflow. Add the business's actual Sinhala/Tamil product aliases
to the catalog for deterministic matching. Local rules do not guess spoken number
words, products or translated names; unclear matches stay for human review. The
configured structured model may resolve those details, subject to server validation.

## WhatsApp voice flow

1. A signed webhook stores only audio media ID/checksum metadata, not audio bytes.
2. The queue worker uses the active workspace phone credential to request Meta's
   media metadata with `phone_number_id`, verifies the download host and checksum,
   and downloads up to 8 MB. Redirects and arbitrary hosts are rejected.
3. Audio, including WhatsApp OGG/Opus, is decoded locally to mono 16 kHz WAV.
   Maximum duration is 3 minutes. Empty/invalid/oversized audio fails explicitly.
4. OpenAI file transcription returns original-language text. Raw audio stays in
   memory and is sent only to the configured OpenAI speech endpoint, not stored
   locally. Provider processing/retention is governed by the provider's terms;
   this is not a zero-retention guarantee.
5. The transcript is persisted before order extraction, so extraction retries do
   not transcribe the same message again. Category and draft creation reuse the
   existing business workflow. Voice drafts carry `voice_transcript_requires_review`.
6. The inbox shows pending/failed/transcribed status, a review warning and a retry
   control for staff/admin/owner. No order is automatically confirmed.

## Server configuration

- Existing `AI_PROVIDER=openai` and `OPENAI_API_KEY`.
- `VOICE_TRANSCRIPTION_ENABLED=true` (default).
- `OPENAI_TRANSCRIPTION_MODEL=gpt-transcribe` (default; separate from the text model).
- Existing WhatsApp app/version and active number connection credentials.
- Install locked Python requirements and apply Alembic migration `0009`.

Disabling voice or having no key keeps the audio message visible for manual review.
Transient provider errors retry with the existing queue backoff; failures stay
visible and can be retried. Transcription is probabilistic: review names, quantities,
addresses and prices, especially noisy or mixed-language notes. Never infer
transcription accuracy from mock tests.

## Verification on 28 October 2026

Backend regression: 128 passed, 3 PostgreSQL-only tests skipped locally.
Tests cover real local WAV and OGG/Opus decoding, multilingual mocked transcripts,
media bounds/checksums/untrusted URLs, tenant isolation, duplicates, durable
transcripts, disabled provider and retry controls. Mixed Sinhala/Tamil/English
invoices use bundled SIL-licensed Noto fonts with shaping.

A real OpenAI transcription request using locally synthesized English speech was
attempted. The provider returned HTTP 429, `credit_balance_exhausted`,
`insufficient_quota`. No client audio or business documents were used. Live speech
acceptance is pending credit availability and real Sinhala/Tamil sample review.

References: https://developers.openai.com/api/docs/guides/speech-to-text
and Meta's official Postman Retrieve Media URL request.

Final web verification: production build and ESLint passed; voice inbox retry/Tamil transcript browser test passed, and existing order/invoice and two website behavior tests passed. Local database backed up and upgraded to 0009; Alembic check reports no schema drift. Mixed-script invoice PDF was rendered and visually reviewed.
