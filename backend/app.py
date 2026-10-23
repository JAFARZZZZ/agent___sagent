"""Shopping API; seller responses are explicitly simulated."""
import json
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from backend import catalog as c
from backend import map_service
from backend import shopping

@asynccontextmanager
async def lifespan(app):
    c.initialize()
    import threading
    def warm():  # pre-compute popular map/search queries so the first user does not wait
        from backend import api_v2
        for q in ('گوشی موبایل', 'هدفون بی سیم', 'ساعت هوشمند', 'کفش اسپرت', 'لپ تاپ', 'دوربین مداربسته', 'تلویزیون', 'جاروبرقی'):
            try: api_v2.map_listings(q=q, category=None, budget=None, installment=False, open_now=False, include_accessories=False, lat=None, lon=None, products=120)
            except Exception: pass
    threading.Thread(target=warm, daemon=True).start()
    yield

app = FastAPI(title='Torob shopping assistant', lifespan=lifespan)
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=2048)

@app.exception_handler(KeyError)
async def missing(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=404,content={'detail':'Record not found'})

class Preferences(BaseModel):
    query: str = Field(default='',max_length=300)
    category: str | None = None
    budget: int | None = Field(default=None,gt=0,le=2**63-1)
    lat: float | None = Field(default=None,ge=-90,le=90)
    lon: float | None = Field(default=None,ge=-180,le=180)
    radius: float = Field(default=10,gt=0,le=1000)
    installment: bool = False
    open_now: bool = False
    area: str | None = Field(default=None,max_length=100)
    @model_validator(mode='after')
    def coordinates(self):
        if (self.lat is None)!=(self.lon is None): raise ValueError('Supply both coordinates')
        return self

class Selection(BaseModel):
    offer_id: str

class ProductSelection(BaseModel):
    product_id:str

class Response(BaseModel):
    inventory: Literal['available','unavailable','unknown'] = 'unknown'
    price: int | None = Field(default=None,gt=0,le=2**63-1)
    visit: Literal['possible','not_possible','unknown'] = 'unknown'
    notes: str = Field(default='',max_length=1000)

def session(sid):
    with c.connect() as db:
        row=db.execute('SELECT payload FROM sessions WHERE id=?',(sid,)).fetchone()
        if not row: raise KeyError(sid)
        return json.loads(row[0])

def save(sid,s):
    with c.connect() as db: db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?)',(sid,json.dumps(s)))

def admin(token):
    expected=os.getenv('SELLER_DEMO_SECRET') or os.getenv('SELLER_TOKEN','')
    if not expected or not secrets.compare_digest(token or '',expected): raise HTTPException(403,'Seller access denied')

@app.get('/api/health')
def health():
    with c.connect() as db: return {t:db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('products','shops','offers','product_search')}

@app.get('/api/categories')
def categories():
    with c.connect() as db:
        return [dict(r) for r in db.execute("SELECT category_id, json_extract(payload,'$.category_name') name,count(*) count FROM products GROUP BY category_id ORDER BY count DESC")]

@app.get('/api/products')
def products(query: str=Query('',max_length=300),category: str|None=None,budget:int|None=Query(None,gt=0,le=2**63-1),page:int=Query(0,ge=0)):
    return c.search(query,category,budget,page)

@app.get('/api/products/{pid}')
def product(pid:str): return c.record('products','product_id',pid)

@app.get('/api/shops/{sid}')
def shop(sid:str): return c.record('shops','shop_id',sid)

@app.post('/api/compare')
def compare(ids:list[str]):
    if not 2<=len(ids)<=4: raise HTTPException(422,'Select two to four products')
    return [product(pid) for pid in ids]

@app.post('/api/sessions')
def create(p:Preferences):
    sid=uuid.uuid4().hex
    s={'preferences':p.model_dump(),'state':'PRODUCTS_READY','offer_id':None,'basket':{'items':[],'total_budget':None}}
    save(sid,s)
    return {'id':sid,**s,'products':c.search(p.query,p.category,p.budget),'message':'نتایج بر اساس اطلاعات ثبت‌شده؛ موجودی و قیمت فعلی نیاز به تأیید دارد.'}

@app.get('/api/sessions/{sid}')
def get_session(sid:str): return session(sid)

