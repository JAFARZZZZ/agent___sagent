import json
import unittest
from datetime import datetime
from types import SimpleNamespace as N

from fastapi.testclient import TestClient

from backend import catalog as c
from backend import search, stores
from backend.app import app


class StoreLogicTests(unittest.TestCase):
    HOURS = {'sat': {'status': 'declared', 'shifts': [{'start_time': '10:00:00', 'end_time': '18:00:00'}]},
             'fri': {'status': 'closed', 'shifts': []}}

    def test_open_status(self):
        sat_noon = datetime(2026, 10, 24, 12, 0, tzinfo=stores.TEHRAN)  # a Saturday
        self.assertEqual(stores.open_status({'weekly_hours': self.HOURS}, sat_noon)['status'], 'open')
        sat_night = datetime(2026, 10, 24, 20, 0, tzinfo=stores.TEHRAN)
        self.assertEqual(stores.open_status({'weekly_hours': self.HOURS}, sat_night)['status'], 'closed')
        self.assertEqual(stores.open_status({'weekly_hours': {}})['status'], 'unknown')

    def test_mall_and_installment(self):
        m = stores.mall_location('خیابان حافظ، مجتمع علاالدین، طبقه 5، واحد 521')
        self.assertEqual((m['floor'], m['unit']), ('5', '521'))
        self.assertIn('علاالدین', m['mall'])
        shop = {'payment_options': [{'provider_name': 'اسنپ‌پی', 'channel': 'in_person'}, {'provider_name': 'دکان ابزار', 'channel': 'unknown'}]}
        self.assertEqual([x['provider'] for x in stores.installment_providers(shop)], ['اسنپ‌پی'])

    def test_query_tokens_drop_chat_and_budget_words(self):
        self.assertEqual(search.query_tokens('یه گوشی سامسونگ تا ۳۰ میلیون میخوام'), ['گوشی', 'سامسونگ'])


class HybridApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c.initialize()

    def test_relevance_and_constraints(self):
        with TestClient(app) as client:
            r = client.get('/api/search', params={'q': 'گوشی سامسونگ'}).json()
            self.assertTrue(r['results'][0]['persian_title'].startswith('گوشی'))
            budget = client.get('/api/search', params={'q': 'هدفون بی سیم', 'budget': 3000000}).json()
            self.assertTrue(budget['results'])
            self.assertTrue(all(p['recorded_min_price'] <= 3000000 for p in budget['results']))
            pid = r['results'][1]['product_id']
            st = client.get(f'/api/products/{pid}/stores', params={'lat': 35.70, 'lon': 51.42, 'installment': True}).json()
            self.assertTrue(all(row['shop']['installment'] for row in st['results']))

    def test_inquiry_flow_with_alternatives(self):
        with TestClient(app) as client:
            sid = client.post('/api/sessions', json={}).json()['id']
            with c.connect() as db:
                pid = db.execute('SELECT product_id FROM offers GROUP BY product_id HAVING count(DISTINCT shop_id)>5 LIMIT 1').fetchone()[0]
            st = client.get(f'/api/products/{pid}/stores').json()
            first = client.post(f'/api/sessions/{sid}/inquiries', json={'offer_id': st['results'][0]['offer_id']}).json()
            self.assertEqual(first['status'], 'calling')
            old, stores.AUTO_REPLY_SECONDS = stores.AUTO_REPLY_SECONDS, 0
            try:
                done = client.get(f'/api/sessions/{sid}/inquiries/{first["id"]}').json()
            finally:
                stores.AUTO_REPLY_SECONDS = old
            self.assertNotEqual(done['status'], 'calling')
            self.assertTrue(done['simulated'])
            if done['status'] != 'confirmed':
                self.assertTrue(done['alternatives'])
                self.assertNotIn(done['shop']['shop_id'], [a['shop']['shop_id'] for a in done['alternatives']])

    def test_streaming_agent_with_fake_model(self):
        from backend.agent.chat_agent import run_stream
        with TestClient(app) as client:
            sid = client.post('/api/sessions', json={}).json()['id']
        calls = []

        def create(**kw):
            calls.append(kw)
            if len(calls) == 1:
                tc = N(id='a', type='function', function=N(name='update_preferences', arguments=json.dumps({'budget_toman': 5000000})))
            elif len(calls) == 2:
                tc = N(id='b', type='function', function=N(name='search_products', arguments=json.dumps({'query': 'ساعت هوشمند'})))
            else:
                return N(choices=[N(message=N(content='دو گزینه پیدا کردم.', tool_calls=None))])
            return N(choices=[N(message=N(content='', tool_calls=[tc]))])
        events = list(run_stream(sid, 'ساعت هوشمند زیر ۵ میلیون', client=N(chat=N(completions=N(create=create)))))
        kinds = [e['type'] for e in events]
        self.assertIn('component', kinds)
        products = next(e for e in events if e.get('ui') == 'products')['data']['results']
        self.assertTrue(products and all(p['recorded_min_price'] <= 5000000 for p in products))
        self.assertEqual(events[-1]['type'], 'done')
        self.assertEqual(events[-1]['preferences']['budget'], 5000000)


if __name__ == '__main__':
    unittest.main()
