import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from backend import catalog as c

with c.connect() as db:
    p=json.loads(db.execute("SELECT payload FROM products WHERE json_array_length(json_extract(payload,'$.image_urls'))>0 LIMIT 1").fetchone()[0])
url=p['image_urls'][0]
out=Path('outputs/evaluation/rendering');out.mkdir(parents=True,exist_ok=True)
reports=[];errors=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True)
    for width in [320,360,375,390,430,768,1024,1440]:
        page=browser.new_page(viewport={'width':width,'height':900})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8002',wait_until='domcontentloaded')
        page.wait_for_function('typeof renderMarkdown === "function"')
        assert page.locator('#lat,#lon').count()==0
        md='**آزمایش نمایش**\n\n- مورد اول\n- مورد دوم\n\n| کالا | تصویر |\n|---|---|\n| '+p['persian_title']+' | ![کالا]('+url+') |\n\n[لینک بلند](https://example.org/'+('long'*100)+')\n<br>خط جدید\n<script>window.injected=true</script>\n[ناامن](javascript:alert(1))'
        page.evaluate('(text)=>message("assistant",text)',md)
        assert page.locator('.markdown strong').count()==1
        assert page.locator('.markdown table').count()==1
        assert page.locator('.markdown img').count()==1
        assert page.locator('.markdown script').count()==0
        assert page.locator('a[href^="javascript:"]').count()==0
        page.wait_for_timeout(1000)
        loaded=page.locator('.markdown img').evaluate_all('(imgs)=>imgs.some(i=>i.complete&&i.naturalWidth>0)')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        if width in (320,390,1440):page.screenshot(path=str(out/f'markdown-{width}.png'))
        reports.append({'width':width,'overflow':False,'real_image_loaded':loaded})
        page.close()
    context=browser.new_context(geolocation={'latitude':35.7,'longitude':51.4},permissions=['geolocation'])
    page=context.new_page();page.goto('http://127.0.0.1:8002')
    page.locator('#location-open').click()
    page.locator('.map-sheet').get_by_role('button',name='موقعیت من',exact=True).click()
    page.get_by_role('button',name='تأیید موقعیت انتخابی',exact=True).wait_for()
    page.get_by_role('button',name='تأیید موقعیت انتخابی',exact=True).click()
    page.wait_for_function('state.prefs.lat===35.7')
    page.locator('.map-sheet').get_by_role('button',name='انتخاب موقعیت',exact=True).click()
    page.locator('.map').click(position={'x':120,'y':120})
    assert page.locator('.location-pin').count()==1
    page.get_by_role('button',name='تأیید موقعیت انتخابی',exact=True).click()
    context.close();browser.close()
assert not errors,errors
(out/'report.json').write_text(json.dumps({'product_id':p['product_id'],'image_url':url,'viewports':reports,'geolocation_granted':True,'manual_selection':True,'errors':errors},indent=2),encoding='utf-8')
print(json.dumps(reports))
