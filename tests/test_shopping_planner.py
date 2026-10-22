import json
import unittest
from backend import catalog as c
from backend import shopping

class PlannerTests(unittest.TestCase):
    def test_real_multi_product_plans_cover_every_item(self):
        with c.connect() as db:
            rows=db.execute("SELECT p.product_id FROM products p JOIN offers o USING(product_id) WHERE o.price_toman>0 GROUP BY p.product_id ORDER BY count(*) DESC LIMIT 3").fetchall()
        basket=shopping.Basket(items=[shopping.BasketItem(product_id=r[0]) for r in rows])
        result=shopping.optimize(basket,35.7,51.4)
        self.assertEqual(result['unresolved'],[])
        ids={r[0] for r in rows}
        for plan in result['plans']:
            covered={item['product_id'] for stop in plan['stops'] for item in stop['items']}
            self.assertEqual(covered,ids)
            self.assertGreater(plan['recorded_total_toman'],0)
            self.assertEqual(plan['distance_kind'],'straight_line_approximation')

    def test_freshness_uses_price_update_only(self):
        self.assertEqual(shopping.freshness(None)['status'],'unknown')
        self.assertEqual(shopping.freshness('2020-01-01T00:00:00+00:00')['status'],'stale')
