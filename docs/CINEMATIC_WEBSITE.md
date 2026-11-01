# OrderMesh cinematic public website

Implemented 28 October 2026 in the existing Next.js application. No API, authentication,
database, billing or dashboard implementation was changed. No environment values
were read or modified. The previous landing source is backed up under
`.local/cinematic-backup/`.

## Experience

- Midnight, blue and violet identity with original CSS/SVG product interfaces,
  light comparison and solutions sections, and the existing layered brand mark.
- Six-scene, 13.2-second phone-to-draft product film, scene controls, pause,
  offscreen/hidden-tab timer suspension, reduced-motion and server-rendered fallback.
- Sticky four-step conversation-to-order story, section reveals and desktop
  pointer-responsive lighting. All actual orders still require human confirmation.
- Local deterministic text demonstration with clothing, grocery and Sinhala samples,
  unknown-message handling, missing-detail review, reset and fictional confirmation.
  It makes no provider calls, stores no input and sends no WhatsApp messages.
- Interactive dashboard tabs, order filters, business-type selector, concept motion
  previews, eight FAQ accordions, pricing, security explanation and contact links.
- Mobile navigation, keyboard controls, visible focus, skip link and responsive
  dashboard presentation. No new dependencies, fonts or large media downloads.
- English marketing copy, existing Sinhala examples marked with `lang="si"`;
  navigation, workflow, FAQ and example content are grouped for future localization.
  Full Sinhala website translation is not included.

## Claims checked against implementation

| Capability | Website treatment | Source |
|---|---|---|
| English / Sinhala text extraction | Available with catalog matching and human review | `services/api/app/extraction.py`, `ai_provider.py` |
| Customer, inventory, order and activity management | Available | `services/api/app/main.py` |
| WhatsApp inbox and team replies | Setup and live verification required | `whatsapp.py`, `meta_signup.py`, `docs/LOCAL_SETUP_STATUS.md` |
| Fully automatic customer replies | Not available in this release | Existing WhatsApp/manual reply flow |
| Images and voice | Explicitly unavailable; animations are concept previews | `extraction.py`, integration status and local setup documentation |
| Starter / existing Lite subscription | LKR 7,400 monthly, 15-day trial, default 500 orders monthly | `billing.py`, `models.py`, order allowance enforcement in `main.py` |
| Growth and Business Pro | Planned, no prices/entitlements/checkout invented | No configured tiers found |
| Recurring payments | Implemented; gateway configuration and verification required | `billing.py`, local setup documentation |

No testimonials, customer counts, growth metrics, certifications, social accounts or
uptime guarantees were fabricated. Contact information was retained from the existing
landing page. Preview business records are explicitly fictional.

## Remaining publication inputs

- Supply final approved privacy policy and commercial terms. `/privacy` and `/terms`
  currently give factual product information and explicitly state that final policies
  have not been supplied; they do not invent retention periods, refund terms or rights.
- Configure and verify live Meta and payment-provider flows before marketing them
  as live. This redesign does not change their setup or enable real transactions.
- Define real Growth / Business Pro plans before adding prices or purchase links.
- Hosting and deployment are unchanged; work was performed in the local project.

## Verification

Production build and TypeScript pass. The existing application browser checks passed
for desktop/mobile design, registration, catalog, customer setup, Sinhala extraction,
order confirmation, invoices, service workflows, provider-mocked WhatsApp setup,
Google sign-in entry without JavaScript, and HTTPS-origin proxy behavior.

The new `tests/cinematic.spec.ts` verifies the local demo, Sinhala sample, unknown
messages, empty input, manual example confirmation, dashboard filtering, solutions,
FAQ, pricing, anchor targets, auth entry points, policy routes, scene progression,
pause/reduced motion, and no horizontal overflow at 1440, 768, 390 and 320 pixels.
All tests passed across the regression run and focused rerun (11 distinct tests).
Real Meta messaging and real payment transactions were not exercised.

Production preview was also inspected in Edge at desktop, tablet and phone sizes:
no browser console errors and no horizontal overflow. Preview screenshots are in
`docs/screenshots/cinematic-*.png`. The favicon reuses the original layered brand
mark as a lightweight SVG.
