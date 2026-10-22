"""Run with python -m scripts.smoke_test; actual source and DB records only."""
import csv
import json
import os
import uuid
from pathlib import Path
from fastapi.testclient import TestClient
from backend import catalog as c
from backend.app import app

def main():
    report={}; sessions=[]
    os.environ['SELLER_DEMO_SECRET']=uuid.uuid4().hex
    with TestClient(app) as client, c.connect() as db:
        for table in ('products','shops','offers'):
            with Path('data',table+'.csv').open(encoding='utf-8-sig',newline='') as f:
                reader=csv.DictReader(f); cols=reader.fieldnames; count=sum(1 for _ in reader)
            actual=db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
            assert count==actual,(table,count,actual)
            report[table]={'source':count,'database':actual,'columns':cols}
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        assert client.get('/api/health').status_code==200
        assert sum(x['count'] for x in client.get('/api/categories').json())==report['products']['source']
        rows=db.execute('SELECT p.product_id,p.payload,count(*) n FROM products p JOIN offers o USING(product_id) GROUP BY p.product_id ORDER BY n DESC LIMIT 3').fetchall()
        report['samples']=[]
        try:
            for row in rows:
                p=json.loads(row['payload']);pid=row['product_id']
                found=client.get('/api/products',params={'query':p['persian_title']}).json()
                assert pid in {x['product_id'] for x in found['results']}
                assert client.get('/api/products/'+pid).json()['product_id']==pid
                s=client.post('/api/sessions',json={}).json();sid=s['id'];sessions.append(sid)
                offers=client.get(f'/api/sessions/{sid}/offers/{pid}').json()
                assert len(offers)==row['n']
                for o in offers:
                    direct=db.execute('SELECT price_toman,shop_id FROM offers WHERE offer_id=?',(o['offer_id'],)).fetchone()
                    assert o['price_toman']==direct['price_toman']
                    assert o['shop']['shop_id']==direct['shop_id']
                oid=offers[0]['offer_id']
                rid=client.post(f'/api/sessions/{sid}/confirmations',json={'offer_id':oid}).json()['id']
                assert client.post('/api/seller/requests/'+rid,headers={'X-Seller-Token':os.environ['SELLER_DEMO_SECRET']},json={'inventory':'unavailable'}).status_code==200
                plan=client.get(f'/api/sessions/{sid}/plan').json()
                assert plan['inventory_status']=='unavailable'
                assert len(plan['alternatives'])==len(offers)-1
                report['samples'].append({'product_id':pid,'title':p['persian_title'],'offers':len(offers),'shop_id':offers[0]['shop_id']})
            first=client.get('/api/products',params={'page':0}).json()['results']
            second=client.get('/api/products',params={'page':1}).json()['results']
            assert not ({p['product_id'] for p in first}&{p['product_id'] for p in second})
            assert client.get('/api/products',params={'query':'zzzznonexistentxyz'}).json()['total']==0
            # Sample each text mode from actual records, without invented brands/models.
            report['search_modes']=[]
            for label,condition,field in [
                ('english',"json_extract(payload,'$.model') GLOB '*[A-Za-z]*'",'model'),
                ('mixed',"json_extract(payload,'$.persian_title') GLOB '*[A-Za-z]*'",'persian_title'),
                ('brand',"json_extract(payload,'$.brand_name') IS NOT NULL",'brand_name')]:
                sample=db.execute('SELECT payload FROM products WHERE '+condition+' LIMIT 1').fetchone()
                value=json.loads(sample[0])[field]
                result=client.get('/api/products',params={'query':value}).json()
                assert result['total']>0,(label,value)
                report['search_modes'].append({'mode':label,'query':value,'matches':result['total']})
        finally:
            for sid in sessions:
                db.execute('DELETE FROM confirmations WHERE session_id=?',(sid,))
                db.execute('DELETE FROM sessions WHERE id=?',(sid,))
    target=Path('outputs/evaluation/smoke_report.json')
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS: source counts, API search, pagination, exact retrieval, prices, joins, seller confirmation and alternatives')

if __name__=='__main__': main()
