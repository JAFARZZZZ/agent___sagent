"""Look at product photos with a vision model and judge whether each item really fits the user's need.

Images are downloaded by this server (the Torob CDN is reachable from Iran, the model provider may not be),
sent inline as data URLs at low detail, and judged in one call. Configure OPENAI_VISION_MODEL
(defaults to OPENAI_MODEL, e.g. gpt-4o-mini / gpt-4o which accept images)."""
from __future__ import annotations

import base64
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import httpx

log = logging.getLogger(__name__)
MAX_BYTES = 1_500_000


def _fetch(url: str) -> str | None:
    try:
        with httpx.Client(timeout=6, follow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'}) as client:
            r = client.get(url)
        if r.status_code != 200 or len(r.content) > MAX_BYTES:
            return None
        mime = r.headers.get('content-type', 'image/jpeg').split(';')[0]
        if not mime.startswith('image/'):
            return None
        return f'data:{mime};base64,' + base64.b64encode(r.content).decode()
    except Exception:
        return None


PROMPT = """You check product photos for an in-person shopping assistant in Tehran.
User need (Persian): {need}
For every numbered product you get its catalogue title and photo. Judge from the PHOTO (and title) whether the item
is really what the user wants. Flag: accessory/part instead of the main product (case, glass, battery, cable, strap…),
toy/replica, wrong product type, clearly used/damaged, or a photo that does not show the product.
Answer ONLY JSON: {{"items":[{{"n":1,"fits":true,"confidence":0.0-1.0,"seen":"<what the photo shows, short Persian>",
"issue":"<short Persian problem or empty>","style":"<short Persian note on look/colour/quality if useful>"}}]}}"""


def inspect(products: list[dict], need: str, client=None) -> dict:
    from openai import OpenAI
    model = os.getenv('OPENAI_VISION_MODEL') or os.getenv('OPENAI_MODEL')
    if not model or not (os.getenv('OPENAI_API_KEY') or client):
        raise RuntimeError('AI_NOT_CONFIGURED')
    urls = [p.get('image_url') for p in products]
    with ThreadPoolExecutor(max_workers=6) as pool:
        inline = list(pool.map(lambda u: _fetch(u) if u else None, urls))
    content = [{'type': 'text', 'text': PROMPT.format(need=need)}]
    for n, (p, data, url) in enumerate(zip(products, inline, urls), 1):
        content.append({'type': 'text', 'text': f"#{n}: {p.get('persian_title')}"})
        if data or url:
            content.append({'type': 'image_url', 'image_url': {'url': data or url, 'detail': 'low'}})
        else:
            content.append({'type': 'text', 'text': '(no photo available)'})
    own = client is None
    client = client or OpenAI(timeout=float(os.getenv('OPENAI_TIMEOUT_SECONDS', '45')), max_retries=0,
                              base_url=os.getenv('OPENAI_BASE_URL') or None)
    try:
        r = client.chat.completions.create(model=model, messages=[{'role': 'user', 'content': content}],
                                           response_format={'type': 'json_object'}, temperature=0, max_tokens=900)
        raw = r.choices[0].message.content or '{}'
    finally:
        if own:
            client.close()
    try:
        items = json.loads(raw).get('items', [])
    except json.JSONDecodeError:
        items = []
    by_n = {int(x.get('n', 0)): x for x in items if isinstance(x, dict)}
    out = []
    for n, p in enumerate(products, 1):
        v = by_n.get(n, {})
        out.append({'product_id': p['product_id'], 'persian_title': p.get('persian_title'), 'image_url': p.get('image_url'),
                    'fits': bool(v.get('fits', True)), 'confidence': float(v.get('confidence') or 0),
                    'seen': v.get('seen') or '', 'issue': v.get('issue') or '', 'style': v.get('style') or '',
                    'photo_checked': bool(inline[n - 1] or urls[n - 1]) and bool(v)})
    return {'need': need, 'items': out, 'model': model}
