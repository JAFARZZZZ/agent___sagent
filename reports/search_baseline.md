# Phone Search Baseline

## Implemented

- Read-only SQLite search restricted to the mobile-phone category.
- Unicode normalization, Arabic/Persian letter normalization, decimal digit normalization, and exact word/model token matching.
- Non-capacity query tokens must match product title/model/brand metadata and the seller title. Explicit capacity requests require matching storage evidence in both titles.
- English and Persian GB/TB aliases are normalized, including decimal digits and attached units. TB converts to 1024 GB for matching. Bare numbers remain lexical terms.
- Hard inclusive budget and radius filters. Prices must be screened and positive; coordinates must be present.
- Haversine straight-line distance. It does not estimate road travel time.
- Stable ordering by price, distance, and offer ID. All matching offers are filtered before applying the result limit.
- Source product, offer, and shop IDs are returned separately. No variant deduplication is attempted.
- Inventory is unknown, price is recorded and unverified, and variant status requires review.

## Run

```powershell
python scripts/search_catalog.py A55 --budget 100000000 --lat 35.7 --lon 51.4 --radius-km 10
python -m unittest discover -s tests -v
python -m scripts.evaluate_search
python scripts/build_analysis_notebook.py
```

Open notebooks/01_data_and_search.ipynb to inspect executed outputs and edit search parameters. The notebook combines baseline counts, category analysis, price-screening counts, live queries, and evaluation summaries. The Python modules own reusable logic; Markdown files retain stable decisions and contracts.

## Validation and Limits

Fifteen unit/integration tests cover preparation, search, unit aliases, RAM/storage separation, and condition hints. The 20-case real-data evaluation checks constraints. Seven A55 offers have assistant-reviewed development labels in relevance_review.json: six positive 256 GB examples are retrieved and the 128 GB negative is excluded. This is not independent human review or a held-out relevance benchmark.

The A55 query with a 100,000,000 toman budget and 10 km radius around (35.7, 51.4) returned three offers in the current export. Inspected titles include used/stock condition; matching a model alone does not mean the item is new. All source titles remain available in the response.

The explicit A55 256GB query now retrieves six offers at a 200,000,000 toman budget and the same location/radius, compared with zero before normalization. Two mention used/stock condition. The remaining four have unknown condition; absence of a used marker does not imply new.

Capacity extraction is intentionally limited: explicit storage labels or non-RAM GB/TB values of at least 32 GB. Ambiguous capacities are excluded from explicit storage searches. Bare numbers, older phones below 32 GB, slash shorthand, and unusual labels need further work. Natural-language needs, spelling correction, general translation, complete variant extraction, route distance, live hours, and live inventory are not implemented.

Saved notebook cells were executed sequentially with standard Python. Jupyter packages and a kernel were not installed in this environment, so interactive kernel execution was not verified. Use a configured Python Jupyter kernel to rerun interactively; the saved outputs can be inspected immediately.
