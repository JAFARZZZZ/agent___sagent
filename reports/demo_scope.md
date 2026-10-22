# Initial Demo Scope

## Decision

Use mobile phones for the first search and seller-comparison slice. Keep headphones as the next category. This is a data-readiness decision, not evidence of search relevance or user demand.

| Category | Products | Products with 2+ screened sellers | Share | Shops with screened offers |
|---|---:|---:|---:|---:|
| Mobile phones | 814 | 336 | 41.3% | 127 |
| Headphones and headsets | 1,339 | 336 | 25.1% | 244 |
| Laptops | 505 | 51 | 10.1% | 24 |

Phones have the highest comparison share among these candidates and 700 products with at least five nonempty specification pairs. Headphones offer broader shop coverage. Laptop offers have much narrower seller coverage and include extreme price anomalies.

## Specification Caveat

A direct inspection of phone specification keys found 459 products with the exact internal-storage key and 458 with the exact battery-capacity key, out of 814 products. Other aliases may exist. General specification completeness must not be treated as complete coverage of every purchasing attribute.

## First User Journey

1. Enter a phone model and a maximum budget in toman.
2. Choose a location and radius.
3. Retrieve source-linked products and screened offers.
4. Compare at least two shops for a supported exact product where data permits.
5. Show recorded price, unknown inventory, and declared schedule separately.

Use exact product IDs as the initial grouping boundary. Do not merge by title similarity. Review storage, memory, color, condition, and warranty differences within offers before describing them as interchangeable.

## Next Implementation

Build baseline text retrieval and deterministic budget/radius filters over the staging database. Preserve Persian source text and normalize it for retrieval, while keeping code and reports in English. Prepare 20 evaluation cases covering exact models, variant mismatch, hard budgets, no results, missing data, and radius boundaries. These cases and search implementation are not included in this data-preparation milestone.

The later seller panel must identify itself as simulated. No current record constitutes confirmed inventory or permission to contact a seller.
