"""Conservative lexical phone search with hard price and geodesic filters."""

import argparse
import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path

if __package__:
    from .product_text import condition_hint, query_terms, storage_values, tokens
else:
    from product_text import condition_hint, query_terms, storage_values, tokens

PHONE_CATEGORY = "a871231821df"


def distance_km(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    x = math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(max(0, min(1, x))))


def search(database, query, max_price_toman, lat, lon, radius_km, limit=20):
    terms = tokens(query)
    if not terms:
        raise ValueError("Query must contain at least one word or model identifier")
    requested_storage = storage_values(query)
    if len(requested_storage) > 1:
        raise ValueError("Specify only one storage capacity")
    if requested_storage:
        terms = query_terms(query)
    if isinstance(max_price_toman, bool) or not isinstance(max_price_toman, int) or not 0 < max_price_toman <= 2**63 - 1:
        raise ValueError("Budget must be a positive 64-bit integer in toman")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (lat, lon, radius_km)):
        raise ValueError("Location and radius must be finite numbers")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180 or radius_km < 0:
        raise ValueError("Location or radius is outside its valid range")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("Limit must be an integer between 1 and 1000")
    matches = []
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        products = {}
        for pid, raw in db.execute("SELECT product_id, payload FROM products WHERE category_id=?", (PHONE_CATEGORY,)):
            product = json.loads(raw)
            searchable = " ".join(product.get(k) or "" for k in ("persian_title", "model", "brand_name"))
            if terms <= tokens(searchable) and (not requested_storage or storage_values(product.get("persian_title")) == requested_storage):
                products[pid] = product
        for pid, product in products.items():
            rows = db.execute("""SELECT o.offer_id, o.shop_id, o.price_toman, o.payload,
                s.lat, s.lon, s.has_declared_hours
                FROM offers o INDEXED BY offers_product JOIN shops s USING(shop_id)
                WHERE o.product_id=? AND o.price_status='screened'
                AND o.price_toman > 0 AND o.price_toman<=?
                AND s.lat IS NOT NULL AND s.lon IS NOT NULL""", (pid, max_price_toman))
            for oid, sid, price, raw, shop_lat, shop_lon, hours in rows:
                offer = json.loads(raw)
                # Fail closed when the seller title does not corroborate every query term.
                if not terms <= tokens(offer.get("seller_title")):
                    continue
                seller_storage = storage_values(offer.get("seller_title"))
                if requested_storage and seller_storage != requested_storage:
                    continue
                distance = distance_km(lat, lon, shop_lat, shop_lon)
                if distance > radius_km:
                    continue
                matches.append(dict(product_id=pid, offer_id=oid, shop_id=sid,
                    product_title=product.get("persian_title"), seller_title=offer.get("seller_title"),
                    price_toman=price, price_status="recorded_screened_not_verified",
                    distance_km=distance, distance_kind="straight_line",
                    inventory_status="unknown", has_declared_hours=bool(hours),
                    warranty=offer.get("warranty"), variant_status="requires_review",
                    storage_gb_evidence=sorted(seller_storage),
                    condition_hint=condition_hint(" ".join([product.get("persian_title") or "", offer.get("seller_title") or ""])),
                    last_price_changed_at=offer.get("last_price_changed_at")))
    matches.sort(key=lambda r: (r["price_toman"], r["distance_km"], r["offer_id"]))
    return {"total_matches": len(matches), "returned": min(limit, len(matches)),
            "sort": "price_then_distance", "results": matches[:limit]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--database", type=Path, default=Path("data/processed/catalog.sqlite"))
    parser.add_argument("--budget", type=int, required=True)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--radius-km", type=float, required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(search(args.database, args.query, args.budget, args.lat, args.lon, args.radius_km, args.limit), indent=2, ensure_ascii=True))
