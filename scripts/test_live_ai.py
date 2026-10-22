"""Opt-in real provider smoke test; never logs credentials or raw provider errors."""
import json
from pathlib import Path
from backend import app as a
from backend import catalog as c
from backend.agent.orchestrator import run

c.initialize()
sid=a.create(a.Preferences())['id']
try:
    with c.connect() as db:
        row=db.execute('SELECT p.payload FROM products p JOIN offers o USING(product_id) GROUP BY p.product_id HAVING count(*)>2 LIMIT 1').fetchone()
    title=json.loads(row[0])['persian_title']
    result=run(sid,'این کالای واقعی را جستجو کن و پیشنهادهای فروشگاه‌هایش را با ابزار دریافت کن: '+title)
    report={'response_type':result.response_type,'warnings':result.warnings,'metrics':result.metrics,'components':[{'tool':x['tool'],'records':len(x['data']) if isinstance(x['data'],list) else len(x['data'].get('results',[]))} for x in result.components]}
    Path('outputs/evaluation/live_agent_smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
    assert any(x['tool']=='search_products' for x in result.components),'No successful product search'
    assert any(x['tool']=='get_product_offers' for x in result.components),'No successful offers retrieval'
finally:
    with c.connect() as db: db.execute('DELETE FROM sessions WHERE id=?',(sid,))
