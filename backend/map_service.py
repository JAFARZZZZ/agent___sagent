"""Viewport aggregation over all registered geolocated offers."""
import json
import math
from backend import catalog as c

def _filters(category,keyword,budget,installment):
    parts=[];args=[]
    if category:parts.append('p.category_id=?');args.append(category)
    if keyword:parts.append("json_extract(p.payload,'$.persian_title') LIKE ?");args.append('%'+keyword+'%')
    if budget is not None:parts.append('o.price_toman>0 AND o.price_toman<=?');args.append(budget)
    if installment:parts.append("(json_extract(s.payload,'$.payment_options') LIKE '%اقساط%' OR json_extract(s.payload,'$.payment_options') LIKE '%installment%')")
    return parts,args

def clusters(west,south,east,north,zoom,category=None,keyword=None,budget=None,installment=False):
    # Fixed world grid. Zoom changes cell size; no arbitrary data limit.
    size=max(.001, 360/(2**(min(zoom,18)+2)))
    base=['s.lat BETWEEN ? AND ?','s.lon BETWEEN ? AND ?','s.lat BETWEEN -90 AND 90','s.lon BETWEEN -180 AND 180']
    parts,args=_filters(category,keyword,budget,installment)
    base+=parts;params=[south,north,west,east]+args
    sql=f'''SELECT CAST(floor(s.lat/{size}) AS INTEGER) gy,CAST(floor(s.lon/{size}) AS INTEGER) gx,
      count(*) offers,count(DISTINCT s.shop_id) shops,avg(s.lat) lat,avg(s.lon) lon,
      min(o.price_toman) min_price
      FROM offers o JOIN shops s USING(shop_id) JOIN products p USING(product_id)
      WHERE {' AND '.join(base)} GROUP BY gy,gx'''
    with c.connect() as db:
        cells=[dict(r) for r in db.execute(sql,params)]
        total=db.execute('SELECT count(*) FROM offers').fetchone()[0]
        geolocated=db.execute('SELECT count(*) FROM offers o JOIN shops s USING(shop_id) WHERE s.lat IS NOT NULL AND s.lon IS NOT NULL').fetchone()[0]
    return {'cells':cells,'viewport_offers':sum(x['offers'] for x in cells),'viewport_shops_aggregated':sum(x['shops'] for x in cells),
            'all_offers':total,'geolocated_offers':geolocated,'non_geolocated_offers':total-geolocated,'cell_degrees':size}

def stores(west,south,east,north,category=None,keyword=None,budget=None,installment=False,limit=100,offset=0):
    parts,args=_filters(category,keyword,budget,installment)
    where=['s.lat BETWEEN ? AND ?','s.lon BETWEEN ? AND ?']+parts
    params=[south,north,west,east]+args
    sql=f'''FROM offers o JOIN shops s USING(shop_id) JOIN products p USING(product_id)
      WHERE {' AND '.join(where)}'''
    with c.connect() as db:
        total=db.execute('SELECT count(DISTINCT s.shop_id) '+sql,params).fetchone()[0]
        rows=db.execute('SELECT s.shop_id,s.lat,s.lon,s.payload,count(*) offer_count,min(o.price_toman) min_price '+sql+' GROUP BY s.shop_id ORDER BY s.shop_id LIMIT ? OFFSET ?',params+[limit,offset])
        result=[]
        for r in rows:
            shop=json.loads(r['payload']);result.append({'shop_id':r['shop_id'],'name':shop.get('name'),'address':shop.get('address'),'lat':r['lat'],'lon':r['lon'],'offer_count':r['offer_count'],'min_price':r['min_price'],'payment_options':shop.get('payment_options')})
    return {'total':total,'results':result,'next_offset':offset+len(result) if offset+len(result)<total else None}

def shop_offers(shop_id,category=None,keyword=None,budget=None,installment=False,limit=24,offset=0):
    parts,args=_filters(category,keyword,budget,installment)
    where=['o.shop_id=?']+parts;params=[shop_id]+args
    sql=f'''FROM offers o JOIN products p USING(product_id) JOIN shops s USING(shop_id) WHERE {' AND '.join(where)}'''
    with c.connect() as db:
        total=db.execute('SELECT count(*) '+sql,params).fetchone()[0]
        rows=db.execute('SELECT o.offer_id,o.product_id,o.shop_id,o.price_toman,o.payload offer,p.payload product,s.payload shop '+sql+' ORDER BY o.offer_id LIMIT ? OFFSET ?',params+[limit,offset])
        result=[]
        for r in rows:
            offer=json.loads(r['offer']);product=json.loads(r['product']);shop=json.loads(r['shop'])
            result.append({'offer_id':r['offer_id'],'product_id':r['product_id'],'shop_id':r['shop_id'],'price_toman':r['price_toman'],'seller_title':offer.get('seller_title'),'description':offer.get('description'),'warranty':offer.get('warranty'),'last_price_changed_at':offer.get('last_price_changed_at'),'product':product,'shop':shop})
    return {'total':total,'results':result,'next_offset':offset+len(result) if offset+len(result)<total else None}
