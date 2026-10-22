# Torob in-store shopping assistant

Persian RTL shopping interface backed by FastAPI and the complete local Torob catalog. The web agent uses the official OpenAI Responses API with validated catalog tools and persistent conversation. The existing phone CLI remains available separately.

## Enable the web agent

Install the updated requirements, then add `OPENAI_API_KEY` and `OPENAI_MODEL` to the project's `.env`. Choose a model available to your account with Responses function calling support. Restart Uvicorn. The application now reads `.env` automatically; existing shell variables take precedence. Never put API keys in frontend files. `OPENAI_BASE_URL` is optional and defaults to OpenAI. Timeout, tool round and output token limits are documented in `.env.example`. The seller secret accepts `SELLER_DEMO_SECRET` or the existing `SELLER_TOKEN`.

The new chat panel creates a session automatically. Product results appear as existing interactive cards. Manual search remains available without AI configuration. Live model validation has not been performed because this project's environment does not contain OpenAI credentials/model configuration. See [implementation status](IMPLEMENTATION_STATUS.md) and [agent architecture](docs/agent_design.md).

## Run

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m scripts.prepare_data
$env:SELLER_TOKEN = 'your-long-private-random-token'
.venv/Scripts/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open http://localhost:8000. The initial startup builds a persistent FTS5 index. API docs: `/docs`; health and counts: `/api/health`. Existing imported databases can be reused without rerunning the importer. Never rebuild the catalog while the app is running: the importer replaces the database, including shopping sessions.

Source files: `data/products.csv`, `data/shops.csv`, `data/offers.csv`. Import preserves source payloads and IDs; malformed or duplicate records and broken references abort the build. It does not silently truncate the catalog. Existing profiling is in `reports/` and `notebooks/01_data_and_search.ipynb`.

## Implemented

- Dynamic category discovery, Persian character/digit normalization, indexed prefix lexical search, budget filters and pagination.
- Product specifications comparison, actual product–offer–shop joins, optional manual coordinates and radius filtering.
- Persistent shopping sessions and confirmation requests; authenticated simulated seller response panel.
- Independent inventory, price and visit responses; same-product alternative offers respecting stored budget and geographic filters.
- Shopping summary, expiry flag after one hour, address and external map navigation.
- Responsive Persian interface, validation errors, empty states and loading text.

## Validation

Core repair smoke test: `.venv/Scripts/python -m scripts.smoke_test`.
Actual browser test (requires `pip install playwright` and installed Chrome; start the app on port 8001): `.venv/Scripts/python -m scripts.browser_smoke`.
Opt-in live provider test: `.venv/Scripts/python -m scripts.test_live_ai` (uses configured credentials and may incur API usage). See `DEBUGGING_REPORT.md` for actual outcomes, including the live-provider timeout.

`.venv/Scripts/python -m unittest discover -s tests -v`

The web integration test requires the actual imported catalog and tests three dynamically selected categories. It removes its own sessions. Original unit tests use small explicit fixtures.

## Deployment

Set `SELLER_TOKEN` in the shell/environment, then `docker compose up --build`. Import the data first. The data directory is a persistent volume. Use HTTPS at a reverse proxy; do not expose the seller token. `.env` is read by both Compose and the Python application. `CATALOG_DATABASE` can override the SQLite path. No hosted deployment is provisioned.

## Current limitations

This is **not completion of the master specification**. SQLite is used instead of PostgreSQL/PostGIS. The new web agent plans via Responses function calls over lexical retrieval; interpretation quality is not yet evaluated against a live model. The legacy CLI remains phone-specific. No semantic retrieval, required-attribute parser, installment filter, configurable ranking, embedded map, similar-model fallback, image rendering or live polling is implemented. Compare uses raw dynamic specifications. All offers remain discoverable including uncertain prices. No live inventory or real seller communication is available. Session IDs are bearer capabilities; production account access control, concurrency and abuse protection remain work. Browser QA, hosted deployment and expanded profiling reports remain incomplete. See IMPLEMENTATION_STATUS.md for detailed agent limitations.

## Demo

Select any populated category, search, choose two products for comparison, then view sellers. Optional coordinates restrict results to a radius. Request simulated confirmation, open the seller panel with the configured token, mark unavailable, and return to the shopping summary. Inspect same-product alternative count. Repeat for a different category. All results come from the database.
