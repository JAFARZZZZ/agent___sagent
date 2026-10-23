"""Dense product vectors for the hybrid search.

Three interchangeable providers, selected with EMBEDDING_PROVIDER:

* ``openai`` – any OpenAI-compatible embeddings endpoint (OpenAI, AvalAI, ...).
  Recommended default: ``text-embedding-3-small`` reduced to 512 dimensions.
* ``local``  – a sentence-transformers model on this machine, e.g. ``BAAI/bge-m3``
  or ``intfloat/multilingual-e5-large`` (best open models for Persian on FaMTEB).
* ``hashing`` – zero-dependency character n-gram vectors. Not semantic, but robust to
  typos, half-spaces and joined/split words. Used when no model is configured.

The index lives in ``data/processed/`` as a float16 matrix plus a JSON manifest and an
ID list. Search is a brute-force cosine product (225k x 512 is a few milliseconds).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from pathlib import Path

import numpy as np

from scripts.product_text import normalize_text

log = logging.getLogger(__name__)
INDEX_DIR = Path(os.getenv('EMBEDDING_INDEX_DIR') or Path(os.getenv('CATALOG_DATABASE', 'data/processed/catalog.sqlite')).parent)
MATRIX = 'embeddings.f16.npy'
IDS = 'embeddings.ids.txt'
META = 'embeddings.meta.json'
HASH_DIMS = 512


def settings(provider: str | None = None) -> dict:
    provider = (provider or os.getenv('EMBEDDING_PROVIDER') or '').strip().lower()
    if not provider:
        provider = 'openai' if (os.getenv('EMBEDDING_API_KEY') or os.getenv('OPENAI_API_KEY')) else 'hashing'
    defaults = {'openai': 'text-embedding-3-small', 'local': 'BAAI/bge-m3', 'hashing': 'char-ngram-hash'}
    if provider not in defaults:
        raise ValueError(f'Unknown EMBEDDING_PROVIDER {provider!r}')
    dims = os.getenv('EMBEDDING_DIMENSIONS')
    return {
        'provider': provider,
        'model': os.getenv('EMBEDDING_MODEL') or defaults[provider],
        'dimensions': int(dims) if dims else (512 if provider == 'openai' else HASH_DIMS if provider == 'hashing' else None),
        'base_url': os.getenv('EMBEDDING_BASE_URL') or os.getenv('OPENAI_BASE_URL') or None,
        'api_key': os.getenv('EMBEDDING_API_KEY') or os.getenv('OPENAI_API_KEY') or None,
    }


def product_text(p: dict) -> str:
    """Compact, retrieval-oriented description of a product."""
    parts = [p.get('persian_title') or '']
    if p.get('model'):
        parts.append(str(p['model']))
    if p.get('brand_name'):
        parts.append('برند ' + str(p['brand_name']))
    if p.get('category_name'):
        parts.append('دسته ' + str(p['category_name']))
    specs = p.get('specs') or []
    if isinstance(specs, list):
        useful = [f"{s.get('key')}: {s.get('value')}" for s in specs[:8] if isinstance(s, dict) and s.get('value')]
        parts.extend(useful)
    return ' | '.join(x for x in parts if x)[:600]


# ---------------------------------------------------------------- providers

def _hash_vectors(texts: list[str]) -> np.ndarray:
    out = np.zeros((len(texts), HASH_DIMS), dtype=np.float32)
    for row, text in enumerate(texts):
        text = normalize_text(text)
        for word in re.findall(r'[^\W_]+', text):
            padded = f' {word} '
            grams = [padded[i:i + 3] for i in range(len(padded) - 2)] + [word]
            for g in grams:
                h = int.from_bytes(hashlib.blake2b(g.encode(), digest_size=8).digest(), 'little')
                out[row, h % HASH_DIMS] += 1.0 if (h >> 63) & 1 else -1.0
        # Sub-linear term frequency, then L2 normalisation.
        out[row] = np.sign(out[row]) * np.sqrt(np.abs(out[row]))
    return _normalise(out)


def _normalise(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return (m / norms).astype(np.float32)


_local_models: dict = {}
_lock = threading.Lock()


def embed(texts: list[str], cfg: dict, kind: str = 'passage') -> np.ndarray:
    """Embed texts. ``kind`` is 'query' or 'passage' (needed by e5-style models)."""
    if cfg['provider'] == 'hashing':
        return _hash_vectors(texts)
    if cfg['provider'] == 'openai':
        from openai import OpenAI
        client = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url'], timeout=float(os.getenv('EMBEDDING_TIMEOUT_SECONDS', '20')), max_retries=2)
        kwargs = {'model': cfg['model'], 'input': texts}
        if cfg['dimensions']:
            kwargs['dimensions'] = cfg['dimensions']
        try:
            data = client.embeddings.create(**kwargs).data
        finally:
            client.close()
        return _normalise(np.array([d.embedding for d in sorted(data, key=lambda d: d.index)], dtype=np.float32))
    # local sentence-transformers
    with _lock:
        model = _local_models.get(cfg['model'])
        if model is None:
            from sentence_transformers import SentenceTransformer  # optional dependency
            model = _local_models[cfg['model']] = SentenceTransformer(cfg['model'])
    if 'e5' in cfg['model'].lower():
        texts = [('query: ' if kind == 'query' else 'passage: ') + t for t in texts]
    return _normalise(np.asarray(model.encode(texts, batch_size=32, normalize_embeddings=True), dtype=np.float32))


# ---------------------------------------------------------------- index

class VectorIndex:
    def __init__(self, directory: Path = INDEX_DIR):
        self.directory = Path(directory)
        self.matrix = None
        self.ids: list[str] = []
        self.meta: dict = {}
        self.cfg: dict | None = None
        self.error: str | None = None

    def load(self) -> bool:
        try:
            meta_path = self.directory / META
            if not meta_path.exists():
                self.error = 'NO_INDEX'
                return False
            self.meta = json.loads(meta_path.read_text(encoding='utf-8'))
            self.matrix = np.load(self.directory / MATRIX, mmap_mode='r')
            self.ids = (self.directory / IDS).read_text(encoding='utf-8').split('\n')
            if len(self.ids) != self.matrix.shape[0]:
                raise ValueError('ID list and matrix differ in length')
            cfg = settings(self.meta['provider'])
            cfg['model'] = self.meta['model']
            cfg['dimensions'] = self.meta.get('dimensions')
            self.cfg = cfg
            # Materialise into RAM as float32 for fast BLAS products when it is small enough.
            if self.matrix.nbytes < int(os.getenv('EMBEDDING_MAX_RAM_MB', '1200')) * 2**20:
                self.matrix = np.asarray(self.matrix, dtype=np.float32)
            self.error = None
            log.info('Vector index loaded: %s rows, %s', len(self.ids), self.meta.get('model'))
            return True
        except Exception as exc:  # index is optional; never break lexical search
            self.matrix, self.ids, self.error = None, [], f'{type(exc).__name__}: {exc}'
            log.warning('Vector index unavailable: %s', self.error)
            return False

    @property
    def ready(self) -> bool:
        return self.matrix is not None

    def info(self) -> dict:
        return {'ready': self.ready, 'rows': len(self.ids), 'provider': self.meta.get('provider'),
                'model': self.meta.get('model'), 'dimensions': self.meta.get('dimensions'), 'error': self.error}

    def search(self, query: str, k: int = 300) -> list[tuple[str, float]]:
        if not self.ready or not query.strip():
            return []
        vector = _query_vector(query, json.dumps(self.cfg, sort_keys=True))
        if vector is None:
            return []
        scores = self.matrix @ vector
        k = min(k, len(scores))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(self.ids[i], float(scores[i])) for i in top]


_cache: dict = {}


def _query_vector(query: str, cfg_key: str):
    key = (cfg_key, normalize_text(query))
    if key in _cache:
        return _cache[key]
    try:
        vector = embed([query], json.loads(cfg_key), kind='query')[0]
    except Exception as exc:  # transient failures are not cached
        log.warning('Query embedding failed (%s); falling back to lexical search', type(exc).__name__)
        return None
    if len(_cache) > 2048:
        _cache.clear()
    _cache[key] = vector
    return vector


index = VectorIndex()
