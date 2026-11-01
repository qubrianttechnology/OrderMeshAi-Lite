# Dashboard feature access update

Existing tools now have direct owner/staff sidebar shortcuts and an Overview tool directory. Inventory is labelled **Products & inventory** for product businesses; service businesses retain their own terminology and saved module visibility. Catalog records are independent of analytics/WhatsApp load failures. Product search includes barcode; filtered results paginate at 50 rows. Navigation preserves the selected tab/operation in the URL fragment across reloads. Switching workspaces clears stale catalog filters. Owners of product businesses can reopen a hidden catalog through Products & inventory, using the existing dashboard preferences endpoint.

Catalog entries remain scoped to the selected workspace. The 3,000 synthetic products are exclusively in the separate demo workspace and were not copied into real business catalogs.

# OrderMesh wholesale operations

Implemented 30 October 2026 in `D:\OrderMesh Ai Lite`. The WhatsApp intake / review / approval workflow remains central. **Operations** is an additional dashboard module for non-service businesses with owner/admin/staff access. Advanced functions stay inside this module.

## Daily workflow

1. Register products with a SKU, optional unique barcode, category, selling unit, retail price, optional cost and wholesale price, wholesale threshold and minimum order quantity. Record stock in the same selling unit. No automatic carton-to-piece or vehicle-fitment inference.
2. Maintain customer credit limits, payment terms and retail/wholesale price group from the customer dialog.
3. Use WhatsApp inbox filters and Business Intelligence answers to separate business, personal, spam, support and uncertain messages. Messages are retained. Human approval remains required; the AI never posts sales independently.
4. Review a WhatsApp request in Orders, choose warehouse/pricing and optional discount/tax, acknowledge flags and confirm. Stock is deducted once. The order's invoice is available immediately. Record payment or post approved credit in Operations; this never deducts stock again.
5. For a counter sale, Operations → POS supports product search or barcode scanner keyboard input. Select customer, warehouse, quantities, pricing and payment, review and complete. Stock, order, payment/credit and cost snapshots commit atomically. Download the payment-record PDF.
6. Operations → Purchases: add supplier, create purchase order, then Receive goods / GRN once goods arrive. Receiving twice does not add stock twice. Costs use a weighted average where the prior cost is known; unknown prior cost remains unknown.
7. Warehouses: create a named depot, transfer stock and view balances. Transfers conserve total stock. Sales validate the selected warehouse, not the global stock total. Existing inventory was allocated to Main by migration.
8. Returns: select original order/product, quantity and resellability. Only resellable physical items restock. Credits and tax are cumulatively prorated to the original invoice, including discounts. Refunds cannot exceed customer money paid above the remaining invoice. Outstanding refunds can be paid later in Credit & payments.
9. Credit & payments: record actual cash, terminal card or bank payments, or zero-payment credit posting within the customer limit. Walk-in customers cannot receive credit. Outstanding balances and overdue days are shown. Existing orders without payment history remain explicitly unposted; they are not silently treated as debt.
10. Reports & expenses: date range uses Asia/Colombo, up to 366 days. Revenue excludes tax and includes return credits. Cost snapshots determine profit; missing cost means incomplete profit, not an invented margin. Receipts/refunds and current outstanding balances are separate measures. Expenses can be voided with an audit trail.
11. Delivery: assign an existing workspace member, set a tracking reference and pending/dispatched/delivered/failed status. Delivered marks fulfillment without another deduction. No courier API is invoked.
12. Team: only owners add/change/remove existing registered users. Owner role is protected. Staff can sell, record receipts and manage delivery; purchasing, transfers, returns, refunds, expenses and reports require owner/admin. Viewers retain read-only dashboard access.

## Notifications

The bell refreshes every ten seconds while the dashboard is visible. It includes WhatsApp approvals, service reviews, low/out-of-stock, unread incoming messages, failed processing/sends, overdue payments, failed delivery and expired access. Read status is per user and workspace. Mark all read does not dismiss the underlying business issue; resolved issues leave the active feed. Stock alerts recur after a genuine restock/reduction.

Enable sound or desktop alerts from the bell. Browser permission and a user gesture are required for those optional effects. These are open-dashboard alerts, not a background push service when the browser is closed.

## Money and records

All amounts are integer LKR minor units. Tax defaults to zero and is owner-configured; no legal rate or tax registration is inferred. Card/bank choices record transactions already handled externally; this system does not charge cards or hold card details. PDFs show recorded payments and outstanding/refund amounts, not bank settlement confirmation. These are operational records, not a full general ledger, supplier payable ledger, statutory tax return or bank reconciliation.

Mutation APIs use workspace authorization, organization locking, audit events and idempotency for sales/payments/POs/transfers/returns/expenses. PostgreSQL migration adds forced tenant RLS to all new tenant tables. Local SQLite migration/rollback and tenant isolation are tested; production PostgreSQL execution still requires the disposable PostgreSQL CI checks.

## Isolated demo and AI checks

`OrderMesh Demo Wholesale` contains 3,000 synthetic products across nine wholesale sectors, two sample customers and a supplier. It has its own demo owner, no WhatsApp number and no enabled chatbot. Real catalogues, prices and stock were not seeded or reset. Local credentials are in `.local/demo-access.json`; do not commit or share that file.

- Seed: run `../../.venv/Scripts/python.exe ../../scripts/seed_commerce_demo.py` from `services/api`. It is restricted to local development SQLite and does not reset existing demo transactions.
- Check: run `../../.venv/Scripts/python.exe ../../scripts/check_commerce_demo.py` from `services/api`.
- Results: `.local/demo-readiness-results.json` and `.local/demo-payment-record.pdf`.
- Local English/Sinhala/Tamil/SKU cases passed against 3,000 products. A configured `gpt-6-luna` live request correctly extracted the synthetic English/Sinhala/Tamil test. Human review remains mandatory. These sample checks do not guarantee accuracy for every real message or voice/image.
- Large-catalog model context is limited to grounded local candidates; unknown or excessively broad matches stay in conservative local review. No new real customer chatbot export was enabled. The earlier choice to keep chatbot conversations local remains in force.

## Remaining external acceptance

Real WhatsApp outbound replies / real-number onboarding, Meta business/app review, stable production domain/OAuth configuration, live billing acceptance and production hosting/database validation remain external acceptance tasks. No production deployment or new public tunnel was performed in this work.

## Final validation

- Backend: 176 passed, 3 PostgreSQL-only skipped locally.
- Browser: all 19 Edge cases passed, including POS/GRN/report/notification acknowledgement and mobile layout.
- Ruff, ESLint, TypeScript and isolated Next.js production build passed.
- Migration/seed tests: 4 passed after adding the explicit Main warehouse stock-preservation assertion.
- Synthetic live model and local 3,000-product results are saved in `.local/demo-readiness-results.json`.
- Development API remains bound to `127.0.0.1:8000`; dashboard is `http://localhost:3000/dashboard`. Existing webhook-only proxy/tunnel routing was not expanded to expose the dashboard.
