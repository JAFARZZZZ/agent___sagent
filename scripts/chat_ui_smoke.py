import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from backend import catalog as c

with c.connect() as db:
    row=db.execute('SELECT p.payload FROM products p JOIN offers o USING(product_id) GROUP BY p.product_id HAVING count(*)>3 LIMIT 1').fetchone()
    product=json.loads(row[0])
out=Path('outputs/evaluation/chat-ui');out.mkdir(parents=True,exist_ok=True)
errors=[];reports=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True)
    for width in (1280,390):
        page=browser.new_page(viewport={'width':width,'height':900})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8002',wait_until='domcontentloaded')
        page.locator('#message').wait_for()
        page.screenshot(path=str(out/f'welcome-{width}.png'))
        assert page.locator('textarea').count()==1
        page.locator('#ai-mode').uncheck()
        page.locator('#message').fill(product['persian_title'])
        page.locator('#send').click()
        card=page.locator('[data-product-id="'+product['product_id']+'"]')
        card.wait_for(timeout=30000)
        sid=page.evaluate('localStorage.getItem("shopping_session")')
        card.get_by_role('button',name='مشاهده پیشنهادها',exact=True).click()
        page.locator('[data-offer-id]').first.wait_for(timeout=30000)
        offers=page.locator('.offer-current [data-offer-id]').count()
        page.locator('#filters-open').click()
        page.locator('#budget').fill('1')
        page.get_by_role('button',name='اعمال فیلترها',exact=True).click()
        page.wait_for_function('!document.getElementById("filters").open')
        assert page.evaluate('localStorage.getItem("shopping_session")')==sid
        page.locator('#filters-open').click()
        page.locator('#reset').click()
        page.wait_for_function('!document.getElementById("filters").open')
        assert page.locator('.offer-current [data-offer-id]').count()==offers
        page.locator('.offer-current').get_by_role('button',name='مشاهده روی نقشه',exact=True).click()
        page.wait_for_timeout(1500)
        map_loaded=page.locator('.map').count()>0
        if map_loaded:
            assert int(page.locator('.map').get_attribute('data-marker-count'))>0
            page.locator('#filters-open').click()
            page.locator('#budget').fill('1')
            page.get_by_role('button',name='اعمال فیلترها',exact=True).click()
            page.wait_for_function('!document.getElementById("filters").open')
            assert page.locator('.offer-current [data-offer-id]').count()==0
            assert page.locator('.map').get_attribute('data-marker-count')=='0'
            page.locator('#filters-open').click()
            page.locator('#reset').click()
            page.wait_for_function('!document.getElementById("filters").open')
        page.screenshot(path=str(out/f'results-{width}.png'))
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        reports.append({'width':width,'offers':offers,'map_loaded':map_loaded,'single_composer':True,'same_session_filters':True})
        page.close()
    browser.close()
assert not errors,errors
(out/'report.json').write_text(json.dumps({'runs':reports,'errors':errors},indent=2),encoding='utf-8')
print(json.dumps(reports))
