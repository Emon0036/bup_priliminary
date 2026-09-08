from fastapi import FastAPI, HTTPException, Query
from backend.config import APP_VERSION
from backend.database import engine
from backend.ai.astar import astar
from backend.ai.risk_model import METRICS
from backend.schemas import SimulationRequest, EventRequest, PathRequest
from backend.store import STORE

app=FastAPI(title="EcoSim AI API",version=APP_VERSION)
@app.get("/api/health")
def health(): return {"status":"ok","database":"connected" if engine else "not_configured","app_version":APP_VERSION}
@app.get("/api/dashboard")
def dashboard(): return STORE.summary()
@app.get("/api/simulation/current")
def current(): return STORE.summary()
@app.post("/api/simulation/create")
def create(): STORE.reset(); return STORE.summary()
@app.post("/api/simulation/run")
def run(request:SimulationRequest):
    if request.simulation_run_id != STORE.run["id"]: raise HTTPException(404,"Simulation run not found")
    return STORE.run_months(request.months)
@app.post("/api/events")
def add_event(event:EventRequest):
    item={"id":len(STORE.events)+1,**event.model_dump(),"start_month":STORE.run["current_month"]+1,"description":event.event_type.replace("_"," ").title()}; STORE.events.append(item); return item
@app.get("/api/events")
def events(): return STORE.events
@app.get("/api/agents")
def agents(page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),search:str="",occupation:str="",skill:str="",employment:str="",risk:str=""):
    items=STORE.citizens
    def match(c): return (not search or search.lower() in c.name.lower() or search.lower() in c.code.lower()) and (not occupation or c.occupation==occupation) and (not skill or c.skill_level==skill) and (not employment or c.employment_status==employment) and (not risk or ("AT_RISK" if c.risk>=.5 else "STABLE")==risk)
    rows=[c.snapshot(STORE.run["current_month"]) for c in items if match(c)]; start=(page-1)*limit; return {"items":rows[start:start+limit],"total":len(rows),"page":page,"limit":limit}
@app.get("/api/agents/{agent_id}")
def agent(agent_id:int):
    found=next((c for c in STORE.citizens if c.id==agent_id),None)
    if not found: raise HTTPException(404,"Agent not found")
    return {"profile":found.snapshot(STORE.run["current_month"]),"history":[STORE.history[m][agent_id-1] for m in sorted(STORE.history)],"latest_state":found.snapshot(STORE.run["current_month"])}
@app.post("/api/pathfinding")
def pathfinding(request:PathRequest):
    grid=[[0]*30 for _ in range(30)]
    for y in range(5,25): grid[y][15]=1
    grid[15][15]=0
    return astar(grid,request.start,request.goal)
@app.get("/api/analytics")
def analytics():
    rows=[]
    for month,states in STORE.history.items():
        total=len(states); rows.append({"month":month,"average_savings":round(sum(s["savings"] for s in states)/total,2),"at_risk_percentage":round(100*sum(s["risk"]>=.5 for s in states)/total,1),"employment_rate":round(100*sum(s["employment_status"]=="EMPLOYED" for s in states)/total,1),"average_expense":round(sum(s["total_expense"] for s in states)/total,2)})
    return {"series":rows}
@app.get("/api/model/metrics")
def model_metrics(): return METRICS
