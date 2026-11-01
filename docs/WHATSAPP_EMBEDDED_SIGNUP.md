# Dashboard WhatsApp connection

Implemented 27 October 2026 in `D:\OrderMesh Ai Lite`.

## Current verified state

- Settings and WhatsApp Inbox include Connect WhatsApp.
- Official Facebook JavaScript SDK opens the configured Embedded Signup code flow.
- Server binds an expiring, single-use attempt to workspace, signed-in user and session.
- Code exchange validates token app identity, expiry, WhatsApp scopes and shared WABA
  target IDs. If granular target metadata is absent, the SDK completion WABA ID is
  only a hint: the validated grant must successfully fetch that account and its phones
  from Meta. An unshared account is rejected. Phone choices come from Meta.
- Confirmation rechecks phone membership and Business App coexistence status with Meta.
  Coexistence does not call register/deregister. Cloud API registration requires a
  six-digit PIN, then the app subscribes to the selected WABA webhook.
- A global unique phone reservation prevents concurrent cross-workspace assignment.
- Phone access tokens are encrypted with Fernet in server-side storage. Temporary
  credentials are erased after successful/failed connection and expired attempt access.
  APIs never return a token or App Secret. Reply sending uses the connected number's
  own encrypted credential, retaining customer-service window and test-recipient checks.
- Manual ID registration is development-only; production uses verified signup.
- Migration 0008 applied locally after a SQLite backup; schema comparison has no drift.

Provider calls and browser SDK responses are mocked in automated connection tests.
A real Meta popup/phone connection, webhook delivery and customer reply are NOT yet
verified. Do not present the completed local tests as production Meta approval.

## Remaining owner/Meta steps

1. Temporary public HTTPS was explicitly approved by the owner and started on
   27 October 2026. Sign-in, API health, webhook challenge and unauthorized-record
   denial passed public checks. The earlier review rejection is resolved by that
   explicit approval. New registrations are disabled while this test is running.
2. Set APP_ORIGIN to the secure dashboard origin and WHATSAPP_PUBLIC_CALLBACK_URL to
   that origin plus /webhooks/whatsapp. The Next server proxies this exact webhook
   path to the API; it is protected by verification token and signed POST checks.
3. In Meta, allow the exact HTTPS dashboard domain for the JavaScript SDK / Facebook
   Login for Business. Enable SDK login as required by the Meta settings screen.
4. Configure the WhatsApp callback URL and copy WHATSAPP_VERIFY_TOKEN directly from
   services/api/.env into Meta. Do not send the secret in chat. Subscribe messages.
5. Restart OrderMesh, open the HTTPS dashboard and sign in. Google OAuth on a new
   hostname requires that hostname's callback to be authorized in Google Cloud; the
   existing localhost Google redirect is not automatically valid on a tunnel.
6. Enter the business number and click Connect WhatsApp. Complete the Meta business/number
   authorization. The matching verified number connects automatically and opens the inbox.
   If popup blocking occurs, allow the popup and use Continue with Meta. Cloud API numbers
   may require a registration PIN; eligible Business App coexistence skips that step. For an
   existing Business App number, use Meta's coexistence option if eligible. Never
   delete the phone's WhatsApp account to try to force coexistence.
7. Send a real customer inquiry and verify categorization, draft, request review and
   reply delivery. WHATSAPP_TEST_MODE remains enabled: explicitly allow test recipients
   before reply testing, or disable it only when intentionally enabling live recipients.
8. Complete Meta Business Verification and App Review/Access Verification before
   onboarding ordinary clients. Testing accounts may require manually assigned app roles.

Current IDs: App 1609244170127322; configuration 1450204687306079.
API Graph version is pinned to v26.0, matching the user-supplied Meta example.
App Secret, webhook verification token and connection encryption key are API-only.
Back up META_CONNECTION_ENCRYPTION_KEY securely: changing/removing it makes saved
connections unreadable. No secrets belong in NEXT_PUBLIC variables or source control.

## Temporary HTTPS limits

Cloudflare Quick Tunnels use a changing hostname, have no uptime guarantee and do
not support SSE. The inbox switches to five-second polling on trycloudflare.com.
A public tunnel makes the application's public routes reachable on the internet;
customer records still require authentication. It is for testing, not production
hosting, and stops when the tunnel process stops. The temporary tunnel is currently running with owner approval.

References:
- https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/implementation/
- https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api
- https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/

