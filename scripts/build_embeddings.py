"""Build the product vector index used by hybrid search.

Examples
  python -m scripts.build_embeddings                      # provider from .env (openai if a key exists)
  python -m scripts.build_embeddings --provider openai --model text-embedding-3-small --dimensions 512
  python -m scripts.build_embeddings --provider local --model BAAI/bge-m3
  python -m scripts.build_embeddings --provider hashing   # offline, no model
  python -m scripts.build_embeddings --limit 2000          # quick trial

The build is resumable: finished batches are kept in data/processed/embedding_parts/ and
skipped on the next run. Restart the server afterwards to load the new index.
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

from backend import config  # noqa: F401  (loads .env)
from backend import embeddings as e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--provider', choices=['openai', 'local', 'hashing'])
    ap.add_argument('--model')
    ap.add_argument('--dimensions', type=int)
    ap.add_argument('--batch', type=int)
    ap.add_argument('--limit', type=int, help='only embed the first N products (trial run)')
    ap.add_argument('--database', default=os.getenv('CATALOG_DATABASE', 'data/processed/catalog.sqlite'))
    args = ap.parse_args()

    cfg = e.settings(args.provider)
    if args.model: cfg['model'] = args.model
    if args.dimensions: cfg['dimensions'] = args.dimensions
    if cfg['provider'] == 'openai' and not cfg['api_key']:
        sys.exit('Set OPENAI_API_KEY (or EMBEDDING_API_KEY) in .env, or use --provider hashing/local.')
    batch = args.batch or {'openai': 256, 'local': 64, 'hashing': 2000}[cfg['provider']]

    out = Path(args.database).parent
    parts = out / 'embedding_parts'
    signature = f"{cfg['provider']}|{cfg['model']}|{cfg['dimensions']}|{args.limit}"
    if parts.exists() and (parts / 'signature.txt').exists() and (parts / 'signature.txt').read_text() != signature:
        shutil.rmtree(parts)
    parts.mkdir(parents=True, exist_ok=True)
    (parts / 'signature.txt').write_text(signature)

    db = sqlite3.connect(args.database)
    sql = 'SELECT product_id, payload FROM products ORDER BY rowid' + (f' LIMIT {int(args.limit)}' if args.limit else '')
    rows = db.execute(sql).fetchall()
    db.close()
    ids = [r[0] for r in rows]
    print(f"Embedding {len(rows):,} products with {cfg['provider']}:{cfg['model']} (dims={cfg['dimensions']}, batch={batch})")
    if cfg['provider'] == 'openai':
        chars = sum(len(e.product_text(json.loads(r[1]))) for r in rows)
        print(f'~{chars/2.5/1e6:.1f}M tokens (rough); text-embedding-3-small is about $0.02 per 1M tokens')

    started = time.monotonic()
    count = (len(rows) + batch - 1) // batch
    for n in range(count):
        target = parts / f'part_{n:05d}.npy'
        if target.exists():
            continue
        chunk = rows[n * batch:(n + 1) * batch]
        texts = [e.product_text(json.loads(p)) for _, p in chunk]
        for attempt in range(5):
            try:
                vectors = e.embed(texts, cfg, kind='passage')
                break
            except Exception as exc:
                wait = 2 ** attempt * 3
                print(f'  batch {n}: {type(exc).__name__}: {str(exc)[:160]} - retry in {wait}s')
                time.sleep(wait)
        else:
            sys.exit('Giving up; run the command again to resume.')
        np.save(target, vectors.astype(np.float16))
        done = n + 1
        rate = done / max(1e-6, time.monotonic() - started)
        print(f'  {done}/{count} batches  ({(count-done)/max(rate,1e-6)/60:.1f} min left)', end='\r', flush=True)
    print()

    matrix = np.concatenate([np.load(parts / f'part_{n:05d}.npy') for n in range(count)])
    np.save(out / e.MATRIX, matrix.astype(np.float16))
    (out / e.IDS).write_text('\n'.join(ids), encoding='utf-8')
    (out / e.META).write_text(json.dumps({'provider': cfg['provider'], 'model': cfg['model'], 'dimensions': int(matrix.shape[1]),
                                          'rows': int(matrix.shape[0]), 'built_at': time.strftime('%Y-%m-%dT%H:%M:%S')}, indent=2), encoding='utf-8')
    shutil.rmtree(parts)
    print(f'Wrote {matrix.shape[0]:,} x {matrix.shape[1]} vectors ({matrix.nbytes/2**20:.0f} MB) in {time.monotonic()-started:.0f}s. Restart the server.')


if __name__ == '__main__':
    main()
