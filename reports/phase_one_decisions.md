# Phase One: Findings and Next Steps

## Completed

All three source CSV files were scanned locally. The reproducible profiler uses only the Python standard library. File hashes, field completeness, JSON validity, identifier integrity, seller coverage, price distributions, timestamp ranges, and coordinate bounds are recorded in data_profile.json and data_profile.md. Raw files were not changed.

Run from the repository root:

```powershell
python scripts/profile_data.py
```

## Findings That Affect the MVP

- 225,903 products, 6,476 shops, and 331,506 offers match the supplied README.
- Primary identifiers are present and unique. All offers reference known products and shops.
- Only 35,254 products (15.61%) have at least two distinct sellers. Comparison is available for a minority of products.
- 2,684 shops (41.45%) have no offers in this export. Search should start from matching offers rather than all nearby shops.
- 9,557 product/shop pairs have multiple offers. Do not silently deduplicate them before reviewing variants and warranty differences.
- 98.20% of model fields and 74.49% of brand fields are missing. Product titles and specifications will be necessary for retrieval; exact variant matching needs explicit checks.
- 81,304 products have empty specifications. Nonempty specifications do not prove that task-specific attributes such as weight or memory exist.
- 15,083 offers have missing prices. Positive prices range from 1 to approximately 7.34e17 toman, requiring investigation before ranking.
- 4,447 shops have at least one day marked as declared in their hours. This does not imply complete or current schedules.
- Only 266 shops have nonempty payment options. Empty options must mean unknown, not a confirmed lack of installment support.
- 112 shops have a website or Instagram field. Their authenticity and connectivity have not been checked.
- Price-change timestamps range from December 2020 to October 2026. They cannot establish the freshness of an inventory or price verification.

## Next Implementation Slice

1. Define a normalization contract: map literal null and empty fields to missing values, parse nested JSON, retain original values and stable IDs, and preserve source provenance.
2. Investigate extreme prices with product context. Quarantine missing or suspect prices from budget ranking; do not invent replacements or apply one global category-independent price cutoff.
3. Evaluate a small set of candidate product categories for useful specifications, distinct sellers, valid prices, and local shop coverage. Select the demo category after this analysis.
4. Build baseline text search with deterministic budget and geographic filters. Compare exact model, broad category, and needs-based queries before deciding whether embeddings are necessary.
5. Curate an initial evaluation set of 20 queries, including missing information and no-result cases. Review top results manually and record incorrect variants, unsupported claims, and filter violations.

## Completion Criteria for the First Search Slice

- Every result resolves to existing product, offer, and shop IDs.
- Hard price filters exclude missing and quarantined prices.
- Variant differences and warranty uncertainty are preserved.
- Source prices are labeled as recorded prices; inventory remains unknown until separately confirmed.
- Missing data never becomes an affirmative claim about hours, installments, or availability.
- The evaluation set records retrieval quality and remaining failures before AI orchestration is added.

## Outstanding Analysis

Category-level suitability, detailed specification coverage, schedule validity, price anomaly review, neighborhood-level availability, and search evaluation remain to be done. This report establishes a baseline, not a production-ready clean dataset. The synthetic-contact limitations in the supplied proposal should remain explicit in any demo.

## Follow-up Milestone

Category-level metrics and an initial price-screening pipeline are now implemented. See category_quality.md, normalization_contract.md, and demo_scope.md. Mobile phones are selected for the first search slice. Detailed variant checks, schedule validation, neighborhood coverage, and search evaluation remain open.
