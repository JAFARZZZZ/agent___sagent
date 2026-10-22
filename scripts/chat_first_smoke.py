import json
from playwright.sync_api import sync_playwright
from backend import catalog as c

with c.connect() as db:
    p=json.loads(db.execute("SELECT p.payload FROM products p JOIN offers o USING(product_id) GROUP BY p.product_id HAVING count(*)>1 LIMIT 1").fetchone()[0])
requests=[];errors=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True)
    for width in [320,390,1440]:
        requests.clear()
        page=browser.new_page(viewport={'width':width,'height':850})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append(r.url))
        page.goto('http://127.0.0.1:8004/',wait_until='domcontentloaded')
        assert page.locator('#message').is_visible()
        assert page.locator('#map').count()==0
        assert not any('/api/map/clusters' in url or '/api/sessions/' in url and '/map-offers' in url for url in requests)
        page.locator('#ai-mode').uncheck()
        page.locator('#message').fill(p['persian_title'])
        page.locator('#send').click()
        card=page.locator('[data-product-id="'+p['product_id']+'"]')
        card.wait_for(timeout=30000)
        card.get_by_role('button',name='افزودن به سبد').click()
        page.wait_for_timeout(700)
        print('basket-debug',page.locator('#status').inner_text().encode('unicode_escape'),page.get_by_role('button',name='بررسی سبد').count())
        page.get_by_role('button',name='بررسی سبد').last.click()
        page.get_by_role('button',name='بررسی روی نقشه').last.click()
        assert page.url.endswith('/map')
        page.wait_for_function('document.getElementById("map-status").textContent.includes("پیشنهاد")',timeout=30000)
        assert page.locator('.leaflet-interactive').count()>0
        page.locator('.chat-link').click()
        assert page.locator('#message').is_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.close()
    browser.close()
assert not errors,errors
print('PASS chat-first initial load, product search, basket, on-demand relevant map, return: 320/390/1440')
