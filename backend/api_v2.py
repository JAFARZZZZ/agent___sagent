"""Endpoints for the chat + map interface: hybrid search, explainable store ranking,
areas, and seller follow-up (inquiries) with automatic alternatives."""
from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend import catalog as c
from backend import embeddings
from backend import search as hybrid
from backend import stores

router = APIRouter()


def _app():
    from backend import app as a
    return a


def prefs(sid: str | None) -> dict:
    if not sid:
        return {}
    try:
        return _app().session(sid).get('preferences', {})
    except KeyError:
        return {}


@router.get('/api/search')
def search_products(q: str = Query('', max_length=300), category: str | None = None,
                    budget: int | None = Query(None, gt=0), lat: float | None = Query(None, ge=-90, le=90),
                    lon: float | None = Query(None, ge=-180, le=180), radius: float | None = Query(None, gt=0, le=100),
                    installment: bool = False, open_now: bool = False, page: int = Query(0, ge=0), limit: int = Query(12, ge=1, le=48)):
    return hybrid.search(q, category, budget, page, limit, lat, lon, radius, installment, open_now)


@router.get('/api/search/info')
def search_info():
    return {'vector_index': embeddings.index.info(), 'fusion': 'RRF k=60', 'lexical': 'FTS5 weighted BM25'}


@router.get('/api/products/{pid}/stores')
def product_stores(pid: str, lat: float | None = Query(None, ge=-90, le=90), lon: float | None = Query(None, ge=-180, le=180),
                   radius: float | None = Query(None, gt=0, le=100), budget: int | None = Query(None, gt=0),
                   installment: bool = False, open_now: bool = False, limit: int = Query(30, ge=1, le=100),
                   priorities: str | None = Query(None, max_length=80)):
    product = c.record('products', 'product_id', pid)
    order = [x for x in (priorities or '').split(',') if x]
    result = stores.ranked_stores(pid, lat, lon, radius, budget, installment, open_now, limit=limit, priorities=order)
    result['product'] = slim_product(product)
    return result


@router.get('/api/shops/{shop_id}/card')
def shop_card(shop_id: str, lat: float | None = None, lon: float | None = None):
    return stores.shop_card(c.record('shops', 'shop_id', shop_id), lat, lon)


@router.get('/api/areas')
def list_areas():
    return stores.areas()


@router.get('/api/geocode')
def geocode(q: str = Query(..., min_length=2, max_length=100)):
    area = stores.find_area(q)
    if not area:
        raise HTTPException(404, 'Area not found')
    return area


def slim_product(p: dict) -> dict:
    return {'product_id': p.get('product_id'), 'persian_title': p.get('persian_title'), 'brand_name': p.get('brand_name'),
            'model': p.get('model'), 'category_name': p.get('category_name'), 'image_url': (p.get('image_urls') or [None])[0],
            'image_urls': (p.get('image_urls') or [])[:4],
            'specs': [{'key': s.get('key'), 'value': s.get('value'), 'section': s.get('section')} for s in (p.get('specs') or []) if isinstance(s, dict)][:40]}


@router.get('/api/products/{pid}/full')
def product_full(pid: str):
    return slim_product(c.record('products', 'product_id', pid))


class CompareRequest(BaseModel):
    ids: list[str] = Field(min_length=2, max_length=4)
    session_id: str | None = None


@router.post('/api/compare/table')
def compare_table(body: CompareRequest):
    return compare(body.ids, prefs(body.session_id))


def compare(ids: list[str], p: dict | None = None) -> dict:
    p = p or {}
    products = [slim_product(c.record('products', 'product_id', i)) for i in ids]
    keys: list[str] = []
    for prod in products:
        for s in prod['specs']:
            if s['key'] and s['key'] not in keys:
                keys.append(s['key'])
    rows = []
    for key in keys:
        values = [next((s['value'] for s in prod['specs'] if s['key'] == key), None) for prod in products]
        if sum(v is not None for v in values) >= 2 or len(products) == 2:
            rows.append({'key': key, 'values': values, 'differs': len({v for v in values if v is not None}) > 1})
    market = []
    for prod in products:
        r = stores.ranked_stores(prod['product_id'], p.get('lat'), p.get('lon'), p.get('radius'), p.get('budget'),
                                 bool(p.get('installment')), False, limit=1)
        market.append(r['summary'] or {'shops': 0})
    return {'products': products, 'rows': rows[:30], 'market': market,
            'note': 'مشخصات همان‌طور که در دیتاست ثبت شده نمایش داده می‌شود؛ ردیف‌های خالی یعنی اطلاعات ثبت نشده.'}


