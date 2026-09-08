import random
from backend.simulation.engine import make_citizens,apply_month
def test_food_shock_increases_food_and_is_deterministic():
    a=make_citizens(5,42); b=make_citizens(5,42); before=a[0].food; e=[{"event_type":"FOOD_PRICE_SHOCK","magnitude":30,"start_month":1,"duration_months":3}]; apply_month(a,e,1,random.Random(43)); apply_month(b,e,1,random.Random(43)); assert a[0].food>before and a[0].snapshot(1)==b[0].snapshot(1)
def test_tax_and_job_shortage_change_state():
    a=make_citizens(30,42); before=sum(x.income for x in a); apply_month(a,[{"event_type":"TAX_CHANGE","magnitude":10,"start_month":1,"duration_months":1},{"event_type":"JOB_SHORTAGE","magnitude":100,"start_month":1,"duration_months":1}],1,random.Random(43)); assert sum(x.income for x in a)<=before
