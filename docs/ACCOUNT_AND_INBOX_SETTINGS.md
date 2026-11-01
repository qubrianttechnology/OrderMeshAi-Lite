# 31 October 2026: profile, basic settings and inbox management

Settings now starts with a personal profile (name, phone and private JPG/PNG/WebP profile photo) and owner/admin business basics (workspace name, contact email/phone and address). Photos are validated, resized and stored privately. Sign-in email, actual business type, currency and report timezone are informational. Business Intelligence remains a dedicated section; the business setup shortcut opens it. Existing subscription setup remains under Business workflow & subscription.

Settings > Your dashboard > Layout offers Recommended or Full business dashboard. Qubriant's software/service workflow differs from the wholesale demo by design. Full layout exposes sales/profit charts, inventory and operations alongside service requests without changing business type or AI extraction workflow. Existing workspace layout choices were not changed automatically.

WhatsApp inbox supports Active/Unread/Archived/All views, pin/unpin, archive/unarchive and mark read/unread, preserving existing category/search/reply/customer-linking controls. Background polling does not clear unread markers. New incoming messages reopen archived chats. Inbox management is scoped to the current workspace and owner/admin/staff; viewers cannot manage chats.

Migration 0015 was applied to the local development database after SQLite backup. Existing user/workspace/product/conversation/message counts were preserved; local API and dashboard health returned HTTP 200. No new public tunnel, real outbound WhatsApp send, production-mode switch or external chatbot data sharing was introduced.

Validation: 181 backend tests passed; 3 PostgreSQL-only tests skipped. Five distinct Edge browser workflows passed across final targeted runs: profile/photo/basic settings/full layout; inbox management; category filters/search; WhatsApp order approval/local chatbot settings; service-business profile/catalog/layout. Frontend lint, TypeScript and production build passed. Desktop/mobile settings preview loaded, with no horizontal page overflow at 390px. Screenshots: `.local/account-settings-desktop.png`, `.local/account-settings-mobile.png`.