# ------------------------------------------------------------ seller follow-up

class InquiryRequest(BaseModel):
    offer_id: str
    questions: list[str] = Field(default_factory=lambda: ['inventory', 'price', 'hours'])


@router.post('/api/sessions/{sid}/inquiries')
def create_inquiry(sid: str, body: InquiryRequest):
    return start_inquiry(sid, body.offer_id, body.questions)


def start_inquiry(sid: str, offer_id: str, questions=None) -> dict:
    a = _app()
    s = a.session(sid)
    offer = c.record('offers', 'offer_id', offer_id)
    rid = uuid.uuid4().hex
    with c.connect() as db:
        db.execute('INSERT INTO confirmations VALUES (?,?,?,?,NULL)', (rid, sid, offer_id, time.time()))
    s.setdefault('inquiries', []).append({'id': rid, 'offer_id': offer_id, 'shop_id': offer['shop_id'],
                                          'product_id': offer['product_id'], 'questions': questions or [], 'created': time.time()})
    s['inquiries'] = s['inquiries'][-20:]
    s.update(offer_id=offer_id, confirmation_id=rid, state='CONFIRMATION_PENDING')
    a.save(sid, s)
    return inquiry_status(sid, rid)


@router.get('/api/sessions/{sid}/inquiries/{rid}')
def get_inquiry(sid: str, rid: str):
    return inquiry_status(sid, rid)


def inquiry_status(sid: str, rid: str) -> dict:
    a = _app()
    with c.connect() as db:
        row = db.execute('SELECT * FROM confirmations WHERE id=? AND session_id=?', (rid, sid)).fetchone()
    if not row:
        raise KeyError(rid)
    offer = c.record('offers', 'offer_id', row['offer_id'])
    shop = c.record('shops', 'shop_id', offer['shop_id'])
    response = json.loads(row['response']) if row['response'] else None
    elapsed = time.time() - row['created']
    if response is None and elapsed >= stores.AUTO_REPLY_SECONDS:
        reply = stores.simulated_reply(offer, shop)
        response = {**reply, 'simulated': True, 'auto': True, 'responded_at': time.time()}
        with c.connect() as db:
            db.execute('UPDATE confirmations SET response=? WHERE id=? AND response IS NULL', (json.dumps(response, ensure_ascii=False), rid))
    p = a.session(sid).get('preferences', {})
    status, needs_alternative = 'calling', False
    if response is not None:
        over_budget = bool(response.get('price') and p.get('budget') and response['price'] > p['budget'])
        if response.get('answered') is False:
            status, needs_alternative = 'no_answer', True
        elif response.get('inventory') == 'unavailable' or response.get('visit') == 'not_possible' or over_budget:
            status, needs_alternative = 'unavailable' if response.get('inventory') == 'unavailable' else 'issue', True
        else:
            status = 'confirmed'
        response['over_budget'] = over_budget
    s = a.session(sid)
    if s.get('confirmation_id') == rid and response is not None:
        s['state'] = 'ALTERNATIVE_REQUIRED' if needs_alternative else 'CONFIRMATION_RECEIVED'
        a.save(sid, s)
    alternatives = []
    if needs_alternative:
        alt = stores.ranked_stores(offer['product_id'], p.get('lat'), p.get('lon'), p.get('radius'), p.get('budget'),
                                   bool(p.get('installment')), False, exclude_shop=offer['shop_id'], limit=6,
                                   priorities=['open'] + list(p.get('priorities') or []))
        alternatives = alt['results'][:3]
    old_price = int(offer['price_toman']) if offer.get('price_toman') else None
    return {'id': rid, 'status': status, 'elapsed_s': round(elapsed, 1), 'expected_s': stores.AUTO_REPLY_SECONDS,
            'offer_id': offer['offer_id'], 'product_id': offer['product_id'],
            'shop': stores.shop_card(shop, p.get('lat'), p.get('lon')), 'recorded_price_toman': old_price,
            'response': response, 'alternatives': alternatives, 'simulated': True,
            'disclaimer': 'شماره‌های دیتاست ساختگی است؛ تماس و پاسخ فروشنده در این دمو شبیه‌سازی می‌شود (یا از پنل فروشنده ثبت می‌شود).'}


