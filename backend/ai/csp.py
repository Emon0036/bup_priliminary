"""Small bounded job-assignment CSP: MRV, capacity checking, backtracking."""
RANK={"LOW":0,"MEDIUM":1,"HIGH":2}
def allocate_jobs(agents, jobs, max_batch=30):
    candidates=list(agents)[:max_batch]; stats={"agents_considered":len(candidates),"agents_assigned":0,"agents_unassigned":0,"constraints_checked":0}; assigned={}; used={j["id"]:j.get("filled_positions",0) for j in jobs}
    def domain(agent):
        choices=[]
        for job in jobs:
            stats["constraints_checked"]+=1
            if job.get("active",True) and job["monthly_salary"]>0 and RANK[agent["skill_level"]]>=RANK[job["required_skill"]] and used[job["id"]] < job["capacity"]: choices.append(job)
        return choices
    def solve(remaining):
        if not remaining: return True
        options=[(domain(a),a) for a in remaining]; choices, agent=min(options,key=lambda x:len(x[0]))
        if not choices: return False
        rest=[a for a in remaining if a["id"] != agent["id"]]
        for job in choices:
            used[job["id"]]+=1; assigned[agent["id"]]=job["id"]
            if solve(rest): return True
            used[job["id"]]-=1; assigned.pop(agent["id"],None)
        return False
    # Incremental calls preserve feasible assignments without requiring everyone to be placeable.
    for agent in candidates:
        solve([agent])
    stats["agents_assigned"]=len(assigned); stats["agents_unassigned"]=len(candidates)-len(assigned)
    return {"assignments":assigned,"stats":stats}