Current temporary dashboard: https://descending-readers-objects-expression.trycloudflare.com/sign-in
Current webhook callback: https://descending-readers-objects-expression.trycloudflare.com/webhooks/whatsapp

Run `./Stop-OrderMeshHttps.ps1` when testing finishes. It verifies the saved PID,
start time and executable, stops only that tunnel and restores pre-tunnel origin,
callback and registration settings before restarting OrderMesh. Settings edited
subsequently are preserved. Google callback is now configured for the temporary domain; authorize the exact
HTTPS callback in Google Cloud before Google login. The stop script restores the
previous localhost callback.

Google OAuth update: app redirect/state/PKCE checks passed on the public URL.
Add this exact authorized redirect URI in the existing Google Web OAuth client:
https://descending-readers-objects-expression.trycloudflare.com/api/auth/google/callback
Google consent/token exchange is pending the owner completing a real login.

Live test follow-up: the Meta app credential check succeeded (HTTP 200, app token issued; token not logged). The dashboard reached begin (201), but a prior exchange returned 502 and no number is connected yet. Safe stage/HTTP/numeric Meta error diagnostics are now available without logging credentials or provider bodies. A fresh owner-initiated Meta authorization is pending to identify the failed stage. The app credential check does not prove client WABA permissions or App Review approval.

Meta exchange follow-up: live provider diagnostics identified HTTP 400/code 100/subcode 36008. The official SDK was inspected in an isolated, unsigned-in browser: its popup uses a dynamic staticxx.facebook.com/x/connect/xd_arbiter callback. The frontend now preserves that exact URI from the synchronous SDK popup call and restores window.open immediately; the server validates the official host/path and passes the URI unchanged during exchange. Provider HTTP 400 errors now return application HTTP 422 so validation details are preserved. Eight Meta backend tests passed, including exact binding and untrusted callback rejection. A fresh owner authorization remains necessary to verify the fix with a real Meta code. No authorization codes or tokens were logged.


## Number-first connection update

The owner requested entering a number followed by Connect. The dashboard now sends
that number with the expiring attempt, launches Meta and captures its completion
account hint. The backend matches the requested number against authoritative Meta
phone details before allowing connection. Sri Lankan 0-prefixed numbers normalize
to +94; other countries should use their international country code.
The initial Connect action authorizes workspace linking; Meta approval remains
mandatory. A single matching Business App number connects automatically. Cloud API
registration requests its six-digit PIN only when needed. Success opens the inbox.
New messages use the existing signed webhook and tenant routing; old chat history
is not automatically imported by this change.

The owner reported that token exchange progressed to missing WABA target metadata.
Completion-event capture and server-verified account discovery address that path;
a new real owner authorization/message test is still required. Automated provider
and browser tests use synthetic data and do not prove a live WhatsApp connection.

Final regression checks: backend 105 passed; 3 PostgreSQL-only checks skipped
because this local environment uses SQLite. TypeScript, ESLint and Ruff passed.
Restarted API/dashboard and verified public /api/health and /sign-in return HTTP 200.
Browser connection checks: 2 passed in Edge (automatic Business App connection
and Cloud API registration PIN fallback), using synthetic Meta responses.


## Current session: 27 October 2026

Previous descending-readers tunnel expired. Current temporary origin:
https://ought-puzzles-darwin-optimization.trycloudflare.com

SDK allowed domain: the origin above, without webhook path.
Callback: https://ought-puzzles-darwin-optimization.trycloudflare.com/webhooks/whatsapp
Google callback: https://ought-puzzles-darwin-optimization.trycloudflare.com/api/auth/google/callback
Copy WHATSAPP_VERIFY_TOKEN from API .env into Meta only. Subscribe messages.

Popup reserved directly on Connect, before awaiting the server attempt. The
reserved window navigates to the official SDK URL; async processing runs behind
a normal SDK callback. Developer tools are collapsed for owners/admins.

Public health and sign-in HTTP 200; public invalid webhook token rejected (403).
Actual verification token checked against localhost only. Approval review rejected
sending the private token through the public tunnel from the diagnostic client;
that action was not executed. Live connection awaits owner Meta configuration,
number authorization and real inbound message delivery. No live success claimed.


Owner screenshot confirms Business Verification and App Review/Access Verification
remain incomplete, while Integrity is cleared. Ordinary client production
onboarding cannot be claimed ready until those Meta requirements are approved.
App-role testing is distinct and does not establish production approval. The
missing account-selection response alone does not identify which configuration
or eligibility issue caused the popup to omit WhatsApp selection.