@app.post('/api/sessions/{sid}/selection')
def select_product(sid:str,selection:ProductSelection):
    c.record('products','product_id',selection.product_id)
    s=session(sid);s['selected_product_id']=selection.product_id;s['offer_id']=None;save(sid,s)
    return {'product_id':selection.product_id}

@app.put('/api/sessions/{sid}/basket')
def put_basket(sid:str,basket:shopping.Basket):
    result=shopping.details(basket)
    s=session(sid);s['basket']=basket.model_dump();save(sid,s)
    return result

@app.get('/api/sessions/{sid}/basket')
def get_basket(sid:str):
    s=session(sid);return shopping.details(shopping.Basket.model_validate(s.get('basket',{})))

@app.post('/api/sessions/{sid}/basket/optimize')
def optimize_basket(sid:str):
    s=session(sid);p=s['preferences']
    result=shopping.optimize(shopping.Basket.model_validate(s.get('basket',{})),p.get('lat'),p.get('lon'))
    s['basket_plan']=result;save(sid,s);return result

@app.get('/api/sessions/{sid}/map-offers')
def relevant_map_offers(sid:str):
    s=session(sid);basket=shopping.Basket.model_validate(s.get('basket',{}));ids={x.product_id for x in basket.items}
    if not ids and s.get('selected_product_id'):ids={s['selected_product_id']}
    if not ids:return {'offers':[],'shop_count':0}
    p=s['preferences'];offers=[]
    for pid in ids:offers.extend(c.offers(pid,budget=p.get('budget'),lat=p.get('lat'),lon=p.get('lon'),radius=p.get('radius',10)))
    return {'offers':offers[:300],'total_offers':len(offers),'shop_count':len({o['shop_id'] for o in offers}),'truncated':len(offers)>300}

@app.put('/api/sessions/{sid}/preferences')
def update_preferences(sid:str,p:Preferences):
    s=session(sid)
    s.update(preferences=p.model_dump(),offer_id=None,state='PRODUCTS_READY')
    s.pop('confirmation_id',None)
    save(sid,s)
    return s

@app.get('/api/map-config')
def map_config():
    return {'tile_url':os.getenv('MAP_TILE_URL','https://tile.openstreetmap.org/{z}/{x}/{y}.png'),'attribution':os.getenv('MAP_ATTRIBUTION','© OpenStreetMap contributors')}

class Viewport(BaseModel):
    west:float=Field(ge=-180,le=180)
    east:float=Field(ge=-180,le=180)
    south:float=Field(ge=-90,le=90)
    north:float=Field(ge=-90,le=90)
    category:str|None=None
    keyword:str|None=Field(default=None,max_length=100)
    budget:int|None=Field(default=None,gt=0)
    installment:bool=False
    @model_validator(mode='after')
    def ordered(self):
        if self.west>=self.east or self.south>=self.north:raise ValueError('Invalid viewport')
        return self

@app.get('/api/map/clusters')
def map_clusters(v:Viewport=Query(),zoom:int=Query(10,ge=1,le=18)):
    return map_service.clusters(**v.model_dump(),zoom=zoom)

@app.get('/api/map/stores')
def map_stores(v:Viewport=Query(),limit:int=Query(100,ge=1,le=200),offset:int=Query(0,ge=0)):
    return map_service.stores(**v.model_dump(),limit=limit,offset=offset)

@app.get('/api/stores/{shop_id}/offers')
def mapped_shop_offers(shop_id:str,category:str|None=None,keyword:str|None=Query(None,max_length=100),budget:int|None=Query(None,gt=0),installment:bool=False,limit:int=Query(24,ge=1,le=100),offset:int=Query(0,ge=0)):
    return map_service.shop_offers(shop_id,category,keyword,budget,installment,limit,offset)

@app.get('/api/offers/{offer_id}')
def mapped_offer(offer_id:str):
    offer=c.record('offers','offer_id',offer_id)
    return {'offer':offer,'product':product(offer['product_id']),'shop':shop(offer['shop_id']),'price_freshness':shopping.freshness(offer.get('last_price_changed_at'))}

class PriceUpdateRequest(BaseModel):
    session_id:str

