"""Create and execute plain-Python notebook cells without extra dependencies."""

import contextlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    cells = []

    def markdown(text):
        cells.append(dict(cell_type="markdown", metadata={}, source=text.splitlines(keepends=True)))

    def code(text):
        cells.append(dict(cell_type="code", metadata={}, source=text.splitlines(keepends=True),
                          execution_count=None, outputs=[]))

    markdown("# Data Readiness and Phone Search\n\nRun cells in order with a Python 3 kernel. All prose and summaries are English. Source-language product data remains in the database. This notebook reads generated artifacts and does not rebuild or change source data.\n\nThe saved outputs were executed sequentially with Python by the builder. A Jupyter kernel launch was not tested in this environment.")
    code('from pathlib import Path\nimport sys, json, sqlite3\nfrom contextlib import closing\nROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "scripts/search_catalog.py").exists())\nif str(ROOT) not in sys.path:\n    sys.path.insert(0, str(ROOT))\nfrom scripts.search_catalog import search\nDB = ROOT / "data/processed/catalog.sqlite"\nassert DB.exists(), "Run python scripts/prepare_data.py first"\nprint("Project and database located.")')
    markdown("## Source Counts\n\nCheck the live database against the recorded baseline.")
    code('profile = json.loads((ROOT / "reports/data_profile.json").read_text())\nwith closing(sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True)) as db:\n    for table in ("shops", "products", "offers"):\n        count = db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]\n        assert count == profile["tables"][table]["rows"]\n        print(f"{table}: {count:,}")')
    markdown("## Category Selection\n\nPhones are the first demo category because 336 of 814 products have multiple screened sellers. Counts do not establish variant equivalence or current availability.")
    code('quality = json.loads((ROOT / "reports/category_quality.json").read_text())\nfor row in quality["categories"]:\n    if row["label"] != row["category_id"]:\n        print(f"{row[\'label\']}: {row[\'products\']} products, {row[\'comparable_products\']} comparable, {row[\'shops\']} shops")\nprint("Price screening:")\nprint(json.dumps(quality["price_status_counts"], indent=2))')
    markdown("## Try a Search\n\nEdit the query, budget, location, and radius below. Distance is straight-line distance, not route distance. Non-capacity query tokens must occur in both product metadata and seller title. English and Persian GB/TB aliases are normalized. Explicit storage queries require matching capacity evidence in both titles; conflicting or missing evidence is excluded. Bare numbers remain lexical terms.\n\nResults are offers, not merged variants. Price is recorded and unverified. Inventory remains unknown. A used-condition hint is based on title mentions; no mention means unknown, not new.")
    code('QUERY = "A55"\nBUDGET_TOMAN = 100_000_000\nLATITUDE, LONGITUDE = 35.7, 51.4\nRADIUS_KM = 10\nresponse = search(DB, QUERY, BUDGET_TOMAN, LATITUDE, LONGITUDE, RADIUS_KM)\nprint(f"Matching offers: {response[\'total_matches\']}")\nfor row in response["results"]:\n    print(json.dumps({k: row[k] for k in ("product_id", "offer_id", "shop_id", "price_toman", "distance_km", "inventory_status", "variant_status")}, ensure_ascii=True))')
    markdown("## Constraint Evaluation\n\nTwenty fixed queries cover models, storage terms, budgets, radius changes, missing models, and letter case. These are automated constraint checks. Relevance labels remain pending; an empty result does not prove good retrieval. Fixture tests separately cover missing prices, suspect offers, missing coordinates, and exact radius boundaries.")
    code('evaluation = json.loads((ROOT / "reports/search_evaluation.json").read_text())\nfor row in evaluation["cases"]:\n    print(f"{row[\'case\']}: matches={row[\'total_matches\']}, constraints_pass={row[\'constraints_pass\']}")\nassert all(row["constraints_pass"] for row in evaluation["cases"])\nprint("Manual relevance review remains pending.")')
    markdown("## Reviewed Storage Example\n\nSeven A55 offers were inspected by the assistant: six mention 256 GB and one mentions 128 GB. Two of the six mention used/stock condition. This is a development sample, not an independent human evaluation or held-out accuracy benchmark.")
    code('reviewed = search(DB, "A55 256GB", 200_000_000, LATITUDE, LONGITUDE, RADIUS_KM)\nfor row in reviewed["results"]:\n    print(json.dumps({k: row[k] for k in ("offer_id", "storage_gb_evidence", "condition_hint")}, ensure_ascii=True))\nprint(json.dumps(evaluation["reviewed_sample"], indent=2))')
    markdown("## Next Checks\n\nReview broader model families and ambiguous titles. Independent relevance judgments remain pending. Exact RAM, color, warranty, and condition equivalence are not established. The baseline uses local SQLite and bounded category scans; it is not a production search service.")
    scope = {}
    execution = 0
    for cell in cells:
        if cell["cell_type"] == "code":
            execution += 1
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                exec(compile("".join(cell["source"]), f"notebook-cell-{execution}", "exec"), scope)
            cell["execution_count"] = execution
            cell["outputs"] = [dict(output_type="stream", name="stdout", text=capture.getvalue().splitlines(keepends=True))]
        cell["id"] = f"cell-{cells.index(cell)+1}"
    notebook = dict(cells=cells, metadata={"kernelspec":{"display_name":"Python 3", "language":"python", "name":"python3"},
                                         "language_info":{"name":"python", "version":"3.14.6"}}, nbformat=4, nbformat_minor=5)
    target = ROOT / "notebooks/01_data_and_search.ipynb"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(notebook, indent=2, ensure_ascii=True)+"\n", encoding="utf-8")
    print(f"Saved notebook with {execution} executed code cells: {target}")


if __name__ == "__main__":
    main()
