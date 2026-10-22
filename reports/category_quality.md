# Category Quality

## Consumer Electronics Candidates

| Category | Products | With specs | With 5+ specs | Screened products | Comparable products | Shops |
|---|---:|---:|---:|---:|---:|---:|
| Mobile phones | 814 | 783 | 700 | 806 | 336 | 127 |
| Headphones and headsets | 1339 | 1174 | 1070 | 1322 | 336 | 244 |
| Speakers and audio systems | 1063 | 902 | 820 | 1029 | 267 | 213 |
| Power banks | 755 | 670 | 598 | 737 | 199 | 166 |
| Laptops | 505 | 499 | 492 | 503 | 51 | 24 |

Comparable means at least two distinct shops with screened offers and valid numeric coordinates. Variant equivalence is not established.

## Price Screening

```json
{
  "category_outlier": 3837,
  "insufficient_reference": 22948,
  "missing": 15083,
  "screened": 289638
}
```

For each category, use the median of per-product median prices, with at least 30 priced products. Flag prices outside 0.01x to 100x this reference. This is a broad provisional anomaly screen, not price verification. Sparse categories require review before budget ranking.

Missing, invalid, fractional, overflow, outlier, and insufficient-reference offers remain stored but are excluded from searchable_offers. Original values remain in the source CSV and payload.

Specifications measure nonempty key/value presence only. Five specifications do not guarantee five useful purchasing attributes. All inventory is unknown. Declared hours do not imply that a shop is open now.

Category IDs are the first 12 hexadecimal characters of SHA-256 of the original category name. English labels are manually assigned only for the candidate shortlist. Full category metrics are in category_quality.json.