@app.post('/api/offers/{offer_id}/price-update-request')
def price_update_request(offer_id:str,body:PriceUpdateRequest):
    offer=c.record('offers','offer_id',offer_id)
    freshness=shopping.freshness(offer.get('last_price_changed_at'))
    if freshness['status']!='stale':raise HTTPException(422,'Recorded price is not proven stale')
    result=confirm(body.session_id,Selection(offer_id=offer_id))
    s=session(body.session_id);s['price_update_request']={'request_id':result['id'],'offer_id':offer_id,'shop_id':offer['shop_id'],'old_price_toman':offer['price_toman'],'requested_at':time.time(),'status':'PENDING'};save(body.session_id,s)
    return {**result,'status':'PENDING','old_price_toman':offer['price_toman'],'shop_id':offer['shop_id'],'simulated':True}

@app.get('/api/sessions/{sid}/offers/{pid}')
def find_offers(sid:str,pid:str):
    p=session(sid)['preferences']
    return c.offers(pid,**{k:p[k] for k in ('budget','lat','lon','radius')})

@app.post('/api/sessions/{sid}/confirmations')
def confirm(sid:str,selection:Selection):
    s=session(sid); offer=c.record('offers','offer_id',selection.offer_id)
    valid=find_offers(sid,offer['product_id'])
    if selection.offer_id not in {o['offer_id'] for o in valid}: raise HTTPException(422,'Offer violates session constraints')
    rid=uuid.uuid4().hex
    with c.connect() as db: db.execute('INSERT INTO confirmations VALUES (?,?,?,?,NULL)',(rid,sid,selection.offer_id,time.time()))
    s.update(offer_id=selection.offer_id,confirmation_id=rid,state='CONFIRMATION_PENDING'); save(sid,s)
    return {'id':rid,'simulated':True}

@app.get('/api/seller/requests')
def requests(x_seller_token:str|None=Header(None)):
    admin(x_seller_token)
    with c.connect() as db: return [dict(r) for r in db.execute('SELECT * FROM confirmations ORDER BY created DESC LIMIT 100')]

@app.post('/api/seller/requests/{rid}')
def respond(rid:str,response:Response,x_seller_token:str|None=Header(None)):
    admin(x_seller_token)
    with c.connect() as db:
        r=db.execute('SELECT * FROM confirmations WHERE id=?',(rid,)).fetchone()
        if not r: raise KeyError(rid)
        value={**response.model_dump(),'simulated':True,'responded_at':time.time()}
        db.execute('UPDATE confirmations SET response=? WHERE id=?',(json.dumps(value),rid))
    s=session(r['session_id'])
    if s.get('confirmation_id')==rid:
        over_budget=response.price is not None and s['preferences'].get('budget') is not None and response.price>s['preferences']['budget']
        s['state']='ALTERNATIVE_REQUIRED' if response.inventory=='unavailable' or response.visit=='not_possible' or over_budget else 'CONFIRMATION_RECEIVED'
        save(r['session_id'],s)
    return value

@app.get('/api/sessions/{sid}/plan')
def plan(sid:str):
    s=session(sid)
    if not s.get('offer_id'): raise HTTPException(409,'Select an offer first')
    o=c.record('offers','offer_id',s['offer_id'])
    with c.connect() as db: r=db.execute('SELECT * FROM confirmations WHERE id=?',(s['confirmation_id'],)).fetchone()
    response=json.loads(r['response']) if r['response'] else None
    expired=bool(response and time.time()-response['responded_at']>3600)
    p=s['preferences']
    return {'product':product(o['product_id']),'offer':o,'shop':shop(o['shop_id']),
        'response':response,'expired':expired,'inventory_status':'unknown' if expired or not response else response['inventory'],
        'simulated':True,'reserved':False,'alternatives':c.offers(o['product_id'],exclude=o['offer_id'],**{k:p[k] for k in ('budget','lat','lon','radius')})}

from backend.agent.orchestrator import ChatRequest, ChatResponse, run

@app.post('/api/sessions/{sid}/chat',response_model=ChatResponse)
def chat(sid:str,request:ChatRequest):
    return run(sid,request.message)

@app.get('/chat')
def chat_page():
    from fastapi.responses import RedirectResponse
    return RedirectResponse('/')

@app.get('/map')
def map_page():
    from fastapi.responses import RedirectResponse
    return RedirectResponse('/')

from backend.api_v2 import router as v2_router
app.include_router(v2_router)

app.mount('/',StaticFiles(directory='frontend',html=True),name='frontend')
