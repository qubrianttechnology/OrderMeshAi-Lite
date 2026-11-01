# Hell Mart: real business setup

Target confirmed by the owner on 31 October 2026: **Hell Mart**. This existing retail workspace is not marked as a demo. It currently has no products, customers or connected WhatsApp number. Orders, POS, inventory, reporting and business setup modules are already available.

## Use the real workspace

Sign out of the separate Demo owner account and sign in with the email/password used to create Hell Mart. Its existing owner uses password sign-in; a Google identity is not currently attached to that account. Select Hell Mart if multiple workspaces are offered. Do not use `.local/demo-access.json` for real business operations.

Complete Business Intelligence and add genuine products, unit costs, selling prices and opening stock in Products & inventory. The 3,000 synthetic products remain isolated in OrderMesh Demo Wholesale; they were not copied or reclassified as real stock. No user permissions, passwords, invoices or business records were reset.

## Live WhatsApp prerequisites still missing

1. The owner confirms only a Meta test number is available. The existing +1 555 152-1646 connection belongs to Qubriant Technology, not Hell Mart. A real business number must be added/verified and explicitly connected to Hell Mart. Do not move the existing test connection or delete an existing WhatsApp Business app account as a shortcut.
2. Read-only Meta verification on 31 October returned HTTP 401, code 190/subcode 463 for the configured test credentials. Those credentials are not currently accepted; refresh the appropriate token through Meta and keep it only in the app's credential configuration/connection flow, never in chat.
3. Embedded Signup needs a valid allowed HTTPS dashboard origin. The existing public test setup exposes only the WhatsApp webhook; it is not permission to expose the dashboard. A stable hosting/domain setup or separately approved HTTPS testing origin is still needed for that browser signup flow.

After real-number verification, use the existing Hell Mart Settings → Connect WhatsApp flow and validate routing, a newly received message and an authorized reply. Enable unrestricted live sending only after the real connection and credentials are verified. Changing a local test flag does not turn Meta's test number into a production number.

## Configuration preserved

WhatsApp test restrictions remain enabled while only the test number is available. PayHere sandbox and local development database settings were not promoted to production. No outbound WhatsApp messages were sent. Local chatbot conversation processing remains local under the owner's earlier privacy choice.
