"""Actual Chrome checks against a running server; no mock API responses."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
from backend import catalog as c

with c.connect() as db:
    row=db.execute('SELECT p.product_id,p.payload,count(*) n FROM products p JOIN offers o USING(product_id) GROUP BY p.product_id ORDER BY n DESC LIMIT 1').fetchone()
    product=json.loads(row['payload']);expected=row['n']
out=Path('outputs/evaluation/browser');out.mkdir(parents=True,exist_ok=True)
errors=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True)
    for width in (1280,390):
        page=browser.new_page(viewport={'width':width,'height':900})
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto('http://127.0.0.1:8001')
        page.locator('#query').fill(product['persian_title'])
        page.locator('#search button').click()
        button=page.locator('[data-offers="'+product['product_id']+'"]')
        button.wait_for(timeout=30000)
        button.click()
        page.locator('[data-confirm]').first.wait_for(timeout=30000)
        assert page.locator('[data-confirm]').count()==expected
        assert page.locator('[data-offer-id]').count()==expected
        if width==1280:
            page.locator('[data-confirm]').first.click()
            page.wait_for_function("document.getElementById('status').textContent.includes('ذخیره شد')")
            sid=page.evaluate("localStorage.getItem('shopping_session')")
            seller=browser.new_page()
            seller.goto('http://127.0.0.1:8001/seller.html')
            seller.locator('#token').fill(os.getenv('SELLER_DEMO_SECRET') or os.getenv('SELLER_TOKEN',''))
            seller.locator('#load').click()
            form=seller.locator('#requests form').first
            form.wait_for()
            form.locator('[name=inventory]').select_option('unavailable')
            form.locator('button').click()
            seller.wait_for_function("document.getElementById('status').textContent.includes('ذخیره شد')")
            page.locator('#plan').click()
            page.wait_for_function("document.getElementById('details').textContent.includes('unavailable')")
            page.get_by_role('button',name='مشاهده فروشنده‌های جایگزین',exact=True).click()
            assert page.locator('[data-confirm]').count()==expected-1
            seller.close()
            with c.connect() as db:
                db.execute('DELETE FROM confirmations WHERE session_id=?',(sid,))
                db.execute('DELETE FROM sessions WHERE id=?',(sid,))
        page.screenshot(path=str(out/f'offers-{width}.png'))
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Horizontal overflow'
        page.close()
    browser.close()
assert not errors,errors
(out/'result.json').write_text(json.dumps({'status':'PASS','product_id':product['product_id'],'offers':expected,'widths':[1280,390],'console_errors':errors}),encoding='utf-8')
print('PASS: desktop/mobile actual search and all offer cards, no JS errors or horizontal overflow')
