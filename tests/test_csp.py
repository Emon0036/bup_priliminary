from backend.ai.csp import allocate_jobs
def test_capacity_and_skill_constraints():
    agents=[{"id":1,"skill_level":"LOW"},{"id":2,"skill_level":"HIGH"}]; jobs=[{"id":1,"required_skill":"MEDIUM","monthly_salary":1,"capacity":1,"filled_positions":0,"active":True},{"id":2,"required_skill":"LOW","monthly_salary":1,"capacity":1,"filled_positions":0,"active":True}]
    result=allocate_jobs(agents,jobs); assert result["assignments"][1]==2; assert result["stats"]["agents_assigned"]==2
