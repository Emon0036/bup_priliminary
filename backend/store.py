"""Request-safe demo store. Production persistence is provided by SQLAlchemy scripts/models."""
from .simulation.engine import make_citizens, apply_month, metrics
from .ai.csp import allocate_jobs
class DemoStore:
    def __init__(self): self.reset()
    def reset(self): self.run={"id":1,"name":"Synthetic demo baseline","seed":42,"current_month":0,"status":"ACTIVE"}; self.citizens=make_citizens(); self.events=[]; self.history={0:[c.snapshot(0) for c in self.citizens]}; self.csp={"agents_considered":0,"agents_assigned":0,"agents_unassigned":0,"constraints_checked":0}
    def run_months(self, months):
        import random
        for _ in range(months):
            self.run["current_month"]+=1; m=self.run["current_month"]; apply_month(self.citizens,self.events,m,random.Random(self.run["seed"]+m)); unemployed=[{"id":c.id,"skill_level":c.skill_level} for c in self.citizens if c.employment_status=="UNEMPLOYED"]
            jobs=[{"id":1,"required_skill":"LOW","monthly_salary":22000,"capacity":15,"filled_positions":0,"active":True},{"id":2,"required_skill":"MEDIUM","monthly_salary":35000,"capacity":10,"filled_positions":0,"active":True},{"id":3,"required_skill":"HIGH","monthly_salary":60000,"capacity":5,"filled_positions":0,"active":True}]
            allocation=allocate_jobs(unemployed,jobs); self.csp=allocation["stats"]
            for c in self.citizens:
                if c.id in allocation["assignments"]: c.employment_status="EMPLOYED"; c.income=jobs[allocation["assignments"][c.id]-1]["monthly_salary"]; c.occupation="Reassigned Worker"
            self.history[m]=[c.snapshot(m) for c in self.citizens]
        return self.summary()
    def summary(self): return {"run":self.run,"metrics":metrics(self.citizens),"events":self.events,"csp_stats":self.csp}
STORE=DemoStore()
