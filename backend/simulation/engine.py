"""Transparent, deterministic monthly household simulation."""
from dataclasses import dataclass, asdict
import random
from ..ai.risk_model import predict_risk

@dataclass
class Citizen:
    id:int; code:str; name:str; age:int; occupation:str; skill_level:str; employment_status:str; family_size:int; income:float; food:float; housing:float; transport:float; other:float; savings:float; debt:float; goal:str; x:int; y:int; risk:float=0; decision:str="NORMAL_SPENDING"
    def snapshot(self, month):
        expense=self.food+self.housing+self.transport+self.other
        return {**asdict(self),"month":month,"total_expense":round(expense,2),"risk_class":"AT_RISK" if self.risk>=.5 else "STABLE"}

OCCUPATIONS=[("Teacher","HIGH"),("Office Worker","MEDIUM"),("Shop Worker","LOW"),("Driver","LOW"),("Technician","MEDIUM"),("Garment Worker","LOW"),("Sales Worker","MEDIUM"),("Small Business Owner","HIGH"),("Freelancer","HIGH"),("Student","LOW"),("Unemployed","LOW")]
def make_citizens(count=500, seed=42):
    rng=random.Random(seed); result=[]
    for i in range(count):
        occupation,skill=rng.choice(OCCUPATIONS); employed=occupation not in ("Student","Unemployed") and rng.random()<.93
        income=0 if not employed else rng.randint(12000 if skill=="LOW" else 25000, 40000 if skill=="LOW" else 85000)
        family=rng.randint(1,6); food=round(max(1500, income*.18 if income else rng.randint(1800,4500))*family/2,2); housing=round(max(1500,income*.22) if income else rng.randint(1200,5000),2)
        result.append(Citizen(i+1,f"AG{i+1:04d}",f"Citizen {i+1:03d}",rng.randint(18,65),occupation if employed else "Unemployed",skill,"EMPLOYED" if employed else "UNEMPLOYED",family,income,food,housing,round(max(300,income*.06),2),round(max(400,income*.1),2),round(rng.uniform(0,90000),2),round(rng.uniform(0,40000),2),rng.choice(["Emergency savings","Reduce debt","Education fund","Asset purchase"]),rng.randint(1,28),rng.randint(1,28)))
    return result
def apply_month(citizens, events, month, rng):
    active=[e for e in events if e["start_month"]<=month<e["start_month"]+e["duration_months"]]
    food_factor=general_factor=salary_factor=1; tax=.05; shortage=0
    for e in active:
        p=e["magnitude"]/100
        if e["event_type"]=="FOOD_PRICE_SHOCK": food_factor+=p
        elif e["event_type"]=="GENERAL_INFLATION": general_factor+=p
        elif e["event_type"]=="TAX_CHANGE": tax+=p
        elif e["event_type"]=="SALARY_CHANGE": salary_factor+=p
        elif e["event_type"]=="JOB_SHORTAGE": shortage=max(shortage,p)
    for c in citizens:
        if c.employment_status=="EMPLOYED" and shortage and rng.random()<shortage*.08: c.employment_status="UNEMPLOYED"; c.occupation="Unemployed"; c.income=0
        gross=c.income*salary_factor if c.employment_status=="EMPLOYED" else 0; net=gross*max(0,1-tax)
        food=c.food*food_factor; housing=c.housing*general_factor; transport=c.transport*general_factor; other=c.other*general_factor; total=food+housing+transport+other; disposable=net-total
        if disposable>=0: c.savings+=disposable*.65; c.decision="INCREASE_SAVINGS" if disposable>net*.1 else "NORMAL_SPENDING"
        else:
            cut=min(other*.45,-disposable); other-=cut; disposable+=cut; c.decision="REDUCE_DISCRETIONARY"
            if disposable<0:
                withdrawal=min(c.savings,-disposable); c.savings-=withdrawal; disposable+=withdrawal; c.decision="USE_SAVINGS"
            if disposable<0: c.debt+=-disposable; c.decision="DEBT_STRESS"
        c.food,c.housing,c.transport,c.other=food,housing,transport,other
        c.risk=predict_risk(net,total,c.savings,c.debt,c.family_size,c.employment_status=="EMPLOYED",max(food_factor-1,general_factor-1))
    return active
def metrics(citizens):
    n=len(citizens); incomes=sorted(c.income for c in citizens); employed=sum(c.employment_status=="EMPLOYED" for c in citizens); expenses=[c.food+c.housing+c.transport+c.other for c in citizens]
    gini=(2*sum((i+1)*v for i,v in enumerate(incomes))/(n*sum(incomes))- (n+1)/n) if sum(incomes) else 0
    return {"population":n,"employment_rate":round(100*employed/n,1),"unemployment_rate":round(100*(n-employed)/n,1),"average_income":round(sum(incomes)/n,2),"average_total_expense":round(sum(expenses)/n,2),"average_savings":round(sum(c.savings for c in citizens)/n,2),"at_risk_percentage":round(100*sum(c.risk>=.5 for c in citizens)/n,1),"stable_percentage":round(100*sum(c.risk<.5 for c in citizens)/n,1),"average_disposable_income":round(sum(c.income-e for c,e in zip(citizens,expenses))/n,2),"gini_coefficient":round(gini,3)}
