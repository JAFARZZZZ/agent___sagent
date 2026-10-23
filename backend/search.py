"""Hybrid product retrieval.

1. Lexical: SQLite FTS5 with column-weighted BM25 (title > brand/model > category > specs),
   prefix matching, Persian normalisation and a stop-word list for conversational queries.
   AND semantics first; OR semantics as a recall fallback.
2. Dense: optional vector index (``backend.embeddings``).
3. Fusion: Reciprocal Rank Fusion, then a small in-store availability prior.

Filters (category, budget, installment, area) are applied to the fused candidate set with
SQL over offers/shops, so every returned product has evidence for the constraint.
"""
from __future__ import annotations

import json
import math
import re
import time

from backend import catalog as c
from backend import embeddings
from backend import stores
from scripts.product_text import normalize_text

RRF_K = 60
CANDIDATES = 300
FTS_VERSION = 2

# Conversational words that should not be required to match a product.
STOP = set(normalize_text(' '.join('''
می خوام میخوام میخواستم می‌خواهم میخواهم خواستم بخرم خرید بخرم بگیرم دنبال هستم هست است
یه یک یکی چند چندتا برای واسه با بدون و یا که تا از به در رو را این اون آن یک‌ عدد
قیمت ارزان ارزون ارزانترین ارزونترین بهترین خوب خوبی مناسب حدود حداکثر زیر کمتر بیشتر
تومن تومان میلیون هزار ملیون میلیارد نزدیک نزدیکم نزدیکترین اطراف حوالی محدوده
لطفا لطفاً سلام ممنون مرسی پیشنهاد پیشنهادی بده بدی بدید معرفی کن کنید چی چه چیه کدوم کدام
مدل مدلی جنس فروشگاه مغازه پاساژ کجا کجاست داره دارد دارن باشه باشد قسطی اقساطی قسط اعتباری الان امروز باز
'''.split())).split())


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS search_meta(key TEXT PRIMARY KEY, value TEXT)')
    version = db.execute("SELECT value FROM search_meta WHERE key='fts_version'").fetchone()
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='product_fts'").fetchone()
    products = db.execute('SELECT count(*) FROM products').fetchone()[0]
    if exists and version and int(version[0]) == FTS_VERSION and \
            db.execute('SELECT count(*) FROM product_fts').fetchone()[0] == products:
        return
    started = time.monotonic()
    db.execute('DROP TABLE IF EXISTS product_fts')
    db.execute("""CREATE VIRTUAL TABLE product_fts USING fts5(
        product_id UNINDEXED, title, brand, category, specs,
        tokenize='unicode61 remove_diacritics 2')""")
    batch = []
    for pid, payload in db.execute('SELECT product_id, payload FROM products'):
        p = json.loads(payload)
        specs = p.get('specs') or []
        spec_text = ' '.join(f"{s.get('key','')} {s.get('value','')}" for s in specs if isinstance(s, dict)) if isinstance(specs, list) else str(specs)
        batch.append((pid, normalize_text(p.get('persian_title') or ''),
                      normalize_text(' '.join(str(x) for x in (p.get('brand_name'), p.get('model')) if x)),
                      normalize_text(p.get('category_name') or ''), normalize_text(spec_text)))
        if len(batch) >= 5000:
            db.executemany('INSERT INTO product_fts VALUES (?,?,?,?,?)', batch); batch.clear()
    if batch:
        db.executemany('INSERT INTO product_fts VALUES (?,?,?,?,?)', batch)
    db.execute("INSERT OR REPLACE INTO search_meta VALUES ('fts_version', ?)", (str(FTS_VERSION),))
    print(f'Built weighted search index in {time.monotonic()-started:.1f}s')


BUDGET_PHRASE = re.compile(r'\d+(?:[.,/]\d+)?\s*(?:میلیون|ملیون|میلیارد|هزار|تومن|تومان|م\b)')


def query_tokens(text: str) -> list[str]:
    words = re.findall(r'[^\W_]+', BUDGET_PHRASE.sub(' ', normalize_text(text)))
    return [w for w in dict.fromkeys(words) if w not in STOP and len(w) > 1 or w.isdigit()]


