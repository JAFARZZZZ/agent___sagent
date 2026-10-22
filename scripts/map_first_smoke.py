import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient
from backend.app import app
from backend import catalog as c

with TestClient(app) as client:
    q={'west':50,'east':52,'south':35,'north':36,'zoom':9}
    coarse=client.get('/api/map/clusters',params=q).json()
    fine=client.get('/api/map/clusters',params={**q,'zoom':14}).json()
    with c.connect() as db:
        count=db.execute('SELECT count(*) FROM offers o JOIN shops s USING(shop_id) WHERE s.lat BETWEEN 35 AND 36 AND s.lon BETWEEN 50 AND 52').fetchone()[0]
    assert coarse['viewport_offers']==count==fine['viewport_offers']
    assert len(fine['cells'])>=len(coarse['cells'])
    assert coarse['geolocated_offers']+coarse['non_geolocated_offers']==coarse['all_offers']==331506
    cell=coarse['cells'][0];size=coarse['cell_degrees']
    bounds={'west':cell['gx']*size,'east':(cell['gx']+1)*size,'south':cell['gy']*size,'north':(cell['gy']+1)*size}
    stores=client.get('/api/map/stores',params=bounds).json()
    assert stores['total']>0
    shop=stores['results'][0]
    offers=client.get(f"/api/stores/{shop['shop_id']}/offers").json()
    assert offers['total']>0 and all(x['shop_id']==shop['shop_id'] for x in offers['results'])

report=[];errors=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True)
    for width in [320,360,375,390,430,768,1024,1440]:
        page=browser.new_page(viewport={'width':width,'height':900})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8003',wait_until='domcontentloaded')
        page.wait_for_function('window.mapCoverage && document.querySelectorAll(".cluster-icon").length>0',timeout=60000)
        assert page.locator('#map').is_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        page.locator('.cluster-icon').first.click()
        page.wait_for_timeout(400)
        if page.locator('#store-panel').is_visible() and page.locator('#store-panel button').count()>0:
            page.locator('#store-panel button').first.click()
            page.locator('[data-offer-id]').first.wait_for(timeout=30000)
            assert page.locator('.carousel [data-offer-id]').count()>0
        page.locator('.chat-link').click()
        assert page.url.endswith('/chat')
        assert page.locator('#message').is_visible()
        page.get_by_role('link',name='بازگشت به نقشه').click()
        page.wait_for_function('window.mapCoverage')
        report.append({'width':width,'clusters':page.locator('.cluster-icon').count(),'overflow':False})
        page.close()
    browser.close()
assert not errors,errors
out=Path('outputs/evaluation/map_first_report.json');out.write_text(json.dumps({'coverage':{k:coarse[k] for k in ['all_offers','geolocated_offers','non_geolocated_offers']},'viewports':report,'errors':errors},indent=2),encoding='utf-8')
print(json.dumps(report))
