# Torob in-store shopping assistant

Persian RTL shopping interface backed by FastAPI and the complete local Torob catalog. The existing phone CLI remains available; the new web catalog supports every dataset category.

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

`.venv/Scripts/python -m unittest discover -s tests -v`

The web integration test requires the actual imported catalog and tests three dynamically selected categories. It removes its own sessions. Original unit tests use small explicit fixtures.

## Deployment

Set `SELLER_TOKEN` in the shell/environment, then `docker compose up --build`. Import the data first. The data directory is a persistent volume. Use HTTPS at a reverse proxy; do not expose the seller token. `.env` is read by Compose, not by the Python application. `CATALOG_DATABASE` can override the SQLite path. No hosted deployment is provisioned.

## Current limitations

This is an initial functional web baseline, **not completion of the master specification**. SQLite is used instead of PostgreSQL/PostGIS. Web search is lexical, not an LLM natural-language planner; use concise product terms and explicit filters. The legacy AI CLI remains phone-specific and is not connected to the web UI. No semantic search, use-case interpretation, attribute constraint parser, installment filter, configurable store ranking, embedded map, similar-model fallback, image rendering, or live polling is implemented. Compare uses raw dynamic specifications and does not infer missing values. All offers remain discoverable including uncertain prices; original price-quality flags should be reviewed. No current inventory or real seller communication is available. Session IDs are bearer capabilities stored locally; production account access control and abuse protection remain work. Browser visual QA and cloud deployment remain unverified. Required expanded profiling notebooks/reports are not yet complete.

## Demo

Select any populated category, search, choose two products for comparison, then view sellers. Optional coordinates restrict results to a radius. Request simulated confirmation, open the seller panel with the configured token, mark unavailable, and return to the shopping summary. Inspect same-product alternative count. Repeat for a different category. All results come from the database.
