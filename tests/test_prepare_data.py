"""Boundary tests for price safety and missing values."""

import unittest
import contextlib
import csv
import io
import json
import sqlite3
import tempfile
from pathlib import Path
from scripts.prepare_data import classify_price, normalize, parse_price, prepare


class PriceTests(unittest.TestCase):
    def test_invalid_prices_never_enter_ranking(self):
        for value in ("", "null", "NaN", "Infinity", "-1", "0", "abc", "12.5", "1e30"):
            price, status = parse_price(value)
            self.assertNotEqual(classify_price(price, status, 100), "screened")

    def test_integer_precision_is_preserved(self):
        self.assertEqual(parse_price("733518940747299001"), (733518940747299001, "parsed"))

    def test_category_context_and_sparse_data(self):
        self.assertEqual(classify_price(100, "parsed", 100), "screened")
        self.assertEqual(classify_price(100, "parsed", 1000000), "category_outlier")
        self.assertEqual(classify_price(100, "parsed", None), "insufficient_reference")

    def test_missing_is_not_zero_or_false(self):
        self.assertIsNone(normalize(" NULL "))
        self.assertEqual(normalize("0"), "0")
        self.assertEqual(normalize("false"), "false")

    def test_pipeline_preserves_rows_and_excludes_unsafe_offers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shops = [dict(shop_id=f"s{i}", lat="35.7", lon="51.4", weekly_hours="{}") for i in range(2)]
            products = [dict(product_id=f"p{i}", category_name="Example", specs="[]") for i in range(30)]
            offers = [dict(offer_id=f"o{i}", product_id=f"p{i}", shop_id="s0", price_toman="100") for i in range(30)]
            offers += [dict(offer_id="missing", product_id="p0", shop_id="s1", price_toman="null"),
                       dict(offer_id="outlier", product_id="p1", shop_id="s1", price_toman="1000000000"),
                       dict(offer_id="second", product_id="p2", shop_id="s1", price_toman="120")]
            for name, values in (("shops", shops), ("products", products), ("offers", offers)):
                with (root / f"{name}.csv").open("w", newline="", encoding="utf-8") as output:
                    writer = csv.DictWriter(output, fieldnames=values[0].keys())
                    writer.writeheader()
                    writer.writerows(values)
            with contextlib.redirect_stdout(io.StringIO()):
                prepare(root, root / "processed", root / "reports")
            with contextlib.closing(sqlite3.connect(root / "processed/catalog.sqlite")) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM offers").fetchone()[0], 33)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM searchable_offers").fetchone()[0], 31)
                self.assertEqual(db.execute("SELECT price_status FROM offers WHERE offer_id='outlier'").fetchone()[0], "category_outlier")
                self.assertEqual(db.execute("SELECT COUNT(*) FROM offers WHERE inventory_status='unknown'").fetchone()[0], 33)
            report = json.loads((root / "reports/category_quality.json").read_text())
            self.assertEqual(report["categories"][0]["comparable_products"], 1)


if __name__ == "__main__":
    unittest.main()
