from backend.ai.astar import astar
def test_shortest_path_and_start_goal():
    grid=[[0]*4 for _ in range(4)]; assert astar(grid,(0,0),(3,3))["cost"]==6; assert astar(grid,(1,1),(1,1))["cost"]==0
def test_blocked_and_unreachable():
    grid=[[0,1,0],[0,1,0],[0,1,0]]; assert astar(grid,(0,0),(2,0))["path"]==[]
