"""Persistent multi-product planning with source offer evidence."""
from datetime import datetime, timezone
from itertools import permutations
from pydantic import BaseModel, Field
from backend import catalog as c
from scripts.search_catalog import distance_km

class BasketItem(BaseModel):
    product_id:str
    quantity:int=Field(default=1,ge=1,le=100)
    offer_id:str|None=None

class Basket(BaseModel):
    items:list[BasketItem]=Field(default_factory=list,max_length=12)
    total_budget:int|None=Field(default=None,gt=0)

def freshness(raw):
    if not raw:return {'status':'unknown','age_days':None}
    try:
        dt=datetime.fromisoformat(str(raw).replace('Z','+00:00'))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        age=(datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).days
        return {'status':'stale' if age>=30 else 'recent','age_days':max(0,age)}
    except (ValueError,TypeError,OverflowError):return {'status':'unknown','age_days':None}

def details(basket:Basket):
    items=[];known_total=0;complete=True
    for item in basket.items:
        product=c.record('products','product_id',item.product_id)
        options=c.offers(item.product_id)
        offer=next((o for o in options if o['offer_id']==item.offer_id),None) if item.offer_id else None
        if item.offer_id and offer is None:raise ValueError('Offer does not belong to product')
        if offer is None:complete=False
        if offer and offer['price_toman'] is not None:known_total+=offer['price_toman']*item.quantity
        else:complete=False
        items.append({'product':product,'quantity':item.quantity,'offer':offer,'alternatives':len(options),'freshness':freshness(offer.get('last_price_changed_at')) if offer else None})
    return {'items':items,'estimated_total_toman':known_total if complete else None,'complete':complete,'budget_ok':None if not complete or basket.total_budget is None else known_total<=basket.total_budget}

def optimize(basket:Basket,lat=None,lon=None):
    if not basket.items:return {'plans':[],'unresolved':[]}
    choices=[];unresolved=[]
    for item in basket.items:
        options=[o for o in c.offers(item.product_id) if o['price_toman'] is not None and o['price_toman']>0]
        if item.offer_id:options=[o for o in options if o['offer_id']==item.offer_id]
        if not options:unresolved.append(item.product_id)
        choices.append(options[:15])
    if unresolved:return {'plans':[],'unresolved':unresolved}
    # Bounded beam search. Keep a cheap diverse frontier by store set and cost.
    states=[([],0,frozenset())]
    for item,options in zip(basket.items,choices):
        next_states={}
        for selected,cost,stores in states:
            for o in options:
                new_cost=cost+o['price_toman']*item.quantity
                if basket.total_budget and new_cost>basket.total_budget:continue
                key=stores|{o['shop_id']}
                candidate=(selected+[o],new_cost,key)
                prior=next_states.get(key)
                if prior is None or new_cost<prior[1]:next_states[key]=candidate
        states=sorted(next_states.values(),key=lambda x:(len(x[2]),x[1]))[:300]
    if not states:return {'plans':[],'unresolved':[],'reason':'No basket satisfies the total budget'}
    picks={}
    picks['fewest_stops']=min(states,key=lambda x:(len(x[2]),x[1]))
    picks['cheapest']=min(states,key=lambda x:(x[1],len(x[2])))
    picks['balanced']=min(states,key=lambda x:x[1]+len(x[2])*max(100000,round(x[1]*.03)))
    plans=[]
    for name,(offers,cost,stores) in picks.items():
        grouped={}
        for item,o in zip(basket.items,offers):grouped.setdefault(o['shop_id'],[]).append({'product_id':item.product_id,'offer_id':o['offer_id'],'quantity':item.quantity,'recorded_unit_price':o['price_toman'],'freshness':freshness(o.get('last_price_changed_at'))})
        stops=[{'shop':c.record('shops','shop_id',sid),'items':entries} for sid,entries in grouped.items()]
        distance=None
        if lat is not None and lon is not None and all(s['shop'].get('lat') is not None and s['shop'].get('lon') is not None for s in stops):
            def route_length(seq):
                total=0;point=(lat,lon)
                for stop in seq:
                    target=(float(stop['shop']['lat']),float(stop['shop']['lon']))
                    total+=distance_km(*point,*target);point=target
                return total
            if len(stops)<=7:stops=min(permutations(stops),key=route_length)
            else:
                ordered=[];remaining=stops[:];point=(lat,lon)
                while remaining:
                    stop=min(remaining,key=lambda s:distance_km(*point,float(s['shop']['lat']),float(s['shop']['lon'])))
                    remaining.remove(stop);ordered.append(stop);point=(float(stop['shop']['lat']),float(stop['shop']['lon']))
                stops=ordered
            distance=route_length(stops)
        plans.append({'type':name,'recorded_total_toman':cost,'stop_count':len(stops),'stops':list(stops),'straight_line_km':distance,'distance_kind':'straight_line_approximation' if distance is not None else 'unknown','reserved':False})
    return {'plans':plans,'unresolved':[]}
