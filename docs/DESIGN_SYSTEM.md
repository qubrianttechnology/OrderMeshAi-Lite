# OrderMesh shared visual design

Updated 27 October 2026 in D:/OrderMesh Ai Lite.

The home page, authentication, dashboard and inbox use app/design-system.css.
The palette is warm white, slate and muted teal. Controls share typography,
borders, corner radii and focus treatment. Dark mode uses restrained charcoal
and sage rather than luminous gradients.

Legacy layout rules are isolated in the legacy cascade layer. Every stylesheet
declares the same layer order before its rules to keep client navigation and
production CSS chunks consistent. New visual work belongs in the design layer.

Landing: split hero, contained image carousel, organized feature cards and a
clear monthly plan. Auth: a consistent brand panel and focused form card.
Workspace: consistent surfaces, readable field labels and restrained controls.

Motion: short card lifts, staggered metric entry and one-time section reveals.
Reduced-motion preferences disable transitions and reveal offsets. Keyboard
focus remains visible. Existing forms, routes and provider integrations remain
functional.

Verification: isolated Edge desktop/mobile checks cover home, sign-in, sign-up,
dashboard and inbox, including overflow and typography. Existing landing and
order workflow browser checks passed. Visual captures are in apps/web/test-results.
Source backups are in .local/design-before-professional.