# ------------------------------------------------------------ streaming agent

class AgentMessage(BaseModel):
    message: str = Field(default='', max_length=2000)
    image: str | None = Field(default=None, max_length=4_000_000, description='data:image/...;base64 photo from the user')


@router.post('/api/sessions/{sid}/agent')
def agent_stream(sid: str, body: AgentMessage):
    from fastapi.responses import StreamingResponse
    from backend.agent.chat_agent import run_stream
    _app().session(sid)  # 404 early for unknown sessions
    if not body.message.strip() and not body.image:
        raise HTTPException(422, 'Empty message')
    if body.image and not body.image.startswith('data:image/'):
        raise HTTPException(422, 'Image must be a data:image URL')

    def events():
        for event in run_stream(sid, body.message.strip(), image=body.image):
            yield 'data: ' + json.dumps(event, ensure_ascii=False, default=str) + '\n\n'
    return StreamingResponse(events(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@router.get('/api/sessions/{sid}/summary')
def session_summary(sid: str):
    s = _app().session(sid)
    return {'preferences': s.get('preferences', {}), 'chat_history': s.get('chat_history', []),
            'selected_product_id': s.get('selected_product_id'), 'inquiries': s.get('inquiries', [])}


class PrefsPatch(BaseModel):
    budget: int | None = Field(default=None, gt=0)
    clear_budget: bool = False
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    area: str | None = Field(default=None, max_length=100)
    clear_location: bool = False
    radius: float | None = Field(default=None, gt=0, le=100)
    installment: bool | None = None
    open_now: bool | None = None
    priorities: list[str] | None = None


@router.patch('/api/sessions/{sid}/preferences')
def patch_preferences(sid: str, body: PrefsPatch):
    a = _app()
    s = a.session(sid)
    p = dict(s.get('preferences', {}))
    patch = body.model_dump(exclude_unset=True)
    if patch.pop('clear_budget', False):
        p['budget'] = None
    if patch.pop('clear_location', False):
        p.update(lat=None, lon=None, area=None)
    p.update({k: v for k, v in patch.items() if v is not None or k == 'area'})
    s['preferences'] = a.Preferences.model_validate(p).model_dump()
    a.save(sid, s)
    return s['preferences']


# ------------------------------------------------------------ map explore: listings in the viewport

_listing_cache: dict = {}


@router.get('/api/map/listings')
def map_listings(q: str = Query('', max_length=300), category: str | None = None,
                 budget: int | None = Query(None, gt=0), installment: bool = False, open_now: bool = False,
                 include_accessories: bool = False, lat: float | None = None, lon: float | None = None,
                 products: int = Query(120, ge=1, le=300)):
    """Every Tehran shop that carries one of the best-matching products (one card per shop: its best match).
    Returned in one response and cached, so the map can pan/zoom without new requests."""
    if not q.strip() and not category:
        return {'listings': [], 'total_shops': 0, 'products': 0, 'note': 'FILTER_FIRST'}
    started = time.monotonic()
    key = (q.strip(), category, budget, installment, open_now, include_accessories, products, int(time.time() // 60) if open_now else 0)
    hit = _listing_cache.get(key)
    if hit and time.monotonic() - hit[0] < 300:
        result = hit[1]
    else:
        result = _build_listings(q, category, budget, installment, open_now, include_accessories, products)
        if len(_listing_cache) > 64:
            _listing_cache.clear()
        _listing_cache[key] = (time.monotonic(), result)
    listings = result['listings']
    if lat is not None and lon is not None:
        listings = [{**x, 'distance_km': round(stores.distance_km(lat, lon, x['lat'], x['lon']), 2)} for x in listings]
    return {**result, 'listings': listings, 'elapsed_ms': round((time.monotonic() - started) * 1000, 1), 'cached': bool(hit)}


def _build_listings(q, category, budget, installment, open_now, include_accessories, products):
    r = hybrid.rank(q, category, budget, None, None, None, installment, open_now, include_accessories=include_accessories)
    ranked = [x for x in r['ranked'] if x[2].get('matching_offers')][:products]
    order = {pid: i for i, (_, pid, _) in enumerate(ranked)}
    if not order:
        return {'listings': [], 'total_shops': 0, 'products': 0, 'intent': r['intent']['categories'], 'hidden_accessories': r['hidden_accessories']}
    marks = ','.join('?' * len(order))
    sql = f'''SELECT o.offer_id, o.product_id, o.price_toman, json_extract(o.payload,'$.last_price_changed_at'), s.shop_id, s.lat, s.lon, s.payload
              FROM offers o JOIN shops s USING(shop_id) WHERE o.product_id IN ({marks}) AND s.lat IS NOT NULL'''
    best: dict[str, dict] = {}
    counts: dict[str, set] = {}
    shop_payload: dict[str, dict] = {}
    with c.connect() as db:
        for offer_id, pid, price, changed, shop_id, slat, slon, spayload in db.execute(sql, list(order)):
            price = int(price) if price else None
            if budget is not None and (not price or price > budget):
                continue
            if shop_id not in shop_payload:
                shop_payload[shop_id] = json.loads(spayload)
            if installment and not stores.installment_providers(shop_payload[shop_id]):
                continue
            k = (order[pid], price or 9e18)
            counts.setdefault(shop_id, set()).add(pid)
            if shop_id not in best or k < best[shop_id]['key']:
                best[shop_id] = {'key': k, 'offer_id': offer_id, 'product_id': pid, 'price': price, 'lat': slat, 'lon': slon, 'changed': changed}
    data = hybrid.payloads(list({b['product_id'] for b in best.values()}))
    listings = []
    for shop_id, b in best.items():
        shop = shop_payload[shop_id]
        status = stores.open_status(shop)
        if open_now and status['status'] != 'open':
            continue
        p = data.get(b['product_id'], {})
        listings.append({
            'shop_id': shop_id, 'shop_name': shop.get('name'), 'lat': b['lat'], 'lon': b['lon'], 'area': shop.get('location_label'),
            'open': {'status': status['status'], 'label': status['label']}, 'installment': [x['provider'] for x in stores.installment_providers(shop)],
            'mall': stores.mall_location(shop.get('address'))['summary'], 'distance_km': None,
            'offer_id': b['offer_id'], 'price_toman': b['price'], 'freshness': stores.freshness(b['changed']),
            'product': {'product_id': b['product_id'], 'title': p.get('persian_title'), 'image_url': (p.get('image_urls') or [None])[0],
                        'category': p.get('category_name'), 'rank': b['key'][0]},
            'more_matches': len(counts[shop_id]) - 1,
        })
    listings.sort(key=lambda x: (x['product']['rank'], x['price_toman'] or 9e18))
    return {'listings': listings[:1500], 'total_shops': len(listings), 'products': len(order),
            'intent': r['intent']['categories'], 'hidden_accessories': r['hidden_accessories']}


# ------------------------------------------------------------ voice input

@router.post('/api/transcribe')
async def transcribe(request: Request):
    """Persian speech-to-text through the configured OpenAI-compatible provider (whisper-1 by default)."""
    import os
    from openai import OpenAI
    audio = await request.body()
    if not audio or len(audio) > 15 * 2**20:
        raise HTTPException(422, 'Audio missing or too large')
    if not os.getenv('OPENAI_API_KEY'):
        raise HTTPException(503, 'AI_NOT_CONFIGURED')
    kind = (request.headers.get('content-type') or 'audio/webm').split(';')[0]
    ext = {'audio/webm': 'webm', 'audio/ogg': 'ogg', 'audio/mp4': 'm4a', 'audio/mpeg': 'mp3', 'audio/wav': 'wav'}.get(kind, 'webm')
    client = OpenAI(base_url=os.getenv('OPENAI_BASE_URL') or None, timeout=40, max_retries=0)
    try:
        result = client.audio.transcriptions.create(model=os.getenv('OPENAI_TRANSCRIBE_MODEL') or 'whisper-1',
                                                    file=(f'voice.{ext}', audio, kind), language='fa')
    except Exception as exc:
        raise HTTPException(502, f'TRANSCRIBE_FAILED: {type(exc).__name__}')
    finally:
        client.close()
    return {'text': (getattr(result, 'text', '') or '').strip()}
