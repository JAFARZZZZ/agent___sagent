"""Profile the source CSV files without modifying them or using external packages."""

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def missing(value):
    return value is None or value.strip().lower() in ("", "null")


def distribution(values):
    values = sorted(values)
    if not values:
        return {}
    return {"min": values[0], "median": values[len(values) // 2],
            "p95": values[int((len(values) - 1) * .95)], "max": values[-1]}


def profile(data_dir):
    result = {"tables": {}, "checks": Counter()}
    ids = {name: set() for name in ("shops", "products", "offers")}
    sellers = defaultdict(set)
    catalogue = defaultdict(set)
    pairs = Counter()
    prices, dates, coordinates = [], [], []
    spec_counts = []
    category_counts = Counter()
    json_fields = {"shops": {"category_names": list, "contacts": list,
                                "payment_options": list, "weekly_hours": dict},
                   "products": {"image_urls": list, "specs": list}, "offers": {}}
    for name in ("shops", "products", "offers"):
        path = data_dir / f"{name}.csv"
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        table = {"rows": 0, "sha256": digest, "bytes": path.stat().st_size,
                 "missing": Counter(), "empty_json": Counter(),
                 "invalid_json": Counter(), "wrong_json_type": Counter(),
                 "duplicate_ids": 0, "missing_ids": 0}
        result["tables"][name] = table
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            table["columns"] = reader.fieldnames
            for row in reader:
                table["rows"] += 1
                if None in row or any(v is None for v in row.values()):
                    result["checks"][f"{name}_malformed_rows"] += 1
                    continue
                for key, value in row.items():
                    table["missing"][key] += int(missing(value))
                key = row[f"{name[:-1]}_id"]
                if missing(key):
                    table["missing_ids"] += 1
                else:
                    table["duplicate_ids"] += int(key in ids[name])
                    ids[name].add(key)
                parsed = {}
                for field, expected in json_fields[name].items():
                    if missing(row[field]):
                        continue
                    try:
                        value = json.loads(row[field])
                        if not isinstance(value, expected):
                            table["wrong_json_type"][field] += 1
                        else:
                            parsed[field] = value
                            table["empty_json"][field] += int(not value)
                    except (ValueError, TypeError):
                        table["invalid_json"][field] += 1
                if name == "shops":
                    try:
                        lat, lon = float(row["lat"]), float(row["lon"])
                        if not (math.isfinite(lat) and math.isfinite(lon)
                                and -90 <= lat <= 90 and -180 <= lon <= 180):
                            raise ValueError
                        coordinates.append((lat, lon))
                    except ValueError:
                        result["checks"]["shops_invalid_or_missing_coordinates"] += 1
                    result["checks"]["shops_with_web_or_instagram"] += int(
                        not missing(row["website_url"]) or not missing(row["instagram"]))
                    hours = parsed.get("weekly_hours", {})
                    result["checks"]["shops_with_declared_hours"] += int(any(
                        isinstance(day, dict) and day.get("status") == "declared"
                        for day in hours.values()))
                    result["checks"]["shops_with_payment_options"] += bool(parsed.get("payment_options"))
                elif name == "products":
                    category_counts[row["category_name"]] += 1
                    specs = parsed.get("specs", [])
                    usable = sum(isinstance(s, dict) and bool(s.get("key"))
                                 and s.get("value") not in (None, "", "null") for s in specs)
                    spec_counts.append(usable)
                    result["checks"]["products_with_nonempty_spec_values"] += int(usable > 0)
                else:
                    pid, sid = row["product_id"], row["shop_id"]
                    result["checks"]["offers_unknown_product"] += int(pid not in ids["products"])
                    result["checks"]["offers_unknown_shop"] += int(sid not in ids["shops"])
                    sellers[pid].add(sid)
                    catalogue[sid].add(pid)
                    pairs[(pid, sid)] += 1
                    try:
                        price = float(row["price_toman"])
                        if not math.isfinite(price) or price <= 0:
                            raise ValueError
                        prices.append(price)
                    except ValueError:
                        result["checks"]["offers_invalid_or_nonpositive_price"] += 1
                    try:
                        stamp = datetime.fromisoformat(row["last_price_changed_at"])
                        if stamp.tzinfo is None:
                            raise ValueError
                        dates.append(stamp)
                    except ValueError:
                        result["checks"]["offers_invalid_or_missing_timestamp"] += 1
    seller_counts = Counter(len(sellers[pid]) for pid in ids["products"])
    result["coverage"] = {
        "distinct_sellers_per_product_histogram": dict(sorted(seller_counts.items())),
        "products_with_multiple_sellers": sum(n for count, n in seller_counts.items() if count >= 2),
        "products_without_offers": seller_counts[0],
        "shops_without_offers": sum(not catalogue[sid] for sid in ids["shops"]),
        "shop_distinct_product_count": distribution([len(catalogue[sid]) for sid in ids["shops"]]),
        "shops_above_300_products": sum(len(catalogue[sid]) > 300 for sid in ids["shops"]),
        "repeated_product_shop_pairs": sum(n > 1 for n in pairs.values()),
        "category_count": len(category_counts),
        "category_size_distribution": distribution(list(category_counts.values())),
        "usable_spec_count": distribution(spec_counts),
        "positive_price_toman": distribution(prices),
        "price_change_timestamp_min": min(dates).isoformat() if dates else None,
        "price_change_timestamp_max": max(dates).isoformat() if dates else None,
        "coordinate_bounds": {"lat": distribution([p[0] for p in coordinates]),
                              "lon": distribution([p[1] for p in coordinates])},
    }
    return result


def write_report(result, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "data_profile.json").write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    lines = ["# Source Data Profile", "", "Full-file analysis; source files are unchanged.", "",
             "## Tables", "", "| Table | Rows | Duplicate IDs | Missing IDs |", "|---|---:|---:|---:|"]
    for name, table in result["tables"].items():
        lines.append(f"| {name} | {table['rows']:,} | {table['duplicate_ids']} | {table['missing_ids']} |")
    for name, table in result["tables"].items():
        lines += ["", f"## {name.title()} Field Completeness", "", "| Field | Missing | Missing % |", "|---|---:|---:|"]
        for field, count in table["missing"].items():
            lines.append(f"| {field} | {count:,} | {100 * count / max(1, table['rows']):.2f}% |")
        for metric in ("empty_json", "invalid_json", "wrong_json_type"):
            lines += ["", f"{metric}: `{json.dumps(table[metric], sort_keys=True)}`"]
    lines += ["", "## Checks", "", "```json", json.dumps(result["checks"], indent=2), "```",
              "", "## Coverage", "", "```json", json.dumps(result["coverage"], indent=2), "```", "",
              "## Interpretation Limits", "",
              "- Missing includes empty strings and the literal null; empty JSON containers are counted separately.",
              "- Nonempty specifications measure presence, not accuracy or suitability for recommendations.",
              "- Multiple sellers are counted by product ID; offer variants and warranties still need review.",
              "- Coordinate validation checks numeric ranges, not physical shop locations or Tehran boundaries.",
              "- Declared hours are not live evidence that a shop is open; schedule semantics need validation.",
              "- Price-change timestamps are not inventory checks or last-verification timestamps.",
              "- Website presence does not establish authenticity, reachability, or permission to contact.",
              "- Category labels and source text are omitted to keep generated reports English-only.",
              "- The supplied proposal describes synthetic names and phone numbers; this profiler cannot verify that claim.",
              "- Percentiles use lower nearest-rank indices; median uses the upper middle observation."]
    (output / "data_profile.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    write_report(profile(args.data_dir), args.output_dir)
    print(f"Profile written to {args.output_dir}")
