"""Conservative text evidence extraction; no inference from missing attributes."""

import re
import unicodedata

# Source-language aliases are encoded to keep code and reports ASCII-only.
GB = "\u06af\u06cc\u06af\u0627\u0628\u0627\u06cc\u062a"
TB = "\u062a\u0631\u0627\u0628\u0627\u06cc\u062a"
STORAGE = "\u062d\u0627\u0641\u0638\u0647"
INTERNAL = "\u062f\u0627\u062e\u0644\u06cc"
CAPACITY = "\u0638\u0631\u0641\u06cc\u062a"
RAM = "\u0631\u0645"
RAM_ALT = "\u0631\u0627\u0645"
USED = {"used", "refurbished", "\u0627\u0633\u062a\u0648\u06a9", "\u06a9\u0627\u0631\u06a9\u0631\u062f\u0647"}


def normalize_text(text):
    text = unicodedata.normalize("NFKC", text or "").casefold()
    text = text.translate({0x064A: 0x06CC, 0x0643: 0x06A9, 0x200C: 32, 0x0640: None})
    text = "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)
    for alias, unit in ((GB, "gb"), (TB, "tb"), ("gigabyte", "gb"), ("terabyte", "tb")):
        text = re.sub(re.escape(alias), unit, text)
    return re.sub(r"(\d)(gb|tb)\b", r"\1 \2", text)


def tokens(text):
    return set(re.findall(r"[^\W_]+", normalize_text(text), flags=re.UNICODE))


def storage_values(text):
    text = normalize_text(text)
    values = set()
    label = rf"(?:{STORAGE}(?:\s+{INTERNAL})?|{CAPACITY}|storage)"
    for match in re.finditer(rf"\b{label}\s*[:=-]?\s*(\d+)\s*(gb|tb)?\b", text):
        value = int(match[1]) * (1024 if match[2] == "tb" else 1)
        # A bare capacity is accepted only for typical phone storage sizes.
        if value >= 32:
            values.add(value)
    for match in re.finditer(r"\b(\d+)\s*(gb|tb)\b", text):
        prefix = text[max(0, match.start()-20):match.start()]
        suffix = text[match.end():match.end()+20]
        if re.search(rf"(?:{RAM}|{RAM_ALT}|ram)\s*[:=-]?\s*$", prefix) or re.match(rf"\s*(?:{RAM}|{RAM_ALT}|ram)\b", suffix):
            continue
        value = int(match[1]) * (1024 if match[2] == "tb" else 1)
        if value >= 32:
            values.add(value)
    return values


def query_terms(text):
    normalized = normalize_text(text)
    normalized = re.sub(r"\b(\d+)\s*(gb|tb)\b", lambda m: " " if int(m[1]) * (1024 if m[2] == "tb" else 1) >= 32 else m[0], normalized)
    normalized = re.sub(rf"\b(?:storage|{STORAGE}(?:\s+{INTERNAL})?|{CAPACITY})\s*[:=-]?\s*\d+\b", " ", normalized)
    return tokens(normalized)


def condition_hint(text):
    return "used_or_refurbished_mentioned" if tokens(text) & USED else "unknown"
