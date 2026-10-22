"""Small read-only analytical DSL: identifiers are allowlisted, values bound."""
import sqlite3
import time
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend import catalog as c

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

FIELDS = {
 'products': {'product_id':'p.product_id','category_id':'p.category_id','title':"json_extract(p.payload,'$.persian_title')",'brand':"json_extract(p.payload,'$.brand_name')",'spec_count':'p.spec_count'},
 'shops': {'shop_id':'s.shop_id','lat':'s.lat','lon':'s.lon','name':"json_extract(s.payload,'$.name')",'has_declared_hours':'s.has_declared_hours'},
 'offers': {'offer_id':'o.offer_id','product_id':'o.product_id','shop_id':'o.shop_id','price_toman':'o.price_toman','category_id':'p.category_id','lat':'s.lat','lon':'s.lon','updated':"json_extract(o.payload,'$.last_price_changed_at')"}}
SOURCES={'products':'products p','shops':'shops s','offers':'offers o JOIN products p USING(product_id) JOIN shops s USING(shop_id)'}

class Filter(Strict):
    field: str
    op: Literal['eq','lt','lte','gt','gte','contains']
    value: str | int | float

class CatalogQuery(Strict):
    entity: Literal['products','shops','offers']
    select: list[str] = Field(default_factory=list,max_length=8)
    filters: list[Filter] = Field(default_factory=list,max_length=12)
    match: Literal['all','any'] = 'all'
    group_by: str | None = None
    aggregate: Literal['count','min','max','avg'] | None = None
    aggregate_field: str | None = None
    sort: str | None = None
    descending: bool = False
    limit: int = Field(default=20,ge=1,le=50)
    offset: int = Field(default=0,ge=0,le=10000)

def query(q:CatalogQuery):
    fields=FIELDS[q.entity]
    def field(name):
        if name not in fields: raise ValueError('UNKNOWN_FIELD')
        return fields[name]
    selected=q.select or list(fields)[:4]
    if q.aggregate:
        expression='count(*)' if q.aggregate=='count' else q.aggregate+'('+field(q.aggregate_field)+')'
        projection=(field(q.group_by)+' AS "'+q.group_by+'", ' if q.group_by else '')+expression+' AS value'
    else:
        if q.group_by: raise ValueError('Grouping requires aggregation')
        projection=', '.join(field(n)+' AS "'+n+'"' for n in selected)
    args=[]; clauses=[]
    for f in q.filters:
        column=field(f.field)
        op={'eq':'=','lt':'<','lte':'<=','gt':'>','gte':'>=','contains':'LIKE'}[f.op]
        clauses.append(column+' '+op+' ?');args.append('%'+str(f.value)+'%' if f.op=='contains' else f.value)
    sql='SELECT '+projection+' FROM '+SOURCES[q.entity]
    if clauses: sql+=' WHERE '+(' AND ' if q.match=='all' else ' OR ').join(clauses)
    if q.group_by: sql+=' GROUP BY '+field(q.group_by)
    if q.sort:
        order='value' if q.aggregate and q.sort=='value' else field(q.sort)
        sql+=' ORDER BY '+order+(' DESC' if q.descending else ' ASC')
    sql+=' LIMIT ? OFFSET ?';args.extend([q.limit,q.offset])
    with c.connect() as db:
        deadline=time.monotonic()+3
        db.execute('PRAGMA query_only=ON')
        db.set_progress_handler(lambda: int(time.monotonic()>deadline),10000)
        try: return {'results':[dict(r) for r in db.execute(sql,args)],'limit':q.limit,'offset':q.offset}
        except sqlite3.OperationalError: raise ValueError('QUERY_TIMEOUT_OR_INVALID_QUERY') from None
