"""Run a repeatable constraint evaluation; relevance still needs human labels."""

import json
from pathlib import Path
from time import perf_counter
from scripts.search_catalog import search

CASES = [
    ("model_a55", "A55", 200000000, 10),
    ("model_a35", "A35", 200000000, 10),
    ("model_a15", "A15", 200000000, 10),
    ("model_s23", "S23", 300000000, 10),
    ("model_s24", "S24", 300000000, 10),
    ("model_iphone", "iPhone", 300000000, 10),
    ("model_redmi", "Redmi", 200000000, 10),
    ("model_poco", "Poco", 200000000, 10),
    ("storage_128", "A55 128", 200000000, 10),
    ("storage_256", "A55 256", 200000000, 10),
    ("storage_512", "S24 512", 300000000, 10),
    ("storage_unit", "A55 256GB", 200000000, 10),
    ("budget_low", "A55", 1000000, 10),
    ("budget_mid", "A55", 100000000, 10),
    ("radius_zero", "A55", 200000000, 0),
    ("radius_small", "A55", 200000000, 1),
    ("radius_large", "A55", 200000000, 30),
    ("unknown_model", "NoSuchModelZXQ999", 200000000, 10),
    ("near_model", "A5", 200000000, 10),
    ("case_normalization", "a55", 200000000, 10),
]


def evaluate(root):
    records = []
    for name, query, budget, radius in CASES:
        start = perf_counter()
        response = search(root / "data/processed/catalog.sqlite", query, budget, 35.7, 51.4, radius, 1000)
        results = response["results"]
        valid = all(0 < r["price_toman"] <= budget and r["distance_km"] <= radius
                    and r["inventory_status"] == "unknown" for r in results)
        if name == "unknown_model":
            valid = valid and not results
        records.append(dict(case=name, query=query, budget_toman=budget, radius_km=radius,
                            total_matches=response["total_matches"], constraints_pass=valid,
                            elapsed_ms=round((perf_counter()-start)*1000, 2),
                            review_status="pending_manual_relevance_review",
                            top_offer_ids=[r["offer_id"] for r in results[:5]]))
    assert all(r["constraints_pass"] for r in records)
    by_name = {r["case"]: r for r in records}
    assert by_name["model_a55"]["top_offer_ids"] == by_name["case_normalization"]["top_offer_ids"]
    review = json.loads((root / "reports/relevance_review.json").read_text())
    reviewed_results = search(root / "data/processed/catalog.sqlite", review["query"], review["budget_toman"], review["latitude"], review["longitude"], review["radius_km"], 1000)["results"]
    found = {r["offer_id"] for r in reviewed_results}
    assert set(review["positive_offer_ids"]) <= found
    assert not set(review["negative_offer_ids"]) & found
    assert all(r["condition_hint"] == "used_or_refurbished_mentioned" for r in reviewed_results if r["offer_id"] in review["used_or_refurbished_offer_ids"])
    reviewed = {"reviewer": review["reviewer"], "positive_examples_retrieved": len(found & set(review["positive_offer_ids"])),
                "negative_examples_retrieved": len(found & set(review["negative_offer_ids"])),
                "scope": "Development regression on seven inspected offers, not held-out retrieval accuracy"}
    output = {"scope": "Constraint checks plus a small assistant-reviewed development sample", "cases": records, "reviewed_sample": reviewed}
    (root / "reports/search_evaluation.json").write_text(json.dumps(output, indent=2)+"\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    result = evaluate(Path(__file__).resolve().parents[1])
    print(f"Completed {len(result['cases'])} cases; all constraint checks passed.")
