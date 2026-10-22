"""Indexed, category-independent retrieval over the complete source catalog."""
import json
import os
import sqlite3
from backend import config
from contextlib import contextmanager
from scripts.product_text import normalize_text, tokens
from scripts.search_catalog import distance_km

DATABASE = os.getenv('CATALOG_DATABASE', 'data/processed/catalog.sqlite')

@contextmanager
def connect():
    db = sqlite3.connect(DATABASE, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()

def initialize():
    with connect() as db:
        db.executescript('''
        CREATE VIRTUAL TABLE IF NOT EXISTS product_search USING fts5(product_id UNINDEXED, text);
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS confirmations(id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
          offer_id TEXT NOT NULL, created REAL NOT NULL, response TEXT);
        CREATE INDEX IF NOT EXISTS confirmation_session ON confirmations(session_id);
        ''')
        if db.execute('SELECT count(*) FROM product_search').fetchone()[0] != db.execute('SELECT count(*) FROM products').fetchone()[0]:
            db.execute('DELETE FROM product_search')
            for row in db.execute('SELECT product_id,payload FROM products'):
                p = json.loads(row['payload'])
                text = ' '.join(str(p.get(k) or '') for k in ('persian_title','model','brand_name','category_name','specs'))
                db.execute('INSERT INTO product_search VALUES (?,?)', (row['product_id'], normalize_text(text)))

def record(table, key, value):
    with connect() as db:
        row = db.execute(f'SELECT * FROM {table} WHERE {key}=?', (value,)).fetchone()
        if row is None:
            raise KeyError(value)
        result = dict(row)
        raw=json.loads(result.pop('payload'))
        if table=='offers': raw['source_price_toman']=raw.get('price_toman')
        result={**raw,**result}
        return result

def search(query='', category=None, budget=None, page=0, limit=24):
    clauses, args = [], []
    join = ''
    if tokens(query):
        join = 'JOIN product_search f ON f.product_id=p.product_id'
        clauses.append('product_search MATCH ?')
        args.append(' AND '.join('"'+t+'"*' for t in sorted(tokens(query))))
    if category:
        clauses.append('p.category_id=?'); args.append(category)
    if budget is not None:
        clauses.append('EXISTS(SELECT 1 FROM offers o WHERE o.product_id=p.product_id AND o.price_toman>0 AND o.price_toman<=?)'); args.append(budget)
    where = ' WHERE '+' AND '.join(clauses) if clauses else ''
    with connect() as db:
        total = db.execute('SELECT count(*) FROM products p '+join+where, args).fetchone()[0]
        rows = db.execute('SELECT p.product_id,p.payload,(SELECT min(price_toman) FROM offers o WHERE o.product_id=p.product_id AND price_toman>0) price, (SELECT count(*) FROM offers o WHERE o.product_id=p.product_id) sellers FROM products p '+join+where+' ORDER BY p.product_id LIMIT ? OFFSET ?', args+[limit,page*limit])
        return {'total':total,'results':[dict(json.loads(r['payload']), recorded_min_price=r['price'], offer_count=r['sellers']) for r in rows]}

def offers(product_id, budget=None, lat=None, lon=None, radius=10, exclude=None):
    with connect() as db:
        rows = db.execute('SELECT o.*,s.lat,s.lon,s.payload shop FROM offers o JOIN shops s USING(shop_id) WHERE product_id=?', (product_id,))
        result = []
        for row in rows:
            r = dict(row)
            if r['offer_id']==exclude or (budget is not None and (r['price_toman'] is None or r['price_toman']>budget)): continue
            distance = distance_km(lat,lon,r['lat'],r['lon']) if lat is not None and lon is not None and r['lat'] is not None and r['lon'] is not None else None
            if lat is not None and (distance is None or distance>radius): continue
            raw=json.loads(r.pop('payload'))
            raw['source_price_toman']=raw.get('price_toman')
            r={**raw,**r}
            r['shop'] = json.loads(r['shop']); r['distance_km'] = distance
            r['inventory_status'] = 'unknown'
            result.append(r)
        return sorted(result,key=lambda r: (int(r['price_toman']) if r['price_toman'] else float('inf'), r['offer_id']))
