# Source Data Profile

Full-file analysis; source files are unchanged.

## Tables

| Table | Rows | Duplicate IDs | Missing IDs |
|---|---:|---:|---:|
| shops | 6,476 | 0 | 0 |
| products | 225,903 | 0 | 0 |
| offers | 331,506 | 0 | 0 |

## Shops Field Completeness

| Field | Missing | Missing % |
|---|---:|---:|
| address | 1 | 0.02% |
| category_names | 0 | 0.00% |
| contacts | 0 | 0.00% |
| instagram | 6,454 | 99.66% |
| lat | 0 | 0.00% |
| location_label | 1 | 0.02% |
| lon | 0 | 0.00% |
| name | 0 | 0.00% |
| payment_options | 0 | 0.00% |
| shop_id | 0 | 0.00% |
| supports_fast_delivery | 4,875 | 75.28% |
| website_url | 6,386 | 98.61% |
| weekly_hours | 0 | 0.00% |

empty_json: `{"category_names": 1797, "contacts": 0, "payment_options": 6210, "weekly_hours": 2003}`

invalid_json: `{}`

wrong_json_type: `{}`

## Products Field Completeness

| Field | Missing | Missing % |
|---|---:|---:|
| brand_name | 168,269 | 74.49% |
| category_name | 0 | 0.00% |
| image_urls | 0 | 0.00% |
| model | 221,847 | 98.20% |
| persian_title | 2 | 0.00% |
| product_id | 0 | 0.00% |
| specs | 0 | 0.00% |

empty_json: `{"image_urls": 1219, "specs": 81304}`

invalid_json: `{}`

wrong_json_type: `{}`

## Offers Field Completeness

| Field | Missing | Missing % |
|---|---:|---:|
| description | 293,129 | 88.42% |
| last_price_changed_at | 769 | 0.23% |
| offer_id | 0 | 0.00% |
| price_toman | 15,083 | 4.55% |
| product_id | 0 | 0.00% |
| seller_title | 0 | 0.00% |
| shop_id | 0 | 0.00% |
| warranty | 272,563 | 82.22% |

empty_json: `{}`

invalid_json: `{}`

wrong_json_type: `{}`

## Checks

```json
{
  "shops_with_web_or_instagram": 112,
  "shops_with_declared_hours": 4447,
  "shops_with_payment_options": 266,
  "products_with_nonempty_spec_values": 144599,
  "offers_unknown_product": 0,
  "offers_unknown_shop": 0,
  "offers_invalid_or_nonpositive_price": 15083,
  "offers_invalid_or_missing_timestamp": 769
}
```

## Coverage

```json
{
  "distinct_sellers_per_product_histogram": {
    "1": 190649,
    "2": 19036,
    "3": 6549,
    "4": 3336,
    "5": 1858,
    "6": 1309,
    "7": 855,
    "8": 654,
    "9": 417,
    "10": 288,
    "11": 192,
    "12": 184,
    "13": 117,
    "14": 95,
    "15": 68,
    "16": 56,
    "17": 46,
    "18": 32,
    "19": 29,
    "20": 14,
    "21": 18,
    "22": 11,
    "23": 19,
    "24": 13,
    "25": 9,
    "26": 5,
    "27": 4,
    "28": 6,
    "29": 3,
    "30": 7,
    "31": 1,
    "32": 3,
    "33": 3,
    "34": 3,
    "35": 2,
    "36": 1,
    "37": 1,
    "38": 2,
    "39": 1,
    "40": 1,
    "41": 2,
    "45": 1,
    "49": 1,
    "51": 1,
    "59": 1
  },
  "products_with_multiple_sellers": 35254,
  "products_without_offers": 0,
  "shops_without_offers": 2684,
  "shop_distinct_product_count": {
    "min": 0,
    "median": 2,
    "p95": 300,
    "max": 300
  },
  "shops_above_300_products": 0,
  "repeated_product_shop_pairs": 9557,
  "category_count": 3428,
  "category_size_distribution": {
    "min": 1,
    "median": 11,
    "p95": 296,
    "max": 5274
  },
  "usable_spec_count": {
    "min": 0,
    "median": 2,
    "p95": 21,
    "max": 258
  },
  "positive_price_toman": {
    "min": 1.0,
    "median": 3640000.0,
    "p95": 108630000.0,
    "max": 7.33518940747299e+17
  },
  "price_change_timestamp_min": "2020-12-03T08:51:32.129814+00:00",
  "price_change_timestamp_max": "2026-10-13T00:02:35.297834+00:00",
  "coordinate_bounds": {
    "lat": {
      "min": 35.64033031672763,
      "median": 35.69482699657525,
      "p95": 35.739111182306125,
      "max": 35.812628383945565
    },
    "lon": {
      "min": 51.30525648593903,
      "median": 51.42087499928497,
      "p95": 51.42759203910828,
      "max": 51.509290119585316
    }
  }
}
```

## Interpretation Limits

- Missing includes empty strings and the literal null; empty JSON containers are counted separately.
- Nonempty specifications measure presence, not accuracy or suitability for recommendations.
- Multiple sellers are counted by product ID; offer variants and warranties still need review.
- Coordinate validation checks numeric ranges, not physical shop locations or Tehran boundaries.
- Declared hours are not live evidence that a shop is open; schedule semantics need validation.
- Price-change timestamps are not inventory checks or last-verification timestamps.
- Website presence does not establish authenticity, reachability, or permission to contact.
- Category labels and source text are omitted to keep generated reports English-only.
- The supplied proposal describes synthetic names and phone numbers; this profiler cannot verify that claim.
- Percentiles use lower nearest-rank indices; median uses the upper middle observation.
