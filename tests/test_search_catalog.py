import json
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path
from scripts.search_catalog import PHONE_CATEGORY, distance_km, search, tokens


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "fixture.sqlite"
        db = sqlite3.connect(self.path)
        db.executescript("""
            CREATE TABLE products(product_id, category_id, payload);
            CREATE TABLE shops(shop_id, lat, lon, has_declared_hours);
            CREATE TABLE offers(offer_id, product_id, shop_id, price_toman, price_status, payload);
            CREATE INDEX offers_product ON offers(product_id);
        """)
        db.execute("INSERT INTO products VALUES (?,?,?)", ("p", PHONE_CATEGORY, json.dumps({"persian_title":"Example A55 256GB"})))
        db.executemany("INSERT INTO shops VALUES (?,?,?,?)", [("near",35.7,51.4,0),("far",36.7,51.4,1),("unknown",None,None,0)])
        for oid, shop, price, status, title in [
            ("ok","near",100,"screened","Example A55 256GB"),
            ("expensive","near",101,"screened","Example A55 256GB"),
            ("far","far",80,"screened","Example A55 256GB"),
            ("wrong","near",50,"screened","Example A55 128GB"),
            ("suspect","near",1,"category_outlier","Example A55 256GB"),
            ("missing","near",None,"missing","Example A55 256GB"),
            ("no_geo","unknown",50,"screened","Example A55 256GB")]:
            db.execute("INSERT INTO offers VALUES (?,?,?,?,?,?)", (oid,"p",shop,price,status,json.dumps({"seller_title":title})))
        db.commit()
        db.close()

    def tearDown(self):
        self.folder.cleanup()

    def test_hard_filters_and_variant_query(self):
        result = search(self.path, "A55 256GB", 100, 35.7, 51.4, 0)
        self.assertEqual([r["offer_id"] for r in result["results"]], ["ok"])
        self.assertEqual(result["results"][0]["inventory_status"], "unknown")

    def test_no_substring_model_match(self):
        self.assertEqual(search(self.path,"A5",100,35.7,51.4,5)["total_matches"], 0)

    def test_distance_and_radius_boundary(self):
        d = distance_km(0,0,0,1)
        self.assertAlmostEqual(d,111.195,places=3)
        edge = distance_km(35.7,51.4,36.7,51.4)
        self.assertIn("far", [r["offer_id"] for r in search(self.path,"256GB",100,35.7,51.4,edge)["results"]])
        self.assertNotIn("far", [r["offer_id"] for r in search(self.path,"256GB",100,35.7,51.4,edge-0.001)["results"]])

    def test_unicode_normalization(self):
        self.assertEqual(tokens(chr(0x064A)+chr(0x0643)), tokens(chr(0x06CC)+chr(0x06A9)))
        self.assertEqual(tokens(chr(0x06F2)+chr(0x06F5)+chr(0x06F6)), {"256"})

    def test_bad_inputs_fail(self):
        for budget, lat, lon, radius in [(0,0,0,1),(True,0,0,1),(100,91,0,1),(100,0,181,1),(100,0,0,-1),(100,math.nan,0,1)]:
            with self.assertRaises(ValueError):
                search(self.path,"A55",budget,lat,lon,radius)
        with self.assertRaises(ValueError):
            search(self.path,"!!!",100,0,0,1)


if __name__ == "__main__":
    unittest.main()
