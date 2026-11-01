# Business-specific dashboards

Implemented in D:/OrderMesh Ai Lite, 28 October 2026.

## Configure a workspace

1. Settings -> Business profile: choose the business type, fill its offerings, customers, workflow, hours, payments and delivery details, then save.
2. Settings -> Your dashboard: choose visible sections and Save dashboard layout.
3. Use business recommendations clears custom module selection; defaults then follow the current business type.

| Business | Recommended sections | Vocabulary/workflow |
| --- | --- | --- |
| Retail, wholesale, online store | Orders, customers, catalog | Products, inventory, order review and invoices |
| Restaurant / bakery | Orders, customers, catalog | Menu; existing product/order workflow |
| Agency / software | Service requests, customers, catalog | Project requests, clients, services |
| Services / salon | Service requests, customers, catalog | Service requests, customers, services |
| Repair / maintenance | Service requests, customers, catalog | Repair requests, customers, services |
| Hybrid | All four sections | Product and service workflows |

WhatsApp inbox, AI assistant, Overview and Settings remain available. Owners and admins can customize; staff and viewers can see the selected layout but cannot change it. Sidebar and overview module cards use the same preferences. Hidden modules retain records and existing API role permissions. This is a display preference, not an authorization control.

Service businesses use tenant-scoped service-request counts (pending review, accepted and completed), not order totals presented as project metrics. Active service counts come from the actual catalog. Returning to Overview refreshes these counts. Salon and repair messages use the existing human-reviewed service extraction workflow, and new catalog items default to not tracking stock. Changing business type does not rewrite existing product stock settings or delete orders.

Preferences are stored under the existing organization's business_profile JSON; no schema migration is needed. Custom selections survive profile edits and organization reloads; automatic recommendations follow a later business-type change. No credentials are stored in preferences.

## Boundaries

This update does not add a reservation calendar, automatic bookings, restaurant kitchen operations, courier integration, full project management, arbitrary customer schema fields or POS. Service requests can capture appointment preferences, budget and deadline for human review. AI accuracy and live WhatsApp connectivity still require provider acceptance checks listed in COMPLETION_STATUS.md.

## API

- GET /api/dashboard-preferences: effective modules and business labels.
- PUT /api/dashboard-preferences: modules array or null to restore recommendations; owner/admin only, tenant-scoped and audited.
- GET /api/dashboard-service-summary: tenant-scoped service-request aggregates.
- GET /api/auth/me: each accessible organization includes its effective dashboard configuration.

Validation evidence is recorded in COMPLETION_STATUS.md after the final checks.
