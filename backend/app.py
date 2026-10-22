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
from pydantic import BaseModel, Field, model_validator
from backend import catalog as c

@asynccontextmanager
async def lifespan(app):
    c.initialize()
    yield

app = FastAPI(title='Torob shopping assistant', lifespan=lifespan)

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
    @model_validator(mode='after')
    def coordinates(self):
        if (self.lat is None)!=(self.lon is None): raise ValueError('Supply both coordinates')
        return self

class Selection(BaseModel):
    offer_id: str

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
    expected=os.getenv('SELLER_TOKEN','')
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
    s={'preferences':p.model_dump(),'state':'PRODUCTS_READY','offer_id':None}
    save(sid,s)
    return {'id':sid,**s,'products':c.search(p.query,p.category,p.budget),'message':'نتایج بر اساس اطلاعات ثبت‌شده؛ موجودی و قیمت فعلی نیاز به تأیید دارد.'}

@app.get('/api/sessions/{sid}')
def get_session(sid:str): return session(sid)

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
        s['state']='ALTERNATIVE_REQUIRED' if response.inventory=='unavailable' or response.visit=='not_possible' else 'CONFIRMATION_RECEIVED'
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

app.mount('/',StaticFiles(directory='frontend',html=True),name='frontend')
