import os
import unittest
import uuid
from fastapi.testclient import TestClient
from backend.app import app
from backend import catalog as c

class WebJourney(unittest.TestCase):
    def test_real_catalog_journey(self):
        os.environ['SELLER_TOKEN']=uuid.uuid4().hex
        headers={'X-Seller-Token':os.environ['SELLER_TOKEN']}
        with TestClient(app) as client:
            counts=client.get('/api/health').json()
            self.assertEqual(counts['products'],225903)
            self.assertEqual(counts['shops'],6476)
            self.assertEqual(counts['offers'],331506)
            self.assertEqual(counts['product_search'],counts['products'])
            categories=client.get('/api/categories').json()
            self.assertEqual(sum(x['count'] for x in categories),counts['products'])
            self.assertEqual(client.get('/api/seller/requests').status_code,403)
            self.assertEqual(client.post('/api/sessions',json={'lat':35}).status_code,422)
            for category in categories[:3]:
                r=client.post('/api/sessions',json={'category':category['category_id']}).json()
                sid=r['id']
                try:
                    ps=r['products']['results']
                    self.assertTrue(ps)
                    self.assertEqual(client.post('/api/compare',json=[p['product_id'] for p in ps[:2]]).status_code,200)
                    p=next(p for p in ps if p['offer_count'])
                    offers=client.get(f'/api/sessions/{sid}/offers/{p["product_id"]}').json()
                    oid=offers[0]['offer_id']
                    rid=client.post(f'/api/sessions/{sid}/confirmations',json={'offer_id':oid}).json()['id']
                    self.assertEqual(client.get(f'/api/sessions/{sid}/plan').json()['inventory_status'],'unknown')
                    response=client.post(f'/api/seller/requests/{rid}',headers=headers,json={'inventory':'unavailable','visit':'possible'})
                    self.assertEqual(response.status_code,200)
                    plan=client.get(f'/api/sessions/{sid}/plan').json()
                    self.assertEqual(plan['inventory_status'],'unavailable')
                    self.assertTrue(all(o['offer_id']!=oid for o in plan['alternatives']))
                    self.assertTrue(all(o['product_id']==p['product_id'] for o in plan['alternatives']))
                    self.assertEqual(client.get(f'/api/sessions/{sid}').json()['state'],'ALTERNATIVE_REQUIRED')
                finally:
                    with c.connect() as db:
                        db.execute('DELETE FROM confirmations WHERE session_id=?',(sid,))
                        db.execute('DELETE FROM sessions WHERE id=?',(sid,))
            self.assertEqual(client.get('/api/products',params={'query':'zzzznonexistentmodel'}).json()['total'],0)
            cheap=client.get('/api/products',params={'budget':1}).json()
            self.assertTrue(all(0<p['recorded_min_price']<=1 for p in cheap['results']))