def _fts_expression(tokens: list[str], mode: str) -> str:
    quoted = ['"' + t.replace('"', '') + '"*' for t in tokens]
    return (' AND ' if mode == 'and' else ' OR ').join(quoted)


def lexical(db, text: str, category: str | None = None, k: int = CANDIDATES) -> list[str]:
    tokens = query_tokens(text)
    if not tokens:
        return []
    ranked: list[str] = []
    for mode in ('and', 'or'):
        if mode == 'or' and (len(tokens) == 1 or len(ranked) >= 40):
            break
        sql = ('SELECT f.product_id FROM product_fts f' + (' JOIN products p ON p.product_id=f.product_id' if category else '') +
               ' WHERE product_fts MATCH ?' + (' AND p.category_id=?' if category else '') +
               ' ORDER BY bm25(product_fts, 0.0, 10.0, 4.0, 2.5, 0.6) LIMIT ?')
        args = [_fts_expression(tokens, mode)] + ([category] if category else []) + [k]
        try:
            rows = [r[0] for r in db.execute(sql, args)]
        except Exception:
            rows = []
        seen = set(ranked)
        ranked.extend(pid for pid in rows if pid not in seen)
    return ranked[:k]


def _rrf(*lists: list[str]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in lists:
        for rank, pid in enumerate(ranking):
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (RRF_K + rank + 1)
    return scores


def _evidence(db, ids: list[str], budget=None, lat=None, lon=None, radius=None, installment=False, open_now=False):
    """Per-product offer evidence under the active constraints."""
    if not ids:
        return {}
    marks = ','.join('?' * len(ids))
    rows = db.execute(f'''SELECT o.product_id, o.price_toman, o.shop_id, s.lat, s.lon, s.payload
        FROM offers o JOIN shops s USING(shop_id) WHERE o.product_id IN ({marks})''', ids)
    result: dict[str, dict] = {}
    shop_cache: dict[str, dict] = {}
    for pid, price, shop_id, slat, slon, payload in rows:
        e = result.setdefault(pid, {'offers': 0, 'matching_offers': 0, 'min_price': None, 'max_price': None,
                                    'nearest_km': None, 'shops': set(), 'installment_shops': 0, 'open_shops': 0})
        e['offers'] += 1
        if shop_id not in shop_cache:
            shop = json.loads(payload)
            shop_cache[shop_id] = {'installment': bool(stores.installment_providers(shop)),
                                   'open': stores.open_status(shop)['status'] == 'open'}
        info = shop_cache[shop_id]
        price = int(price) if price else None
        if budget is not None and (price is None or price <= 0 or price > budget):
            continue
        distance = None
        if lat is not None and lon is not None and slat is not None:
            distance = stores.distance_km(lat, lon, slat, slon)
            if radius and distance > radius:
                continue
        if installment and not info['installment']:
            continue
        if open_now and not info['open']:
            continue
        e['matching_offers'] += 1
        e['shops'].add(shop_id)
        e['installment_shops'] += info['installment']
        e['open_shops'] += info['open']
        if price and price > 0:
            e['min_price'] = price if e['min_price'] is None else min(e['min_price'], price)
            e['max_price'] = price if e['max_price'] is None else max(e['max_price'], price)
        if distance is not None:
            e['nearest_km'] = distance if e['nearest_km'] is None else min(e['nearest_km'], distance)
    for e in result.values():
        e['shops'] = len(e['shops'])
    return result


# ------------------------------------------------------------------ category intent

ACCESSORY_WORDS = [normalize_text(w) for w in (
    'کیف', 'کاور', 'قاب', 'شاسی', 'محافظ', 'گلس', 'تاچ', 'ال سی دی', 'باتری', 'شارژر', 'فلت', 'برد ', 'پایه',
    'نگهدارنده', 'لوازم جانبی', 'قطعات', 'یدکی', 'آی سی', 'بازر', 'شیشه', 'کابل', 'آنتن', 'میز ', 'جعبه', 'آویز',
    'برچسب', 'استیکر', 'واکس', 'نظم دهنده', 'جاکفشی', 'باکس', 'لنز', 'هولدر', 'کیس ', 'سایر لوازم', 'بند ساعت',
    'آداپتور', 'رم ', 'ریموت', 'اسباب بازی', 'یدک')]

_category_sizes: dict | None = None


def category_sizes(db) -> dict:
    global _category_sizes
    if _category_sizes is None:
        _category_sizes = dict(db.execute('SELECT category_id, count(*) FROM products GROUP BY category_id').fetchall())
    return _category_sizes


def _accessory_markers(text: str) -> set[str]:
    t = ' ' + normalize_text(text) + ' '
    return {w for w in ACCESSORY_WORDS if w in t}


def detect_intent(db, query: str, lexical_ids: list[str]) -> dict:
    """Which categories does the user mean? Accessories are excluded unless the query asks for them."""
    tokens = query_tokens(query)
    if not tokens or not lexical_ids:
        return {'categories': [], 'accessory_categories': []}
    wanted = _accessory_markers(query)
    marks = ','.join('?' * len(lexical_ids))
    cats = {}
    order = {pid: i for i, pid in enumerate(lexical_ids)}
    rows = db.execute(f"SELECT product_id, category_id, json_extract(payload,'$.category_name') FROM products WHERE product_id IN ({marks})", lexical_ids).fetchall()
    for pid, cid, name in rows:
        entry = cats.setdefault(cid, {'id': cid, 'name': name or '', 'evidence': 0.0, 'hits': 0})
        entry['evidence'] += 1.0 / (10 + order[pid])
        entry['hits'] += 1
    head = tokens[0]
    for entry in cats.values():
        words = normalize_text(entry['name']).split()
        bonus = 1.0 if words and words[0].startswith(head[:4]) else 0.0
        bonus += 0.3 * sum(any(w.startswith(t[:4]) for w in words) for t in tokens)
        size = category_sizes(db).get(entry['id'], 1)
        entry['score'] = entry['evidence'] * (1 + bonus) * (1 + math.log10(size))
        markers = _accessory_markers(entry['name']) - wanted
        entry['accessory'] = bool(markers)
    main = sorted((e for e in cats.values() if not e['accessory']), key=lambda e: -e['score'])
    if main:
        top = main[0]['score']
        main = [e for e in main if e['score'] >= 0.25 * top][:4]
    accessory = [e for e in cats.values() if e['accessory']]
    return {'categories': [{'id': e['id'], 'name': e['name']} for e in main],
            'accessory_categories': [e['id'] for e in accessory]}


_rank_cache: dict = {}
RANK_TTL = 300


def rank(query: str = '', category: str | None = None, budget: int | None = None,
         lat: float | None = None, lon: float | None = None, radius: float | None = None,
         installment: bool = False, open_now: bool = False, use_vectors: bool = True,
         include_accessories: bool = False) -> dict:
    """Cached wrapper: the map, the chat and pagination reuse the same ranking for a few minutes."""
    key = (normalize_text(query).strip(), category, budget, round(lat, 4) if lat is not None else None,
           round(lon, 4) if lon is not None else None, radius, installment, open_now, use_vectors, include_accessories,
           int(time.time() // 60) if open_now else 0)
    hit = _rank_cache.get(key)
    if hit and time.monotonic() - hit[0] < RANK_TTL:
        return hit[1]
    result = _rank(query, category, budget, lat, lon, radius, installment, open_now, use_vectors, include_accessories)
    if len(_rank_cache) > 256:
        _rank_cache.clear()
    _rank_cache[key] = (time.monotonic(), result)
    return result


def _rank(query: str = '', category: str | None = None, budget: int | None = None,
          lat: float | None = None, lon: float | None = None, radius: float | None = None,
          installment: bool = False, open_now: bool = False, use_vectors: bool = True,
          include_accessories: bool = False) -> dict:
    """Full ranked candidate list (score, product_id, evidence) plus retrieval/intent metadata."""
    started = time.monotonic()
    constrained = any(x is not None and x is not False for x in (budget, lat, installment or None, open_now or None))
    intent = {'categories': [], 'accessory_categories': []}
    hidden_accessories = 0
    with c.connect() as db:
        lexical_ids = lexical(db, query, category)
        if query_tokens(query) and not category:
            intent = detect_intent(db, query, lexical_ids)
            # Second pass: full recall inside the target categories (e.g. phones are not buried under cases).
            extra = []
            for cat in intent['categories'][:3]:
                extra.extend(lexical(db, query, cat['id'], k=200))
            if extra:
                seen = set(extra)
                lexical_ids = list(dict.fromkeys(extra)) + [p for p in lexical_ids if p not in seen]
        vector_hits = embeddings.index.search(query, CANDIDATES) if use_vectors and query_tokens(query) else []
        floor = 0.35 if embeddings.index.meta.get('provider') == 'hashing' else 0.0
        vector_ids = [pid for pid, score in vector_hits if score >= floor]
        if not query_tokens(query):
            where, args = [], []
            if category:
                where.append('p.category_id=?'); args.append(category)
            sql = ('SELECT p.product_id FROM products p LEFT JOIN offers o USING(product_id)' +
                   (' WHERE ' + ' AND '.join(where) if where else '') + ' GROUP BY p.product_id ORDER BY count(o.offer_id) DESC LIMIT ?')
            fused_ids = [r[0] for r in db.execute(sql, args + [CANDIDATES])]
            scores = {pid: 1.0 / (RRF_K + i + 1) for i, pid in enumerate(fused_ids)}
        else:
            scores = _rrf(lexical_ids, vector_ids)
        ordered = sorted(scores, key=scores.get, reverse=True)
        cat_of = {}
        if ordered:
            marks = ','.join('?' * len(ordered))
            cat_of = dict(db.execute(f'SELECT product_id, category_id FROM products WHERE product_id IN ({marks})', ordered).fetchall())
        if category:
            ordered = [p for p in ordered if cat_of.get(p) == category]
        elif intent['categories'] and not include_accessories:
            target = {x['id'] for x in intent['categories']}
            focused = [p for p in ordered if cat_of.get(p) in target]
            no_acc = [p for p in ordered if cat_of.get(p) not in set(intent['accessory_categories'])]
            chosen = focused if len(focused) >= 3 else no_acc if len(no_acc) >= 3 else ordered
            hidden_accessories = len(ordered) - len(chosen)
            ordered = chosen
        evidence = _evidence(db, ordered, budget, lat, lon, radius, installment, open_now)
        head = query_tokens(query)[:1]
        titles = {}
        if head and ordered:
            marks = ','.join('?' * len(ordered))
            titles = {r[0]: r[1] for r in db.execute(f'SELECT product_id,title FROM product_fts WHERE product_id IN ({marks})', ordered)}
        ranked = []
        primary = intent['categories'][0]['id'] if intent['categories'] else None
        for pid in ordered:
            e = evidence.get(pid, {'offers': 0, 'matching_offers': 0, 'shops': 0})
            if constrained and not e['matching_offers']:
                continue
            score = scores[pid] * (1 + 0.08 * math.log1p(e.get('shops', 0)))
            if head and titles.get(pid, '').startswith(head[0]):
                score *= 1.6
            if primary and cat_of.get(pid) == primary:
                score *= 1.4
            ranked.append((score, pid, e))
        ranked.sort(key=lambda x: x[0], reverse=True)
    return {'ranked': ranked, 'lexical_ids': lexical_ids, 'vector_ids': vector_ids, 'intent': intent,
            'hidden_accessories': hidden_accessories, 'elapsed_ms': round((time.monotonic() - started) * 1000, 1),
            'constraints': {'category': category, 'budget': budget, 'lat': lat, 'lon': lon, 'radius': radius,
                            'installment': installment, 'open_now': open_now}}


def card(p: dict, pid: str, e: dict, score: float = 0.0, match=()) -> dict:
    return {
        'product_id': pid, 'persian_title': p.get('persian_title'), 'brand_name': p.get('brand_name'),
        'model': p.get('model'), 'category_name': p.get('category_name'),
        'image_url': (p.get('image_urls') or [None])[0], 'spec_count': len(p.get('specs') or []),
        'specs_preview': [{'key': s.get('key'), 'value': s.get('value')} for s in (p.get('specs') or [])[:4] if isinstance(s, dict)],
        'recorded_min_price': e.get('min_price'), 'recorded_max_price': e.get('max_price'),
        'offer_count': e.get('offers', 0), 'matching_offers': e.get('matching_offers', 0), 'shop_count': e.get('shops', 0),
        'nearest_km': round(e['nearest_km'], 2) if e.get('nearest_km') is not None else None,
        'installment_shops': e.get('installment_shops', 0), 'open_shops': e.get('open_shops', 0),
        'match': list(match), 'score': round(score, 5),
    }


def payloads(ids: list[str]) -> dict:
    if not ids:
        return {}
    with c.connect() as db:
        marks = ','.join('?' * len(ids))
        return {r[0]: json.loads(r[1]) for r in db.execute(f'SELECT product_id,payload FROM products WHERE product_id IN ({marks})', ids)}


def search(query: str = '', category: str | None = None, budget: int | None = None, page: int = 0, limit: int = 12,
           lat: float | None = None, lon: float | None = None, radius: float | None = None,
           installment: bool = False, open_now: bool = False, use_vectors: bool = True,
           include_accessories: bool = False) -> dict:
    r = rank(query, category, budget, lat, lon, radius, installment, open_now, use_vectors, include_accessories)
    ranked = r['ranked']
    window = ranked[page * limit:(page + 1) * limit]
    data = payloads([w[1] for w in window])
    lexical_set, vector_set = set(r['lexical_ids']), set(r['vector_ids'])
    results = [card(data[pid], pid, e, score, [m for m, s_ in (('lexical', lexical_set), ('semantic', vector_set)) if pid in s_])
               for score, pid, e in window]
    return {'total': len(ranked), 'results': results, 'page': page, 'limit': limit,
            'intent': {'categories': r['intent']['categories'], 'hidden_accessories': r['hidden_accessories'],
                       'include_accessories': include_accessories},
            'retrieval': {'lexical_candidates': len(r['lexical_ids']), 'vector_candidates': len(r['vector_ids']),
                          'vector_index': embeddings.index.info()['model'] if embeddings.index.ready else None,
                          'elapsed_ms': r['elapsed_ms']},
            'constraints': r['constraints']}


def _percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))]


