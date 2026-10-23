"""Price grounding: exact Persian price strings for the model, and a checker that finds prices in the
model's text that do not exist in the tool data (so they can be corrected before the user sees them)."""
from __future__ import annotations

import re

FA = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
TO_FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
UNITS = {'میلیارد': 1_000_000_000, 'میلیون': 1_000_000, 'ملیون': 1_000_000, 'هزار': 1_000}
PRICE = re.compile(r'(\d[\d٬,]*(?:[.٫/]\d+)?)\s*(میلیارد|میلیون|ملیون|هزار)?\s*(تومان|تومن)?')


def text(price: int | None) -> str | None:
    """Exact human string, e.g. 2,450,000 -> '۲٬۴۵۰٬۰۰۰ تومان'."""
    if not price:
        return None
    return f'{int(price):,}'.replace(',', '٬').translate(TO_FA) + ' تومان'


def mentions(message: str) -> list[tuple[str, int, tuple[int, int]]]:
    """Price-like mentions with a unit (میلیون/هزار/تومان); bare numbers such as 256GB are ignored.
    Returns (original text, value in toman, span in the original message)."""
    norm = message.translate(FA)  # 1:1 character mapping keeps spans valid
    out = []
    for m in PRICE.finditer(norm):
        number, unit, currency = m.group(1), m.group(2), m.group(3)
        if not unit and not currency:
            continue
        try:
            value = float(number.replace('٬', '').replace(',', '').replace('٫', '.').replace('/', '.')) * UNITS.get(unit or '', 1)
        except ValueError:
            continue
        if value < 1000:
            continue
        start, end = m.span()
        out.append((message[start:end].strip(), int(value), (start, end)))
    return out


def collect(obj, bag: set[int]) -> set[int]:
    """All integer prices found in tool results (any key containing price/budget, plus percentile blocks)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k).lower()
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v and ('price' in key or 'budget' in key or key in ('min', 'max', 'p25', 'p75', 'median')):
                bag.add(int(v))
            else:
                collect(v, bag)
    elif isinstance(obj, list):
        for v in obj:
            collect(v, bag)
    return bag


def unverified(message: str, known: set[int], tolerance: float = 0.03) -> list[str]:
    return [raw for raw, value, _ in mentions(message) if not any(abs(value - k) <= tolerance * k for k in known)]


def strip(message: str, known: set[int], tolerance: float = 0.03) -> str:
    """Replace unverifiable prices in place with a pointer to the card."""
    for raw, value, (a, b) in reversed(mentions(message)):
        if not any(abs(value - k) <= tolerance * k for k in known):
            message = message[:a] + '(قیمت روی کارت)' + message[b:]
    return message
