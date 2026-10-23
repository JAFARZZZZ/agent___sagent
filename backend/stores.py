"""Store intelligence: opening hours, installment providers, in-mall location, areas,
explainable seller ranking and (simulated) seller follow-up with alternatives."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from datetime import datetime, timedelta, timezone

from backend import catalog as c

TEHRAN = timezone(timedelta(hours=3, minutes=30))  # Iran has no DST since 2022
DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']  # datetime.weekday() order
FA_DAYS = {'sat': 'شنبه', 'sun': 'یکشنبه', 'mon': 'دوشنبه', 'tue': 'سه‌شنبه', 'wed': 'چهارشنبه', 'thu': 'پنجشنبه', 'fri': 'جمعه'}
INSTALLMENT = {'ترب‌پی', 'اسنپ‌پی', 'دیجی پی', 'تارا', 'ازکی‌وام'}
FA_DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def fa(value) -> str:
    return str(value).translate(FA_DIGITS)


def distance_km(lat1, lon1, lat2, lon2) -> float:
    a, b = math.radians(float(lat1)), math.radians(float(lat2))
    x = math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(math.radians(float(lon2) - float(lon1)) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(max(0.0, min(1.0, x))))


# ------------------------------------------------------------ payment

def installment_providers(shop: dict) -> list[dict]:
    seen = {}
    for option in shop.get('payment_options') or []:
        name = (option or {}).get('provider_name')
        if name in INSTALLMENT:
            channel = option.get('channel') or 'unknown'
            if name not in seen or channel == 'in_person':
                seen[name] = {'provider': name, 'channel': channel, 'in_person_confirmed': channel == 'in_person'}
    return list(seen.values())


# ------------------------------------------------------------ hours

def _minutes(value: str) -> int:
    h, m, *_ = (value or '0:0').split(':')
    return int(h) * 60 + int(m)


def _shifts(day: dict) -> list[tuple[int, int]]:
    out = []
    for s in (day or {}).get('shifts') or []:
        start, end = _minutes(s.get('start_time')), _minutes(s.get('end_time'))
        if start == end == 0:
            continue
        out.append((start, end if end > start else 24 * 60))
    return out


def _hhmm(minutes: int) -> str:
    return fa(f'{minutes // 60:02d}:{minutes % 60:02d}') if minutes < 24 * 60 else fa('24:00')


def open_status(shop: dict, now: datetime | None = None) -> dict:
    hours = shop.get('weekly_hours') or {}
    if not any(isinstance(d, dict) and d.get('status') == 'declared' for d in hours.values()):
        return {'status': 'unknown', 'label': 'ساعت کاری ثبت نشده', 'today': None}
    now = (now or datetime.now(TEHRAN)).astimezone(TEHRAN)
    key = DAYS[now.weekday()]
    minute = now.hour * 60 + now.minute
    today = hours.get(key) or {}
    shifts = _shifts(today) if today.get('status') == 'declared' else []
    today_label = '، '.join(f'{_hhmm(a)} تا {_hhmm(b)}' for a, b in shifts) or 'تعطیل'
    for start, end in shifts:
        if start <= minute < end:
            left = end - minute
            return {'status': 'open', 'label': f'باز است · تا {_hhmm(end)}', 'closing_soon': left <= 45,
                    'minutes_left': left, 'today': today_label}
    # Find next opening within a week.
    for offset in range(0, 8):
        day_key = DAYS[(now.weekday() + offset) % 7]
        day = hours.get(day_key) or {}
        if day.get('status') != 'declared':
            continue
        for start, _ in _shifts(day):
            if offset == 0 and start <= minute:
                continue
            when = 'امروز' if offset == 0 else 'فردا' if offset == 1 else FA_DAYS[day_key]
            return {'status': 'closed', 'label': f'بسته · باز می‌شود {when} {_hhmm(start)}', 'today': today_label,
                    'opens_in_minutes': offset * 1440 + start - minute}
    return {'status': 'closed', 'label': 'بسته', 'today': today_label}


def weekly_table(shop: dict) -> list[dict]:
    hours = shop.get('weekly_hours') or {}
    rows = []
    for key in ['sat', 'sun', 'mon', 'tue', 'wed', 'thu', 'fri']:
        day = hours.get(key) or {}
        if day.get('status') == 'declared':
            text = '، '.join(f'{_hhmm(a)} تا {_hhmm(b)}' for a, b in _shifts(day)) or 'تعطیل'
        elif day.get('status') == 'closed':
            text = 'تعطیل'
        else:
            text = 'نامشخص'
        rows.append({'day': FA_DAYS[key], 'hours': text})
    return rows


# ------------------------------------------------------------ in-mall location

MALL = re.compile(r'((?:پاساژ|مجتمع(?:\s+تجاری)?|مرکز\s+(?:تجاری|خرید|تجارت)|بازار(?:چه)?|تیمچه|سرای|سرا|برج|ساختمان|مال)\s+[^،,\-\n]{2,40})')
FLOOR = re.compile(r'(?:طبقه|ط\.?)\s*(همکف|زیرزمین|زیر\s*همکف|منفی\s*\d+|اول|دوم|سوم|چهارم|پنجم|ششم|هفتم|\d+|[۰-۹]+)')
UNIT = re.compile(r'(?:واحد|غرفه|مغازه)\s*(?:شماره\s*)?([\d۰-۹]+(?:\s*[a-zA-Z؀-ۿ])?)')
PLATE = re.compile(r'پلاک\s*([\d۰-۹]+(?:\.0)?(?:\s*/\s*[\d۰-۹]+)?)')


def mall_location(address: str | None) -> dict:
    address = address or ''
    mall = MALL.search(address)
    floor = FLOOR.search(address)
    unit = UNIT.search(address)
    plate = PLATE.search(address)
    info = {
        'mall': mall.group(1).strip() if mall else None,
        'floor': floor.group(1).strip() if floor else None,
        'unit': unit.group(1).strip() if unit else None,
        'plate': plate.group(1).replace('.0', '').strip() if plate else None,
    }
    parts = []
    if info['mall']:
        parts.append(info['mall'])
    if info['floor']:
        parts.append('طبقه ' + fa(info['floor']))
    if info['unit']:
        parts.append('واحد ' + fa(info['unit']))
    info['summary'] = '، '.join(parts) or None
    return info


# ------------------------------------------------------------ areas (offline geocoder)

_areas: list[dict] | None = None


def areas() -> list[dict]:
    global _areas
    if _areas is None:
        groups: dict[str, list[tuple[float, float]]] = {}
        with c.connect() as db:
            for label, lat, lon in db.execute("SELECT json_extract(payload,'$.location_label'), lat, lon FROM shops WHERE lat IS NOT NULL"):
                if label:
                    groups.setdefault(label.strip(), []).append((lat, lon))
        out = []
        for label, points in groups.items():
            lats = sorted(p[0] for p in points); lons = sorted(p[1] for p in points)
            out.append({'name': label, 'lat': lats[len(lats) // 2], 'lon': lons[len(lons) // 2], 'shops': len(points)})
        _areas = sorted(out, key=lambda a: -a['shops'])
    return _areas


EXTRA_PLACES = {  # well-known shopping hubs that are not location labels in the dataset
    'جمهوری': (35.6978, 51.4105), 'لاله زار': (35.6950, 51.4190), 'لاله‌زار': (35.6950, 51.4190),
    'منوچهری': (35.6965, 51.4170), 'امین حضور': (35.6930, 51.4250), 'بازار': (35.6750, 51.4220),
    'پامنار': (35.6800, 51.4250), 'ولیعصر': (35.7300, 51.4100), 'ونک': (35.7580, 51.4090),
    'میرداماد': (35.7600, 51.4330), 'صادقیه': (35.7180, 51.3350), 'تهرانپارس': (35.7380, 51.5300),
    'نارمک': (35.7350, 51.5000), 'سعادت آباد': (35.7800, 51.3700), 'پونک': (35.7620, 51.3300),
    'شریعتی': (35.7500, 51.4430), 'هفت تیر': (35.7150, 51.4260), 'انقلاب': (35.7010, 51.3900),
    'آزادی': (35.6990, 51.3380), 'ستارخان': (35.7130, 51.3520), 'شهرک غرب': (35.7580, 51.3700),
}


def find_area(text: str) -> dict | None:
    from scripts.product_text import normalize_text
    norm = normalize_text(text)
    best = None
    for a in areas():
        name = normalize_text(a['name'])
        if len(name) >= 3 and name in norm and (best is None or len(name) > len(normalize_text(best['name']))):
            best = a
    if best:
        return best
    for name, (lat, lon) in EXTRA_PLACES.items():
        if normalize_text(name) in norm:
            return {'name': name, 'lat': lat, 'lon': lon, 'shops': None, 'approximate': True}
    return None


# ------------------------------------------------------------ ranking

def freshness(raw) -> dict:
    if not raw:
        return {'status': 'unknown', 'age_days': None, 'label': 'زمان تغییر قیمت نامشخص'}
    try:
        dt = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age = max(0, (datetime.now(timezone.utc) - dt).days)
    except (ValueError, TypeError):
        return {'status': 'unknown', 'age_days': None, 'label': 'زمان تغییر قیمت نامشخص'}
    label = 'قیمت امروز ثبت شده' if age == 0 else f'قیمت {fa(age)} روز پیش ثبت شده'
    return {'status': 'stale' if age >= 30 else 'recent', 'age_days': age, 'label': label}


def shop_card(shop: dict, lat=None, lon=None) -> dict:
    distance = None
    if lat is not None and lon is not None and shop.get('lat') not in (None, 'null'):
        distance = round(distance_km(lat, lon, shop['lat'], shop['lon']), 2)
    contacts = shop.get('contacts') or []
    return {
        'shop_id': shop.get('shop_id'), 'name': shop.get('name'), 'address': shop.get('address'),
        'area': shop.get('location_label'), 'lat': float(shop['lat']) if shop.get('lat') not in (None, 'null') else None,
        'lon': float(shop['lon']) if shop.get('lon') not in (None, 'null') else None,
        'distance_km': distance, 'open': open_status(shop), 'hours': weekly_table(shop),
        'installment': installment_providers(shop), 'mall': mall_location(shop.get('address')),
        'fast_delivery': shop.get('supports_fast_delivery'),
        'instagram': shop.get('instagram'), 'website': shop.get('website_url'),
        'contacts': [{'channel': x.get('channel'), 'number': x.get('display_number')} for x in contacts if isinstance(x, dict)],
        'contacts_are_demo': True,
    }


def ranked_stores(product_id: str, lat=None, lon=None, radius=None, budget=None, installment=False,
                  open_now=False, exclude_shop=None, exclude_offer=None, limit=30) -> dict:
    offers = c.offers(product_id)
    per_shop: dict[str, dict] = {}
    for o in offers:
        if o['offer_id'] == exclude_offer or o['shop_id'] == exclude_shop:
            continue
        current = per_shop.get(o['shop_id'])
        price = int(o['price_toman']) if o.get('price_toman') else None
        if current is None or (price and (current['price'] is None or price < current['price'])):
            per_shop[o['shop_id']] = {'offer': o, 'price': price}
    rows, excluded = [], {'budget': 0, 'radius': 0, 'installment': 0, 'closed': 0}
    for shop_id, entry in per_shop.items():
        o = entry['offer']
        card = shop_card(o['shop'], lat, lon)
        price = entry['price']
        if budget is not None and (price is None or price > budget):
            excluded['budget'] += 1; continue
        if radius and card['distance_km'] is not None and card['distance_km'] > radius:
            excluded['radius'] += 1; continue
        if installment and not card['installment']:
            excluded['installment'] += 1; continue
        if open_now and card['open']['status'] != 'open':
            excluded['closed'] += 1; continue
        rows.append({
            'offer_id': o['offer_id'], 'product_id': product_id, 'price_toman': price,
            'seller_title': o.get('seller_title'), 'warranty': o.get('warranty'), 'description': o.get('description'),
            'freshness': freshness(o.get('last_price_changed_at')), 'last_price_changed_at': o.get('last_price_changed_at'),
            'inventory': 'unknown', 'shop': card,
        })
    prices = [r['price_toman'] for r in rows if r['price_toman']]
    dists = [r['shop']['distance_km'] for r in rows if r['shop']['distance_km'] is not None]
    lo, hi = (min(prices), max(prices)) if prices else (0, 0)
    dmax = max(dists) if dists else 0
    for r in rows:
        p = r['price_toman']
        price_score = 1 - ((p - lo) / (hi - lo)) if p and hi > lo else (1.0 if p else 0.3)
        d = r['shop']['distance_km']
        dist_score = (1 - d / dmax) if d is not None and dmax > 0 else (1.0 if d is not None else 0.5)
        status = r['shop']['open']['status']
        open_score = {'open': 1.0, 'unknown': 0.5, 'closed': 0.15}[status]
        fresh_score = {'recent': 1.0, 'unknown': 0.5, 'stale': 0.2}[r['freshness']['status']]
        weights = (0.45, 0.30, 0.15, 0.10) if lat is not None else (0.70, 0.0, 0.18, 0.12)
        r['score'] = round(weights[0] * price_score + weights[1] * dist_score + weights[2] * open_score + weights[3] * fresh_score, 4)
    rows.sort(key=lambda r: -r['score'])
    if rows:
        tags = {}
        cheapest = min((r for r in rows if r['price_toman']), key=lambda r: r['price_toman'], default=None)
        nearest = min((r for r in rows if r['shop']['distance_km'] is not None), key=lambda r: r['shop']['distance_km'], default=None)
        tags[rows[0]['offer_id']] = ['best_choice']
        if cheapest: tags.setdefault(cheapest['offer_id'], []).append('cheapest')
        if nearest: tags.setdefault(nearest['offer_id'], []).append('nearest')
        for r in rows:
            reasons = tags.get(r['offer_id'], [])[:]
            if r['shop']['open']['status'] == 'open': reasons.append('open_now')
            if r['shop']['installment']: reasons.append('installment')
            if r['freshness']['status'] == 'recent': reasons.append('fresh_price')
            r['reasons'] = reasons
    summary = None
    if rows:
        summary = {'shops': len(rows), 'min_price': lo or None, 'max_price': hi or None,
                   'open_now': sum(r['shop']['open']['status'] == 'open' for r in rows),
                   'installment': sum(bool(r['shop']['installment']) for r in rows),
                   'nearest_km': min(dists) if dists else None}
    return {'product_id': product_id, 'results': rows[:limit], 'total': len(rows), 'excluded': excluded, 'summary': summary,
            'ranking': 'قیمت ۴۵٪، فاصله ۳۰٪، باز بودن ۱۵٪، تازگی قیمت ۱۰٪' if lat is not None else 'قیمت ۷۰٪، باز بودن ۱۸٪، تازگی قیمت ۱۲٪ (موقعیت شما مشخص نیست)'}


# ------------------------------------------------------------ seller follow-up (simulated)

AUTO_REPLY_SECONDS = float(os.getenv('SELLER_AUTO_REPLY_SECONDS', '6'))


def simulated_reply(offer: dict, shop: dict) -> dict:
    """Deterministic demo reply. The dataset has fake phone numbers, so no real call happens."""
    seed = int(hashlib.sha256((offer['offer_id'] + datetime.now(TEHRAN).strftime('%Y%m%d')).encode()).hexdigest(), 16)
    roll = seed % 100
    status = open_status(shop)
    price = int(offer['price_toman']) if offer.get('price_toman') else None
    if status['status'] == 'closed' and roll % 3 == 0:
        return {'answered': False, 'inventory': 'unknown', 'visit': 'unknown', 'price': None,
                'notes': 'مغازه الان بسته است و کسی پاسخ نداد.'}
    if roll < 12:
        return {'answered': False, 'inventory': 'unknown', 'visit': 'unknown', 'price': None, 'notes': 'فروشنده پاسخ نداد.'}
    if roll < 30:
        return {'answered': True, 'inventory': 'unavailable', 'visit': 'possible', 'price': None,
                'notes': 'این کالا فعلاً موجود نیست.'}
    change = ((seed >> 8) % 11 - 3) / 100  # -3% .. +7%
    new_price = int(round(price * (1 + change), -4)) if price else None
    note = 'موجود است. ' + ('قیمت تغییری نکرده.' if change == 0 or not price else f'قیمت به‌روز شده.')
    return {'answered': True, 'inventory': 'available', 'visit': 'possible', 'price': new_price, 'notes': note}
