"""Reproducible full-catalog coverage and lexical latency report."""
import json
import time
from pathlib import Path
from backend import catalog as c

def main():
    c.initialize()
    with c.connect() as db:
        counts={t:db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('products','shops','offers','product_search')}
        counts['categories']=db.execute('SELECT count(DISTINCT category_id) FROM products').fetchone()[0]
        counts['foreign_key_violations']=len(db.execute('PRAGMA foreign_key_check').fetchall())
        counts['unindexed_products']=db.execute('SELECT count(*) FROM products p WHERE NOT EXISTS(SELECT 1 FROM product_search f WHERE f.product_id=p.product_id)').fetchone()[0] if counts['products']!=counts['product_search'] else None
        samples=db.execute("SELECT category_id,json_extract(payload,'$.persian_title') title FROM products GROUP BY category_id ORDER BY count(*) DESC LIMIT 5").fetchall()
    timings=[]
    for s in samples:
        query=' '.join((s['title'] or '').split()[:2])
        start=time.perf_counter(); result=c.search(query,category=s['category_id'])
        timings.append({'query':query,'category':s['category_id'],'matches':result['total'],'milliseconds':round((time.perf_counter()-start)*1000,2)})
    out=Path('outputs/evaluation');out.mkdir(parents=True,exist_ok=True)
    (out/'catalog_verification.json').write_text(json.dumps({'counts':counts,'queries':timings},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(counts))

if __name__=='__main__': main()
