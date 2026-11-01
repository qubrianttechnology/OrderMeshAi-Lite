# Dashboard business performance charts

Overview now includes Profit vs sales, Gross profit, Low stock items, Top selling products and Staff performance, arranged in a responsive main grid with a smaller right column. Navy sales bars, restrained orange profit lines and horizontal bars follow the reference direction. Existing sales trend and business tools remain available; tools now follow the performance area.

## Definitions

- Period: last 7, 30 or 90 days, inclusive of today in Asia/Colombo.
- Financial sales: non-cancelled orders posted by recording a payment or approved credit. Sales exclude tax and subtract return credits issued in the selected period. Unposted orders are explicitly excluded.
- Gross profit: net sales minus sale-time cost snapshots, with resellable returned cost restored. Missing cost produces an incomplete value/gap rather than a guessed margin. Net profit also subtracts non-voided operating expenses.
- Trend: up to ten consecutive date groups. Gross profit is unknown for a group with missing costs. Negative values are supported; a zero baseline is shown. Native chart tooltips and an expandable data table provide readable values and keyboard access.
- Top products: ranked by net quantities sold in each SKU's catalog unit after returns; tax-free, discount-adjusted sales value is shown. Quantities do not convert packs, cartons or pieces. Integer revenue allocation preserves rounding cents.
- Low stock: current active tracked products at/below reorder point, independent of the selected sales period. Links open the existing product/stock screen.
- Staff: attributed to the account that originally recorded the order. Posted sales and return credits use financial posting/return dates. Fulfillment counts reflect current status of non-cancelled orders created in the period; it is not a subjective employee rating. Names are actual workspace transaction participants, without fabricated avatars or percentages.

Financial panels and their read-only endpoint `/api/commerce/dashboard-insights?days=30` require owner/admin access. Existing staff/viewer inventory and normal dashboard access are unchanged. No schema changes or external services were added. Data refreshes every 30 seconds while the page is visible, with a manual refresh and isolated error state.

## Validation

Backend: 178 passed, 3 PostgreSQL-only skipped locally. New checks reconcile daily/summary financial totals, returns, expenses, unknown costs, staff attribution, period validation and tenant/role isolation. Three targeted Edge browser cases passed: business charts, commerce workflow and feature navigation. Production build and frontend lint/TypeScript checks were run for this update. Local synthetic demo screenshots are saved under `.local/dashboard-business-charts*.png`.
