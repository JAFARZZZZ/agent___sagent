import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from backend import app as a
from backend import catalog as c
from backend.agent.orchestrator import run
from backend.agent.query import CatalogQuery, query
from backend.agent.tools import execute

class Item:
    type='function_call'
    name='search_products'
    arguments='{"query":""}'
    call_id='call-1'
    def model_dump(self,**kwargs): return {'type':self.type,'name':self.name,'arguments':self.arguments,'call_id':self.call_id}

class AgentTests(unittest.TestCase):
    def setUp(self):
        c.initialize()
        self.sid=a.create(a.Preferences(budget=1000000))['id']
    def tearDown(self):
        with c.connect() as db:
            db.execute('DELETE FROM sessions WHERE id=?',(self.sid,))
    def test_multiround_real_tool_and_history(self):
        calls=[]
        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output=[Item()] if len(calls)==1 else [],usage=SimpleNamespace(total_tokens=12),output_text='نتایج ثبت‌شده')
        client=SimpleNamespace(responses=SimpleNamespace(create=create))
        result=run(self.sid,'کالاهای زیر یک میلیون',client)
        self.assertEqual(len(calls),2)
        self.assertEqual(result.metrics['total_tokens'],24)
        self.assertTrue(result.components[0]['data']['results'])
        self.assertTrue(all(p['recorded_min_price']<=1000000 for p in result.components[0]['data']['results']))
        self.assertEqual(a.session(self.sid)['history'][-1]['content'],'نتایج ثبت‌شده')
    def test_unconfigured_fallback_and_no_secret(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'','OPENAI_MODEL':''}):
            result=run(self.sid,'سلام')
        self.assertIn('AI_NOT_CONFIGURED',result.warnings)
        self.assertEqual(result.response_type,'ERROR')
    def test_dsl_rejects_injection(self):
        with self.assertRaises(ValueError): query(CatalogQuery(entity='products',select=['payload; DROP TABLE products']))
        result=query(CatalogQuery(entity='offers',aggregate='count'))
        self.assertEqual(result['results'][0]['value'],331506)
        result=query(CatalogQuery(entity='products',filters=[{'field':'product_id','op':'eq','value':"' OR 1=1 --"}]))
        self.assertEqual(result['results'],[])
    def test_preference_mutation_keeps_budget(self):
        execute('update_shopping_preferences',{'radius':5},self.sid)
        self.assertEqual(a.session(self.sid)['preferences']['budget'],1000000)
        with self.assertRaises(ValueError): execute('update_shopping_preferences',{'budget':None},self.sid)
        with self.assertRaises(ValueError): execute('process_seller_response',{},self.sid)
