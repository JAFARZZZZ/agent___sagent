# Unified shopping workspace

The customer route `/` now has one persistent composer and an RTL red/white conversation timeline. The same input switches between AI and deterministic keyword retrieval; service failures offer a direct-search action, never invented results. The existing seller admin route is retained.

Shared session preferences power inline keyword chips, budget/category filters, manual coordinates, optional user-initiated geolocation and radius. `PUT /api/sessions/{id}/preferences` updates the existing session, preserves history and clears incompatible confirmation selection. Filters refresh current offers and map markers together. Previous result blocks are labeled historical. Local selection supports product and seller comparisons. Product image URLs come from source records, accept HTTP(S) only, and use a neutral fallback on failure.

Leaflet 1.9.4 and the OFL-licensed Vazirmatn regular font are bundled in `frontend/vendor` with licenses. Map tiles default to attributed OpenStreetMap; configure `MAP_TILE_URL` and `MAP_ATTRIBUTION` for a production provider appropriate to expected traffic. Map markers are grouped by shop ID and drawn only from current offers with valid coordinates. Clicking a map position explicitly updates the session location. Missing-coordinate offers stay in unfiltered lists. No route times are inferred.

Seller requests and shopping plans render within the timeline. Status refresh is explicit via a button, not background polling. Alternatives are actionable. The map remains inline on both desktop and mobile; filter controls use a modal/bottom sheet.

## Validation and limits

`python -m scripts.chat_ui_smoke` uses actual Chrome against port 8002 and real backend records. It checks one composer, product/offer cards, budget add/remove, same session ID, map marker presence, marker/list filtering synchronization and horizontal overflow at 1280 and 390 widths. Screenshots are local in outputs/evaluation/chat-ui. All 27 backend tests pass (22.135 seconds). Map tiles did not render in the captured browser environment; local map controls and real marker data did load. A fully rendered basemap is not verified. No frontend build or lint/type configuration exists for this plain-JavaScript application.

Not validated live: OpenAI interpretation (previous provider timeout persists as an unresolved issue), external tile availability, every remote product image, geolocation permission outcomes, all-category visual coverage. Product comparison and seller-confirmation APIs remain covered by existing tests; the redesigned versions of those UI interactions need expanded browser coverage. This is not a claim that all 12 requested browser scenarios passed. Refresh restores server conversation text/preferences, not historical structured carousel DOM. Installment/brand/specification filters are not shown because backend enforcement is not implemented. AI explanations and automatic response polling remain incomplete.
