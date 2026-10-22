import json
from pydantic import Field
from backend import catalog as c
from backend.agent.query import Strict, CatalogQuery, query, FIELDS

class Empty(Strict): pass
class Search(Strict):
    query: str = Field(default='',max_length=300)
class Identity(Strict):
    id: str = Field(min_length=1,max_length=100)
class Compare(Strict):
    ids: list[str] = Field(min_length=2,max_length=4)
class PreferenceUpdate(Strict):
    budget: int | None = Field(default=None,gt=0,le=2**63-1)
    category: str | None = None
    lat: float | None = Field(default=None,ge=-90,le=90)
    lon: float | None = Field(default=None,ge=-180,le=180)
    radius: float | None = Field(default=None,gt=0,le=1000)

REGISTRY={
 'get_catalog_schema':(Empty,'Discover approved analytical fields and relationships.'),
 'get_data_coverage':(Empty,'Inspect dataset limitations and counts.'),
 'get_available_categories':(Search,'Find actual categories by part of their Persian name.'),
 'search_products':(Search,'Search all categories using stored hard budget/category constraints.'),
 'get_product_details':(Identity,'Retrieve a real product by ID.'),
 'compare_products':(Compare,'Retrieve actual specifications for two to four products.'),
 'get_product_offers':(Identity,'Find sellers for product ID with stored budget and geographic constraints.'),
 'get_store_details':(Identity,'Retrieve recorded store information; not live opening status.'),
 'compare_stores':(Compare,'Retrieve recorded details for two to four stores.'),
 'get_shopping_session':(Empty,'Read preferences and workflow state.'),
 'update_shopping_preferences':(PreferenceUpdate,'Update only explicitly user-requested constraints; omitted fields stay unchanged.'),
 'get_confirmation_status':(Empty,'Get current simulated response and same-product alternative sellers.'),
 'create_shopping_plan':(Empty,'Read shopping plan after the user selects and requests confirmation.'),
 'find_alternative_offers':(Identity,'Find other offers for a product; exclude selected offer and preserve constraints.'),
 'query_catalog':(CatalogQuery,'Read-only bounded analytical query; never use it to bypass shopping constraints.')}

def schemas():
    return [{'type':'function','name':name,'description':desc,'parameters':model.model_json_schema(),'strict':False} for name,(model,desc) in REGISTRY.items()]

def execute(name,arguments,sid):
    from backend import app as a
    if name not in REGISTRY: raise ValueError('UNKNOWN_TOOL')
    m=REGISTRY[name][0].model_validate(arguments)
    s=a.session(sid); p=s['preferences']
    if name=='get_catalog_schema': return {'entities':{k:list(v) for k,v in FIELDS.items()},'relations':['offers.product_id -> products','offers.shop_id -> shops'],'currency':'toman'}
    if name=='get_data_coverage': return {'counts':a.health(),'limitations':['Historical prices; unknown inventory','Fictional phones; simulated confirmations','No exceptional closure or live opening verification','Missing payment options mean unknown']}
    if name=='get_available_categories':
        return [r for r in a.categories() if m.query in r['name']][:50]
    if name=='search_products': return c.search(m.query,p.get('category'),p.get('budget'),limit=12)
    if name=='get_product_details': return a.product(m.id)
    if name=='get_store_details': return a.shop(m.id)
    if name=='compare_products': return a.compare(m.ids)
    if name=='compare_stores': return [a.shop(i) for i in m.ids]
    if name=='get_shopping_session': return {k:v for k,v in s.items() if k!='history'}
    if name=='update_shopping_preferences':
        changes=m.model_dump(exclude_unset=True)
        # Null is not a license to silently clear hard constraints.
        if any(v is None for v in changes.values()): raise ValueError('Use the manual form to clear constraints')
        merged=a.Preferences.model_validate({**p,**changes}).model_dump()
        s.update(preferences=merged,state='PRODUCTS_READY',offer_id=None)
        s.pop('confirmation_id',None);a.save(sid,s)
        return merged
    if name in ('get_product_offers','find_alternative_offers'):
        return c.offers(m.id,exclude=s.get('offer_id') if name=='find_alternative_offers' else None,**{k:p[k] for k in ('budget','lat','lon','radius')})[:30]
    if name in ('get_confirmation_status','create_shopping_plan'): return a.plan(sid)
    if name=='query_catalog': return query(m)
