# Normalization Contract

## Scope and Reproduction

This is a local staging layer for data exploration and the first search prototype. It does not replace the planned production database.

```powershell
python scripts/prepare_data.py
python -m unittest discover -s tests -v
```

The builder reads data/shops.csv, data/products.csv, and data/offers.csv. It writes data/processed/catalog.sqlite and reports/category_quality.md and .json. It uses Python standard-library modules. A completed rebuild replaces the generated database. An interrupted catalog.build.sqlite must be moved aside before retrying. Do not open the generated database in a writable application during a rebuild.

## Source Preservation

- Source CSV files remain unchanged. Their SHA-256 hashes are recorded in the sources table.
- Every imported row retains its original stable ID and CSV record number. Record numbers count logical records starting at two, not physical lines within quoted multiline fields.
- The payload column preserves all source fields after whitespace/null normalization and nested JSON parsing. Exact original text remains in the source CSV.
- Source-language text is preserved as data. Code, report prose, and labels are English. JSON payloads use ASCII escapes.
- Duplicate primary IDs and broken foreign keys fail the build. Offers sharing a product/shop pair remain separate.

## Missing and Structured Values

- Empty strings and case-insensitive literal null become SQL NULL or JSON null.
- Empty arrays and objects remain empty containers. They do not establish a negative fact about payment, hours, or specifications.
- Nested JSON is parsed. Invalid JSON fails the build. Current source container types were checked in the baseline profile; broader schema validation remains future work.
- Coordinates must be finite and within latitude/longitude numeric ranges. Invalid coordinate pairs become NULL in typed columns; their source values remain in payload.
- A declared schedule means only that at least one day has status declared. Live opening status is not inferred.

## Prices and Search Eligibility

- Currency is toman, as specified by the source field. No currency conversion is applied.
- Parse with Decimal, then store positive integral values in SQLite INTEGER without floating-point conversion.
- Missing, invalid, fractional, and values above SQLite's signed 64-bit integer range receive separate statuses. No price is imputed.
- Compute a reference for each category from the median of per-product median prices, requiring at least 30 priced products. This reduces the influence of products with many offers; duplicates within a product can still affect its median.
- Prices below 0.01 times or above 100 times the reference receive category_outlier. Sparse categories receive insufficient_reference. Both are excluded from budget ranking pending review.
- The factor of 100 is a provisional broad screening heuristic, not a learned market-price boundary. It can miss anomalies and flag valid niche products. Screened does not mean verified or current.
- searchable_offers includes only screened prices and numerically valid shop coordinates. Consumers must apply exact variant, budget, and geographic constraints separately.
- All inventory_status values are unknown. Price-change timestamps remain source metadata, not verification times.

## Current Results

All 331,506 offers are retained: 289,638 screened, 3,837 category outliers, 22,948 with insufficient category reference, and 15,083 missing prices.

The most extreme inspected example, offer_1665378712426ed7b9199f72, records 733518940747298944 toman for a laptop. It is retained with category_outlier status. No replacement value is guessed.

## Validation

The build checks SQLite integrity and foreign keys. Tests cover invalid values, exact large-integer preservation, category-dependent screening, sparse references, missing-value semantics, and an end-to-end fixture proving row retention and exclusion from search.
