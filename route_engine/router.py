import heapq
import collections
from .utils import distance
from .validator import is_point_valid, allow_simulated_connection
from .data_loader import get_departure_points, get_arrival_points

def build_spatial_grid(points_db, grid_size_deg=2.0):
    grid = collections.defaultdict(list)
    for name, data in points_db.items():
        lat = data.get('lat', 0.0)
        lon = data.get('lon', 0.0)
        lat_idx = int(lat // grid_size_deg)
        lon_idx = int(lon // grid_size_deg)
        grid[(lat_idx, lon_idx)].append(name)
    return grid

def get_nearby_points(curr_name, points_db, grid, grid_size_deg=2.0):
    curr_data = points_db[curr_name]
    lat = curr_data.get('lat', 0.0)
    lon = curr_data.get('lon', 0.0)
    
    lat_idx = int(lat // grid_size_deg)
    lon_idx = int(lon // grid_size_deg)
    
    candidates = []
    # Check 3x3 grid cells
    for di in [-1, 0, 1]:
        for dj in [-1, 0, 1]:
            candidates.extend(grid[(lat_idx + di, lon_idx + dj)])
    return candidates

def heuristic(curr_name, end_set, points_db):
    p1 = points_db[curr_name]
    min_dist = float('inf')
    for e in end_set:
        d = distance(p1, points_db[e])
        if d < min_dist: min_dist = d
    return min_dist

def resolve_graph_node_options(identifier, points_db, is_start=True):
    """
    Resolves an identifier (Airport or Waypoint) to a list of FRA Graph Node Names.
    - If identifier is in points_db, it's a Waypoint -> [identifier]
    - If identifier is an Airport Code -> Lookup Annex -> [Option1, Option2...]
    """
    if identifier in points_db:
        return [identifier]
    
    # Assume Airport
    if is_start:
        return get_departure_points(identifier, points_db)
    else:
        return get_arrival_points(identifier)

def find_path_astar(start_nodes, end_nodes, edges, points_db):
    """
    Core A* Algorithm.
    start_nodes: list of valid FRA point names to start from.
    end_nodes: list of valid FRA point names to end at.
    """
    print("Building spatial index...")
    grid = build_spatial_grid(points_db)
    
    end_set = set([e for e in end_nodes if e in points_db])
    start_set = [s for s in start_nodes if s in points_db]
    
    if not start_set or not end_set:
        return None, None
        
    open_set = []
    
    # Init Open Set
    for s in start_set:
        # Check Node Validity
        if not is_point_valid(points_db[s]):
            continue
        h = heuristic(s, end_set, points_db)
        heapq.heappush(open_set, (h, s, [s], 0))
        
    g_scores = {s: 0 for s in start_set}
    aug_edges_used = collections.defaultdict(dict)
    closed_set = set()
    
    itr = 0
    max_iter = 50000
    
    while open_set:
        f, curr, path, g = heapq.heappop(open_set)
        
        if curr in end_set:
            return path, aug_edges_used
            
        if curr in closed_set: continue
        closed_set.add(curr)
        
        if itr > max_iter:
            print("Max iterations reached")
            break
        itr += 1
        
        neighbors = []
        
        # 1. Explicit Edges
        if curr in edges:
            for e in edges[curr]:
                neighbors.append((e['To'], "Explicit DCT"))
                
        # 2. Simulated Edges
        p1 = points_db[curr]
        candidates = get_nearby_points(curr, points_db, grid)
        
        for nxt in candidates:
            if nxt == curr: continue
            
            if not is_point_valid(points_db[nxt]): continue
            
            allowed, reason = allow_simulated_connection(p1, points_db[nxt])
            if not allowed: continue
            
            d = distance(p1, points_db[nxt])
            if d < 400.0: # Range limit
                neighbors.append((nxt, f"Simulated: {reason}"))
                
        # Process Neighbors
        for nxt, type_str in neighbors:
            if nxt not in points_db: continue
            
            if "Explicit" in type_str:
                if not is_point_valid(points_db[nxt]): continue
                
            step_dist = distance(points_db[curr], points_db[nxt])
            new_g = g + step_dist
            
            if new_g < g_scores.get(nxt, float('inf')):
                g_scores[nxt] = new_g
                h = heuristic(nxt, end_set, points_db)
                new_f = new_g + h
                
                aug_edges_used[curr][nxt] = {
                    'To': nxt,
                    'Remarks': type_str,
                    'Dist': step_dist
                }
                
                heapq.heappush(open_set, (new_f, nxt, path + [nxt], new_g))
                
    return None, None
