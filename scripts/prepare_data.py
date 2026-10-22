"""Build a reproducible SQLite staging database and English category reports."""

import argparse
import csv
import hashlib
import json
import math
import sqlite3
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median

CANDIDATES = {
    "a871231821df": "Mobile phones",
    "0e6f174b6d47": "Laptops",
    "de3a3d46348f": "Headphones and headsets",
    "716eb1cc792d": "Power banks",
    "4e64535c3054": "Speakers and audio systems",
}
NESTED = {"specs", "image_urls", "category_names", "contacts", "weekly_hours", "payment_options"}


def normalize(value):
    if value is None or value.strip().lower() in ("", "null"):
        return None
    return value.strip()


def parse_price(value):
    value = normalize(value)
    if value is None:
        return None, "missing"
    try:
        price = Decimal(value)
    except InvalidOperation:
        return None, "invalid"
    if not price.is_finite() or price <= 0:
        return None, "invalid"
    if price != price.to_integral_value():
        return None, "fractional_toman"
    if price > 2**63 - 1:
        return None, "integer_overflow"
    return int(price), "parsed"


def classify_price(price, status, reference):
    if status != "parsed":
        return status
    if reference is None:
        return "insufficient_reference"
    if price < reference / 100 or price > reference * 100:
        return "category_outlier"
    return "screened"


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        for line, row in enumerate(csv.DictReader(source), 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Malformed CSV record at {path.name}:{line}")
            yield line, row


def payload(row):
    normalized = {k: normalize(v) for k, v in row.items()}
    for field in NESTED & normalized.keys():
        if normalized[field] is not None:
            normalized[field] = json.loads(normalized[field])
    return json.dumps(normalized, ensure_ascii=True)


def prepare(data_dir, output_dir, report_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "catalog.sqlite"
    temporary = output_dir / "catalog.build.sqlite"
    if temporary.exists():
        raise FileExistsError(f"Previous incomplete build exists: {temporary}")
    db = sqlite3.connect(temporary)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE sources (name TEXT PRIMARY KEY, sha256 TEXT NOT NULL);
        CREATE TABLE shops (shop_id TEXT PRIMARY KEY, lat REAL, lon REAL,
            has_declared_hours INTEGER, source_row INTEGER, payload TEXT NOT NULL);
        CREATE TABLE products (product_id TEXT PRIMARY KEY, category_id TEXT,
            spec_count INTEGER, source_row INTEGER, payload TEXT NOT NULL);
        CREATE TABLE offers (offer_id TEXT PRIMARY KEY,
            product_id TEXT REFERENCES products(product_id), shop_id TEXT REFERENCES shops(shop_id),
            price_toman INTEGER, price_status TEXT, inventory_status TEXT DEFAULT 'unknown',
            source_row INTEGER, payload TEXT NOT NULL);
    """)
    categories = defaultdict(list)
    products = {}
    for name in ("shops", "products", "offers"):
        with (data_dir / f"{name}.csv").open("rb") as source:
            db.execute("INSERT INTO sources VALUES (?, ?)",
                       (name, hashlib.file_digest(source, "sha256").hexdigest()))
    for line, row in rows(data_dir / "shops.csv"):
        try:
            lat, lon = float(row["lat"]), float(row["lon"])
            if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
        except ValueError:
            lat = lon = None
        hours = json.loads(row["weekly_hours"]) or {}
        declared = any(isinstance(d, dict) and d.get("status") == "declared" for d in hours.values())
        db.execute("INSERT INTO shops VALUES (?, ?, ?, ?, ?, ?)",
                   (row["shop_id"], lat, lon, declared, line, payload(row)))
    for line, row in rows(data_dir / "products.csv"):
        category = hashlib.sha256(row["category_name"].encode()).hexdigest()[:12]
        specs = json.loads(row["specs"]) or []
        count = sum(isinstance(s, dict) and normalize(str(s.get("key") or "")) is not None
                    and normalize(str(s.get("value") or "")) is not None for s in specs)
        products[row["product_id"]] = category
        categories[category].append(row["product_id"])
        db.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?)",
                   (row["product_id"], category, count, line, payload(row)))
    product_prices = defaultdict(list)
    for line, row in rows(data_dir / "offers.csv"):
        price, status = parse_price(row["price_toman"])
        if status == "parsed":
            product_prices[row["product_id"]].append(price)
        db.execute("INSERT INTO offers (offer_id, product_id, shop_id, price_toman, price_status, source_row, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (row["offer_id"], row["product_id"], row["shop_id"], price, status, line, payload(row)))
    references = {}
    for category, pids in categories.items():
        values = [median(product_prices[pid]) for pid in pids if product_prices[pid]]
        references[category] = median(values) if len(values) >= 30 else None
    updates = []
    for oid, pid, price, status in db.execute("SELECT offer_id, product_id, price_toman, price_status FROM offers"):
        updates.append((classify_price(price, status, references[products[pid]]), oid))
    db.executemany("UPDATE offers SET price_status=? WHERE offer_id=?", updates)
    db.executescript("""
        CREATE INDEX offers_product ON offers(product_id);
        CREATE INDEX offers_shop ON offers(shop_id);
        CREATE INDEX products_category ON products(category_id);
        CREATE INDEX offers_price ON offers(price_status, price_toman);
        CREATE VIEW searchable_offers AS SELECT o.* FROM offers o JOIN shops s USING(shop_id)
            WHERE o.price_status='screened' AND s.lat IS NOT NULL AND s.lon IS NOT NULL;
    """)
    stats = []
    category_specs = dict((r[0], r[1:]) for r in db.execute("""
        SELECT category_id, COUNT(*), SUM(spec_count > 0), SUM(spec_count >= 5)
        FROM products GROUP BY category_id"""))
    category_offers = dict((r[0], r[1:]) for r in db.execute("""
        SELECT p.category_id, COUNT(*), COUNT(DISTINCT o.shop_id),
               COUNT(DISTINCT o.product_id), SUM(s.has_declared_hours)
        FROM searchable_offers o JOIN products p USING(product_id) JOIN shops s USING(shop_id)
        GROUP BY p.category_id"""))
    category_comparable = dict(db.execute("""
        SELECT category_id, COUNT(*) FROM (
            SELECT p.category_id, o.product_id FROM searchable_offers o
            JOIN products p USING(product_id)
            GROUP BY p.category_id, o.product_id HAVING COUNT(DISTINCT shop_id)>=2
        ) GROUP BY category_id"""))
    for category, pids in sorted(categories.items()):
        row = category_specs[category]
        offers = category_offers.get(category, (0, 0, 0, 0))
        comparable = category_comparable.get(category, 0)
        stats.append(dict(category_id=category, label=CANDIDATES.get(category, category),
                          products=row[0], with_specs=row[1], with_five_specs=row[2],
                          screened_offers=offers[0], shops=offers[1], priced_products=offers[2],
                          offers_with_declared_hours=offers[3] or 0,
                          comparable_products=comparable,
                          price_reference_toman=references[category]))
    counts = dict(db.execute("SELECT price_status, COUNT(*) FROM offers GROUP BY price_status"))
    assert not db.execute("PRAGMA foreign_key_check").fetchall()
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    db.commit()
    db.close()
    temporary.replace(destination)
    report = {"price_status_counts": counts, "categories": stats}
    (report_dir / "category_quality.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    candidates = sorted((s for s in stats if s["category_id"] in CANDIDATES),
                        key=lambda s: s["comparable_products"], reverse=True)
    lines = ["# Category Quality", "", "## Consumer Electronics Candidates", "",
             "| Category | Products | With specs | With 5+ specs | Screened products | Comparable products | Shops |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for s in candidates:
        lines.append(f"| {s['label']} | {s['products']} | {s['with_specs']} | {s['with_five_specs']} | {s['priced_products']} | {s['comparable_products']} | {s['shops']} |")
    lines += ["", "Comparable means at least two distinct shops with screened offers and valid numeric coordinates. Variant equivalence is not established.",
              "", "## Price Screening", "", "```json", json.dumps(counts, indent=2), "```", "",
              "For each category, use the median of per-product median prices, with at least 30 priced products. Flag prices outside 0.01x to 100x this reference. This is a broad provisional anomaly screen, not price verification. Sparse categories require review before budget ranking.",
              "", "Missing, invalid, fractional, overflow, outlier, and insufficient-reference offers remain stored but are excluded from searchable_offers. Original values remain in the source CSV and payload.",
              "", "Specifications measure nonempty key/value presence only. Five specifications do not guarantee five useful purchasing attributes. All inventory is unknown. Declared hours do not imply that a shop is open now.",
              "", "Category IDs are the first 12 hexadecimal characters of SHA-256 of the original category name. English labels are manually assigned only for the candidate shortlist. Full category metrics are in category_quality.json."]
    (report_dir / "category_quality.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"database": str(destination), "price_status_counts": counts, "candidates": candidates}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    prepare(args.data_dir, args.output_dir, args.report_dir)
