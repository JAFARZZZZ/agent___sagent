# Debugging report — 2026-10-22

## Reproduced defects and corrections

1. **Offer price mapping**: direct retrieval of `product_9106e7ac3baeb6ea64c58c85` returned 105 offers but `price_toman` was a string. `payload` overwrote validated database columns in both record and offer retrieval. `backend/catalog.py` now gives typed database fields precedence and preserves the source string separately as `source_price_toman`. Smoke checks compare every returned sample offer price against SQL, with exact equality.
2. **Agent results disappear**: tool results over 30,000 characters were replaced with a warning before being added to UI components. This could erase actual listings from large search/offer responses. `backend/agent/orchestrator.py` now preserves complete UI components and trims only model context. A regression test executes the loop with an oversized result and asserts preservation.
3. **Disconnected agent offers**: `get_product_offers` responses rendered only as expandable JSON, without the existing confirmation action. `frontend/app.js` now uses the same offer-card renderer for manual and agent results. Agent-generated cards themselves were not live-model tested because the provider timed out.
4. **Dead-end alternatives**: shopping plans displayed only the number of alternative offers. A working button now renders those actual offers with confirmation actions. Actual Chrome test submitted unavailable through the seller panel and opened 104 alternatives for a 105-offer product.
5. **Stale comparison selection**: new manual searches retained selected IDs from prior results. Starting a new manual search now clears that selection.

## Runtime and data evidence

Started `uvicorn backend.app:app --host 127.0.0.1 --port 8001`: successful startup, no missing table/import errors. Working tree was clean before edits. No source data, credentials, or user environment files were changed.

Fresh streaming CSV counts exactly match SQLite:

| Entity | CSV | SQLite |
|---|---:|---:|
| Products |225903|225903|
| Shops |6476|6476|
| Offers |331506|331506|

Foreign-key check returned no violations. Category API totals sum to all products. CSV schemas and actual sample IDs are saved in `outputs/evaluation/smoke_report.json`. No incomplete import was reproduced, so the importer was not rebuilt. Prices are source toman, not rial conversion. Missing-price offers remain visible without a budget constraint; budget constraints require known parsed prices.

Examples: `product_9106e7ac3baeb6ea64c58c85` (105 offers), `product_a984d858a7dbfd86b7c8f56b` (105), `product_0c76a59f5c71858dcd82a678` (88). Each was found using its actual complete Persian title. All associated offer/shop IDs and prices were checked against direct SQL. Additional actual brand, English-model, mixed-language and nonexistent queries and disjoint pagination were executed. Existing tests cover additional categories and geographic boundaries.

## Executed tests

- `.venv/Scripts/python -m scripts.smoke_test`: PASS, source/database counts, health/categories/search/details/offers APIs, typed prices, joins, pagination, seller response and alternatives.
- `.venv/Scripts/python -m unittest discover -s tests`: **26 passed**, 19.463 seconds.
- `.venv/Scripts/python -m scripts.browser_smoke`: PASS using installed Chrome, actual HTTP API, widths 1280 and 390. Exact search, all 105 offer cards, seller-panel unavailable response, updated customer plan and 104 actionable alternatives. No page errors or horizontal overflow. Screenshots under `outputs/evaluation/browser/`. Browser used the running server for UI workflow; corrected price types separately verified by fresh-process API smoke tests.
- `.venv/Scripts/python -m scripts.test_live_ai`: **FAIL**, both sandbox and network-escalated runs. `APITimeoutError` after approximately 45 seconds, zero tokens, no tool calls. Configuration is present; compatibility/authentication cannot be concluded from a timeout. Provider details and credentials are not logged. Actual live tool use remains unverified, rather than marked successful.

## Remaining issues (priority order)

1. Live provider connectivity/latency must be resolved; this run did not reproduce a successful OpenAI response.
2. Browser coverage is intentionally limited: broad-category, geographic-input and live AI journeys were not browser-tested. Geography is covered by deterministic tests. No claim of exhaustive category quality or every endpoint is made.
3. Search still sorts by product ID and uses prefix AND matching; relevance ranking, typo handling, and exact-variant guarantees remain absent. No evidence justified replacing the search engine in this repair.
4. Standalone store-search and store-comparison REST routes remain absent (comparison exists as an agent tool). Customer account controls, concurrent-session safety, and automatic polling remain incomplete.
5. The importer replaces the database including sessions; do not run it against the active application. No importer changes were necessary for the observed complete dataset.

Git remote is not configured, so pushing is unavailable. Screenshots are local artifacts; no secrets or large raw data are staged.
