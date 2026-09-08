"""A* on a four-direction grid using the Manhattan admissible heuristic."""
from heapq import heappop, heappush

def astar(grid: list[list[int]], start: tuple[int,int], goal: tuple[int,int]):
    if not grid or not grid[0]: return {"path": [], "cost": None, "explored": 0}
    height, width = len(grid), len(grid[0])
    def valid(p): return 0 <= p[0] < width and 0 <= p[1] < height and grid[p[1]][p[0]] == 0
    if not valid(start) or not valid(goal): return {"path": [], "cost": None, "explored": 0}
    if start == goal: return {"path": [list(start)], "cost": 0, "explored": 1}
    frontier=[(abs(start[0]-goal[0])+abs(start[1]-goal[1]),0,start)]; came={}; best={start:0}; explored=0
    while frontier:
        _, cost, node=heappop(frontier); explored += 1
        if node == goal:
            path=[node]
            while node in came: node=came[node]; path.append(node)
            path.reverse(); return {"path":[list(p) for p in path],"cost":cost,"explored":explored}
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nxt=(node[0]+dx,node[1]+dy); new=cost+1
            if valid(nxt) and new < best.get(nxt, float("inf")):
                best[nxt]=new; came[nxt]=node; heappush(frontier,(new+abs(nxt[0]-goal[0])+abs(nxt[1]-goal[1]),new,nxt))
    return {"path": [], "cost": None, "explored": explored}
