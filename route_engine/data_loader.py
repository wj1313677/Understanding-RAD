import csv
import collections
import re
from .config import (
    FRA_POINTS_FILE, ANNEX_3B_DCT_FILE, 
    ANNEX_3A_DEP_FILE, ANNEX_3A_ARR_FILE, ANNEX_2B_FILE
)
from .utils import parse_coordinate

def load_fra_points():
    """Loads FRA points from CSV into a dictionary keyed by Point Name."""
    points = {}
    try:
        with open(FRA_POINTS_FILE, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('FRA Point'):
                    name = row['FRA Point']
                    # Pre-parse coordinates for speed
                    row['lat'] = parse_coordinate(row.get('FRA Point Latitude', ''))
                    row['lon'] = parse_coordinate(row.get('FRA Point Longitude', ''))
                    points[name] = row
    except FileNotFoundError:
        print(f"Error: {FRA_POINTS_FILE} not found.")
    return points

def load_dct_edges():
    """Loads explicit DCT edges from Annex 3B."""
    edges = collections.defaultdict(list)
    try:
        with open(ANNEX_3B_DCT_FILE, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            first = True
            for row in reader:
                if not row: continue
                if first:
                    first = False
                    continue
                if "From" in row[1]: continue
                if len(row) < 3: continue
                
                u = row[1]
                v = row[2]
                restr = row[6] if len(row) > 6 else ""
                
                if u and v:
                    edges[u].append({
                        'To': v,
                        'Remarks': restr or "Explicit DCT"
                    })
    except FileNotFoundError:
        print(f"Error: {ANNEX_3B_DCT_FILE} not found.")
    return edges

def get_departure_points(airport, points_db):
    """Finds valid FRA connection points for a Departure Airport (from Annex 3A)."""
    candi = set()
    try:
        with open(ANNEX_3A_DEP_FILE, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            next(reader) 
            for row in reader:
                if len(row) < 4: continue
                if row[1] == airport:
                    # Column 3 'DCT DEP PT' or 2 'Last PT SID'
                    pt_str = row[3] if row[3].strip() else row[2]
                    
                    # Clean up string
                    clean_pts = re.findall(r'[A-Z]{3,5}', pt_str)
                    for p in clean_pts:
                        if p in points_db:
                            candi.add(p)
    except FileNotFoundError:
        pass
    return list(candi)

def get_arrival_points(airport):
    """Finds valid FRA connection points for an Arrival Airport."""
    candi = set()
    
    # Try Annex 2B (simpler format, more reliable)
    try:
        with open(ANNEX_2B_FILE, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_str = str(row.values())
                if f"ARR {airport}" in row_str:
                    # Extract all 5-letter waypoint codes
                    clean_pts = re.findall(r'\b[A-Z]{5}\b', row_str)
                    for p in clean_pts:
                        candi.add(p)
    except FileNotFoundError:
        pass
    
    return list(candi)

def resolve_points(identifier, points_db):
    """
    Generic resolver.
    If identifier is an Airport (4 letters starting with E,L, etc. and not in points_db? 
    Actually Airports are NOT in points_db usually, or mapped differently).
    
    Logic:
    1. If identifier is in points_db -> It's a Waypoint. Return [identifier].
    2. If identifier looks like Airport code (4 chars) -> Try getting DEP/ARR options.
       (We need to know if it's Source or Dest to pick DEP or ARR logic... 
        But here we might return BOTH if ambiguous, or context is needed).
        
    For this specific refactor, let's keep it simple: 
    The Caller (router) decides if it's looking for Start or End options.
    """
    # This might be split into `resolve_start_options` and `resolve_end_options` in the Router 
    # or expose the specific getters.
    pass 
