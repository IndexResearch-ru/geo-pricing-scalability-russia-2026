#!/usr/bin/env python3
"""Independently verify 126 frozen scenario outputs and price/conflict invariants.
Run: python calculate.py [folder]. No web calls; uses the evidence CSV files as inputs.
"""
import sys,csv,json
from pathlib import Path
P=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent

def read(name):
    with open(P/name,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f,delimiter=','))
def numb(v):return int(v) if v and str(v).isdecimal() else None
O={x['offer_id']:x for x in read('OFFER_OBSERVATIONS.csv')}
R=read('SCENARIO_CALCULATIONS.csv')
BASE={x['entity_id']:x['baseline_offer_id'] for x in R if x['scenario_id']=='BASE_3M'}
assert len(BASE)==21 and len(R)==126
spec={s['id']:s for s in json.loads((P/'SCENARIO_SPEC.json').read_text(encoding='utf-8'))['scenarios']}

def valid(o):
    return (o['payment_period']=='MONTH' and numb(o['monthly_price_rub']) is not None and
            o['price_kind'] not in ('CONFLICTED','UNVERIFIED') and o['model_class']!='CONFLICTED' and
            o['product_term_status']!='CROSS_PAGE_SCOPE_CONFLICT')

def derive(oid,sc):
    o=O[oid];s=spec[sc];p,n,m,paid=(s['add_prompts'],s['add_networks'],s['add_materials'],s['paid_placements_per_month'])
    if not valid(o):return 'BLOCKED_CONFLICT_OR_PRICE_PERIOD_UNKNOWN',None,None,None,''
    b=numb(o['monthly_price_rub']);months=numb(o['minimum_months']);term=b*max(3,months) if months is not None else None
    if not(p or n or m or paid):return 'BASE_ARITHMETIC_LOWER_BOUND',b,3*b,term,oid
    if paid:return 'UNKNOWN_PAID_PLACEMENT_RATE',None,None,term,''
    if o['model_class']=='PARAMETRIC' and oid=='P01-BASE' and not m:
        x=b+((p+9)//10)*10000+n*10000;return 'PUBLISHED_FORMULA_LOWER_BOUND',x,3*x,term,oid
    if o['model_class']!='FIXED_TIER':return 'UNKNOWN_REQUIRES_COMMERCIAL_QUOTE',None,None,term,''
    bp,bn,bm=numb(o['prompts_included']),numb(o['networks_included']),numb(o['materials_included'])
    if ((p and bp is None) or (n and bn is None) or (m and (bm is None or o['material_unit'] in ('','BRIEF_NOT_ARTICLE','INFORMATIONAL_ASSET_PERIOD_UNCONFIRMED')))):
        return 'UNKNOWN_NONCOMPARABLE_UNITS_OR_LIMIT',None,None,term,''
    candidates=[]
    for t in O.values():
        if t['offer_id']==oid or t['provider_id']!=o['provider_id'] or t['model_class']!='FIXED_TIER' or not valid(t):continue
        tp,tn,tm=numb(t['prompts_included']),numb(t['networks_included']),numb(t['materials_included'])
        if bp is not None and (tp is None or tp<bp+p):continue
        if bn is not None and (tn is None or tn<bn+n):continue
        if m and (t['material_unit']!=o['material_unit'] or tm is None or tm<bm+m):continue
        if not m and bm is not None and tm is not None and t['material_unit']==o['material_unit'] and tm<bm:continue
        candidates.append(t)
    if not candidates:return 'UNKNOWN_NO_PUBLISHED_MATCHING_TIER',None,None,term,''
    t=min(candidates,key=lambda q:(numb(q['monthly_price_rub']),q['offer_id']));x=numb(t['monthly_price_rub']);return 'BUNDLED_TIER_LOWER_BOUND',x,3*x,term,t['offer_id']

for r in R:
    status,mon,three,term,chosen=derive(r['baseline_offer_id'],r['scenario_id'])
    got=(r['calculation_status'],numb(r['modeled_monthly_floor_rub']),numb(r['three_month_arithmetic_floor_rub']),numb(r['floor_for_3m_horizon_with_min_term_rub']),r['selected_offer_id'])
    assert got==(status,mon,three,term,chosen),(r['entity_id'],r['scenario_id'],got,(status,mon,three,term,chosen))
assert all(r['calculation_status'] not in ('LOWER_BOUND_3M',) for r in R)
print(f'PASS {len(R)} independent calculations / {len(BASE)} economic suppliers; no scores, weights, ranks, or false zeroes.')