def facets(query: str, budget=None, lat=None, lon=None, radius=None, installment=False, open_now=False) -> dict:
    """What does the catalogue actually offer for this need? Grounds the agent's follow-up questions."""
    r = rank(query, None, budget, lat, lon, radius, installment, open_now)
    ranked = [x for x in r['ranked'] if x[2].get('matching_offers')][:250]
    data = payloads([x[1] for x in ranked])
    prices = [x[2]['min_price'] for x in ranked if x[2].get('min_price')]
    brands, specs = {}, {}
    for _, pid, _e in ranked:
        p = data[pid]
        brand = p.get('brand_name')
        for s_ in p.get('specs') or []:
            if not isinstance(s_, dict) or not s_.get('value'):
                continue
            key = s_.get('key')
            if not brand and key in ('برند', 'شرکت سازنده', 'سازنده'):
                brand = s_['value']
            if key in ('نام محصول', 'مدل', 'تاریخ معرفی', 'برند', 'شرکت سازنده', 'سازنده'):
                continue
            value = str(s_['value'])[:40]
            specs.setdefault(key, {}).setdefault(value, 0)
            specs[key][value] += 1
        if brand:
            brands[str(brand).strip()] = brands.get(str(brand).strip(), 0) + 1
    top_specs = sorted(specs.items(), key=lambda kv: -sum(kv[1].values()))[:5]
    return {
        'query': query, 'products_with_inperson_offers': len(ranked),
        'categories': r['intent']['categories'],
        'price_toman': {'min': _percentile(prices, 0), 'p25': _percentile(prices, .25), 'median': _percentile(prices, .5),
                        'p75': _percentile(prices, .75), 'max': _percentile(prices, 1)} if prices else None,
        'brands': [{'name': k, 'products': v} for k, v in sorted(brands.items(), key=lambda kv: -kv[1])[:8]],
        'spec_facets': [{'key': k, 'values': [{'value': v, 'products': n} for v, n in sorted(vals.items(), key=lambda kv: -kv[1])[:6]]}
                        for k, vals in top_specs],
        'examples': [data[pid].get('persian_title') for _, pid, _e in ranked[:6]],
    }
