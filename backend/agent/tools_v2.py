"""Agent tools for the chat + map assistant (Chat Completions function calling).

Every tool reads/writes the shopping session, so hard constraints (budget, radius,
installment, open-now, location) are applied consistently across turns and by the UI.
Each result carries a ``ui`` type so the frontend can render real catalog records."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend import api_v2
from backend import catalog as c
from backend import search as hybrid
from backend import stores
from backend.agent import prices as P


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SearchArgs(Strict):
    query: str = Field(description='Short Persian product query: product type + brand/model/key attributes. No budget or location words.', max_length=200)
    category_hint: str | None = Field(default=None, description='Optional Persian category name (from explore_needs) to restrict the search')
    include_accessories: bool = Field(default=False, description='Only true if the user explicitly wants accessories/parts (قاب، گلس، شارژر…)')


class NeedsArgs(Strict):
    query: str = Field(description='Product type the user is thinking about, e.g. «گوشی موبایل» or «هدفون بی سیم»', max_length=120)


class AskArgs(Strict):
    question: str = Field(description='One short, warm Persian question about the most decision-relevant missing need', max_length=220)
    options: list[str] = Field(min_length=2, max_length=6, description='2-6 short tappable answers grounded in explore_needs facts (price bands, brands, use cases)')
    multi: bool = Field(default=False, description='True if the user may pick several options')


class Pick(Strict):
    product_id: str
    reason: str = Field(max_length=200, description='Why this fits THIS user (their need/budget) using real data: price, shops, specs')
    label: str | None = Field(default=None, max_length=30, description='Short badge e.g. «اقتصادی‌ترین», «بهترین دوربین», «پیشنهاد اصلی»')


class RecommendArgs(Strict):
    picks: list[Pick] = Field(min_length=1, max_length=3)


class PhotoArgs(Strict):
    product_ids: list[str] = Field(min_length=1, max_length=6)
    need: str = Field(max_length=200, description='What the user wants, in Persian (type, use, style), so the photos can be judged against it')


class ProductArgs(Strict):
    product_id: str


class CompareArgs(Strict):
    product_ids: list[str] = Field(min_length=2, max_length=4)


class StoresArgs(Strict):
    product_id: str
    sort: Literal['best', 'cheapest', 'nearest', 'open'] = 'best'


class ShopArgs(Strict):
    shop_id: str


class LocationArgs(Strict):
    place: str = Field(description='Neighbourhood / street / mall name in Tehran as the user wrote it')


class PrefArgs(Strict):
    budget_toman: int | None = Field(default=None, gt=0, description='Maximum price in toman (1 million = 1000000)')
    radius_km: float | None = Field(default=None, gt=0, le=50)
    installment_only: bool | None = None
    open_now_only: bool | None = None
    priorities: list[Literal['price', 'distance', 'open', 'installment', 'fresh']] | None = Field(
        default=None, description='What matters most to the user when choosing a SHOP, most important first: price=cheaper, distance=closer, open=open now, installment=credit purchase, fresh=recently updated price. Infer from the conversation or ask.')
    clear_budget: bool = False


class InquiryArgs(Strict):
    offer_id: str


class InquiryStatusArgs(Strict):
    inquiry_id: str


class Empty(Strict):
    pass


SPECS = {
    'explore_needs': (NeedsArgs, 'insight', 'Before asking the user questions: what the catalogue really has for this kind of product (categories, price spread, common brands and spec values, number of products sold in physical shops). Use its facts to craft grounded options.'),
    'ask_user': (AskArgs, 'question', 'Ask ONE friendly clarifying question with tappable options, then stop and wait for the answer. Use while the need is still vague.'),
    'search_products': (SearchArgs, 'products', 'Hybrid (keyword + semantic) search over the Torob catalog. Accessories are hidden automatically unless include_accessories. Session constraints (budget, location radius, installment, open-now) are applied automatically.'),
    'check_product_photos': (PhotoArgs, 'vision', 'Look at the product PHOTOS with a vision model and judge whether each candidate really is what the user wants (not an accessory, toy, wrong type, damaged…). Use on the top 3-6 search candidates before recommending.'),
    'recommend_products': (RecommendArgs, 'picks', 'Present your 1-3 best matches from search results with a personal reason each. Always call after a search that has relevant results.'),
    'get_product_details': (ProductArgs, 'product', 'Full specifications and images of one product.'),
    'compare_products': (CompareArgs, 'compare', 'Side-by-side specification table plus price range and number of in-person shops for 2-4 products.'),
    'find_stores': (StoresArgs, 'stores', 'In-person shops in Tehran that registered an offer for the product, ranked by price, distance, opening hours and price freshness, with reasons, mall/floor/unit and installment providers.'),
    'get_store_details': (ShopArgs, 'shop', 'One shop: address, in-mall location, weekly hours, open-now status, installment providers.'),
    'set_location': (LocationArgs, 'location', 'Resolve a Tehran neighbourhood/street/mall name to coordinates and save it as the user location.'),
    'update_preferences': (PrefArgs, 'preferences', 'Save explicit user constraints: budget, search radius, installment-only, open-now-only. Only send fields the user stated.'),
    'contact_seller': (InquiryArgs, 'inquiry', 'Ask a shop (simulated call) to confirm stock, current price and opening for an offer. Use when the user wants to check before going, or the recorded price is old.'),
    'check_inquiry': (InquiryStatusArgs, 'inquiry', 'Read the status/answer of a seller inquiry; includes alternative shops when the seller has no stock, does not answer, or is over budget.'),
    'get_session': (Empty, None, 'Read current constraints, location, selected product and recent inquiries.'),
}


def schemas() -> list[dict]:
    out = []
    for name, (model, _, desc) in SPECS.items():
        schema = model.model_json_schema()
        schema.pop('title', None)
        for prop in schema.get('properties', {}).values():
            prop.pop('title', None)
        out.append({'type': 'function', 'function': {'name': name, 'description': desc, 'parameters': schema}})
    return out


def _session(sid):
    from backend import app as a
    return a, a.session(sid)


def execute(name: str, arguments: dict, sid: str) -> tuple[str | None, dict]:
    if name not in SPECS:
        raise ValueError('UNKNOWN_TOOL')
    model, ui, _ = SPECS[name]
    args = model.model_validate(arguments)
    a, s = _session(sid)
    p = s.get('preferences', {})

    if name == 'explore_needs':
        r = hybrid.facets(args.query, p.get('budget'), p.get('lat'), p.get('lon'),
                          p.get('radius') if p.get('lat') is not None else None, bool(p.get('installment')), bool(p.get('open_now')))
        return ui, r

    if name == 'ask_user':
        return ui, {'question': args.question, 'options': args.options, 'multi': args.multi}

    if name == 'check_product_photos':
        from backend.agent import vision
        data = hybrid.payloads(args.product_ids)
        products = [{'product_id': pid, 'persian_title': data[pid].get('persian_title'),
                     'image_url': (data[pid].get('image_urls') or [None])[0]} for pid in args.product_ids if pid in data]
        return ui, vision.inspect(products, args.need, reference=vision.REFERENCES.get(sid))

    if name == 'recommend_products':
        ids = [x.product_id for x in args.picks]
        data = hybrid.payloads(ids)
        with c.connect() as db:
            evidence = hybrid._evidence(db, ids, p.get('budget'), p.get('lat'), p.get('lon'),
                                        p.get('radius') if p.get('lat') is not None else None, bool(p.get('installment')), bool(p.get('open_now')))
        picks = []
        for x in args.picks:
            if x.product_id not in data:
                continue
            card = hybrid.card(data[x.product_id], x.product_id, evidence.get(x.product_id, {}))
            own = {v for v in (card['recorded_min_price'], card['recorded_max_price']) if v}
            picks.append({**card, 'reason': P.strip(x.reason, own), 'label': x.label})
        s['selected_product_id'] = picks[0]['product_id'] if picks else s.get('selected_product_id'); a.save(sid, s)
        return ui, {'picks': picks}

    if name == 'search_products':
        category = None
        if args.category_hint:
            hint = args.category_hint.strip()
            match = next((x for x in a.categories() if x['name'] == hint), None) or \
                next((x for x in a.categories() if hint in (x['name'] or '')), None)
            category = match['category_id'] if match else None
        result = hybrid.search(args.query, category, p.get('budget'), 0, 10, p.get('lat'), p.get('lon'),
                               p.get('radius') if p.get('lat') is not None else None, bool(p.get('installment')), bool(p.get('open_now')),
                               include_accessories=args.include_accessories)
        s['preferences'] = {**p, 'query': args.query[:300]}
        s['last_results'] = [r['product_id'] for r in result['results']]
        a.save(sid, s)
        return ui, {**result, 'query': args.query}

    if name == 'get_product_details':
        product = api_v2.slim_product(c.record('products', 'product_id', args.product_id))
        s['selected_product_id'] = args.product_id; a.save(sid, s)
        return ui, product

    if name == 'compare_products':
        return ui, api_v2.compare(args.product_ids, p)

    if name == 'find_stores':
        product = c.record('products', 'product_id', args.product_id)
        result = stores.ranked_stores(args.product_id, p.get('lat'), p.get('lon'),
                                      p.get('radius') if p.get('lat') is not None else None, p.get('budget'),
                                      bool(p.get('installment')), bool(p.get('open_now')), limit=40, priorities=p.get('priorities'))
        key = {'cheapest': lambda r: (r['price_toman'] is None, r['price_toman'] or 0),
               'nearest': lambda r: (r['shop']['distance_km'] is None, r['shop']['distance_km'] or 0),
               'open': lambda r: (r['shop']['open']['status'] != 'open', -r['score'])}.get(args.sort)
        if key:
            result['results'].sort(key=key)
        result['product'] = api_v2.slim_product(product)
        result['sort'] = args.sort
        s['selected_product_id'] = args.product_id; a.save(sid, s)
        return ui, result

    if name == 'get_store_details':
        return ui, stores.shop_card(c.record('shops', 'shop_id', args.shop_id), p.get('lat'), p.get('lon'))

    if name == 'set_location':
        area = stores.find_area(args.place)
        if not area:
            return ui, {'found': False, 'place': args.place,
                        'hint': 'محله پیدا نشد؛ از کاربر بخواه دکمه «موقعیت من» را بزند یا روی نقشه انتخاب کند.',
                        'known_areas': [x['name'] for x in stores.areas()[:20]]}
        s['preferences'] = {**p, 'lat': area['lat'], 'lon': area['lon'], 'area': area['name'], 'radius': p.get('radius') or 5}
        a.save(sid, s)
        return ui, {'found': True, **area, 'radius': s['preferences']['radius']}

    if name == 'update_preferences':
        new = dict(p)
        if args.clear_budget:
            new['budget'] = None
        if args.budget_toman is not None:
            new['budget'] = args.budget_toman
        if args.radius_km is not None:
            new['radius'] = args.radius_km
        if args.installment_only is not None:
            new['installment'] = args.installment_only
        if args.open_now_only is not None:
            new['open_now'] = args.open_now_only
        if args.priorities is not None:
            new['priorities'] = list(dict.fromkeys(args.priorities))
        new = a.Preferences.model_validate(new).model_dump()
        s['preferences'] = new; a.save(sid, s)
        return ui, new

    if name == 'contact_seller':
        return ui, api_v2.start_inquiry(sid, args.offer_id, ['inventory', 'price', 'hours'])

    if name == 'check_inquiry':
        return ui, api_v2.inquiry_status(sid, args.inquiry_id)

    if name == 'get_session':
        return None, {k: v for k, v in s.items() if k not in ('history', 'chat_history', 'last_agent_trace')}
    raise ValueError('UNKNOWN_TOOL')


def compact_for_model(name: str, data: dict) -> dict:
    """Keep the model context small; the UI receives the full records."""
    if name == 'explore_needs':
        return {k: data[k] for k in ('products_with_inperson_offers', 'categories', 'price_toman', 'brands', 'spec_facets', 'examples')}
    if name == 'ask_user':
        return {'asked': True, 'note': 'Question shown with buttons. Stop now and wait for the user.'}
    if name == 'recommend_products':
        return {'shown': [{'product_id': x['product_id'], 'title': x['persian_title'], 'min_price_text': P.text(x['recorded_min_price'])} for x in data['picks']]}
    if name == 'check_product_photos':
        return {'items': [{k: x[k] for k in ('product_id', 'persian_title', 'fits', 'confidence', 'seen', 'issue', 'style')} for x in data['items']]}
    if name == 'search_products':
        return {'total': data['total'], 'constraints': data['constraints'], 'categories': data.get('intent', {}).get('categories'),
                'hidden_accessories': data.get('intent', {}).get('hidden_accessories'), 'results': [
            {'n': i + 1, **{k: r.get(k) for k in ('product_id', 'persian_title', 'brand_name', 'category_name', 'shop_count',
                                                  'nearest_km', 'installment_shops', 'open_shops')},
             'min_price_text': P.text(r.get('recorded_min_price')) or 'قیمت ثبت نشده',
             'max_price_text': P.text(r.get('recorded_max_price')) if r.get('recorded_max_price') != r.get('recorded_min_price') else None,
             'min_price': r.get('recorded_min_price'), 'replica_or_copy': r.get('replica'),
             'price_age_days': r.get('min_price_age_days')}
            for i, r in enumerate(data['results'])]}
    if name == 'find_stores':
        return {'product': data['product']['persian_title'], 'total': data['total'], 'summary': data['summary'],
                'sorted_by_user_priorities': data.get('priorities'), 'priorities_known': data.get('priorities_known'),
                'excluded_by_constraints': data['excluded'], 'ranking': data['ranking'], 'results': [
                    {'n': i + 1, 'offer_id': r['offer_id'], 'shop_id': r['shop']['shop_id'], 'shop': r['shop']['name'],
                     'price_toman': r['price_toman'], 'price_text': P.text(r['price_toman']) or 'قیمت ثبت نشده',
                     'distance_km': r['shop']['distance_km'], 'open': r['shop']['open']['label'], 'mall': r['shop']['mall']['summary'],
                     'installment': [x['provider'] for x in r['shop']['installment']], 'price_age_days': r['freshness']['age_days'],
                     'reasons': r['reasons']} for i, r in enumerate(data['results'][:8])]}
    if name == 'compare_products':
        return {'products': [p['persian_title'] for p in data['products']], 'rows': data['rows'][:15], 'market': data['market']}
    if name == 'get_product_details':
        return {**{k: data[k] for k in ('product_id', 'persian_title', 'brand_name', 'category_name')}, 'specs': data['specs'][:20]}
    if name in ('contact_seller', 'check_inquiry'):
        return {'inquiry_id': data['id'], 'status': data['status'], 'shop': data['shop']['name'], 'response': data['response'],
                'recorded_price_toman': data['recorded_price_toman'],
                'alternatives': [{'offer_id': r['offer_id'], 'shop': r['shop']['name'], 'price_toman': r['price_toman'],
                                  'open': r['shop']['open']['label'], 'distance_km': r['shop']['distance_km']} for r in data['alternatives']]}
    if name == 'get_store_details':
        return {k: data[k] for k in ('shop_id', 'name', 'address', 'distance_km', 'open', 'hours', 'installment', 'mall')}
    return data
