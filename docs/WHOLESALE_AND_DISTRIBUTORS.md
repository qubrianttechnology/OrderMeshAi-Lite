# Current operational extension

The October 30 commerce update adds retail/wholesale pricing thresholds, MOQ enforcement, POS, supplier purchasing/GRN, warehouse stock/transfers, customer credit/aging, returns/refunds and operational reporting. See [COMMERCE_WORKFLOWS.md](COMMERCE_WORKFLOWS.md) for workflows, permissions and limits. The original focus and baseline below are historical.

# Wholesalers and distributors

OrderMesh now presents its home and signup pages for wholesale and distribution businesses. New workspaces default to the wholesale business type. Existing workspaces keep their selected workflow and data; choose Wholesale / distributor in Business profile to change an existing workspace.

## Sectors

| Category | Example catalog |
| --- | --- |
| Electronics | Phone accessories, chargers, earphones, cables |
| Fashion | T-shirts, shirts, trousers, shoes |
| Beauty | Cosmetics, skincare, perfumes |
| Grocery | Rice, sugar, dhal, spices, snacks |
| Household | Kitchen items, plastics, cleaning supplies |
| Packaging | Shopping bags, food containers, boxes |
| Stationery | Books, pens, files, office supplies |
| Hardware | Electrical items, tools, plumbing accessories |
| Vehicle parts | Car, van, motorcycle and commercial vehicle spare parts |

Other / mixed categories remains available. Set a primary product category in Business profile; choose each product's category independently. Inventory supports category filtering and search by name, SKU, category label and alias/part number. Categories do not grant access to another workspace or change order prices.

## Selling units and vehicle parts

Use a consistent selling unit for stock, unit price and order quantity: piece, set, carton, pack, bag or kg. A carton catalog item with quantity 2 means two cartons; automatic pack-to-piece conversion is not implemented. Quantities remain whole catalog units. Separate SKUs should represent distinct variants or selling units. There is one catalog price per SKU; customer-specific price tiers, MOQ enforcement and trade credit accounting are not implemented by this update.

For vehicle parts, capture exact brand/model and part/OEM numbers in product names or aliases. The AI receives category context and is instructed not to infer fitment, substitute parts or convert packs. This is not a compatibility database. Review exact part, variant, unit, availability and customer intent before confirming.

Business Intelligence can describe trade customer types, order examples, delivery areas and commercial terms. Those descriptions provide context; they do not automatically enforce minimum orders or approve credit.

## Data changes

Migration 0011 adds products.category with an Other default for existing items. It preserves stock, pricing, users, workspace types and orders. The local development database was backed up before migration. No example products were added to business data.

Validation: backend suite 153 passed, 3 PostgreSQL-only checks skipped locally. Migration/model alignment and rollback tests passed, including preservation of an existing product's stock and price. All 16 Edge browser cases passed across the full run and a corrected marketing assertion rerun. Production build, frontend lint/TypeScript and backend Ruff passed. Desktop/mobile layouts and the vehicle-parts catalog were visually reviewed.
