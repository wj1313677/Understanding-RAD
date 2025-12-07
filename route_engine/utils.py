import math
import re

def parse_coordinate(coord_str):
    """
    Parses a coordinate string which might be in DMS format (e.g. N500424) 
    or just a decimal string (less likely for this dataset).
    Returns decimal degrees.
    """
    if not coord_str:
        return 0.0
    
    # Check if it looks like DMS: e.g. starts with N, S, E, W
    direction = coord_str[0]
    if direction in ['N', 'S', 'E', 'W']:
        # Format: D [D] D M M S S
        # N/S: 7 chars (e.g. N500424 -> N 50 04 24)
        # E/W: 8 chars (e.g. E0083416 -> E 008 34 16)
        try:
            val = coord_str[1:]
            if direction in ['N', 'S']:
                deg = int(val[0:2])
                min_ = int(val[2:4])
                sec = int(val[4:6])
            else:
                deg = int(val[0:3])
                min_ = int(val[3:5])
                sec = int(val[5:7])
            
            decimal = deg + min_ / 60.0 + sec / 3600.0
            
            if direction in ['S', 'W']:
                decimal = -decimal
            return decimal
        except (ValueError, IndexError):
            # Fallback if parsing fails
            return 0.0
    else:
        # Assume decimal string
        try:
            return float(coord_str)
        except ValueError:
            return 0.0

def parse_fl(fl_str):
    """Parses Flight Level string (e.g. 'FL245', '245', 'GND', 'UNL')."""
    s = fl_str.strip().upper()
    if 'FL' in s:
        s = s.replace('FL', '')
    
    if s == 'GND': return 0
    if s == 'UNL': return 999
    if s == 'LAL': return 0 # Lower Airspace Limit? Treat as low.
    
    try:
        return int(s)
    except ValueError:
        return 0

def distance(p1, p2):
    """Calculates Haversine distance between two points (dicts with 'coordinates')."""
    # Try getting pre-parsed coordinates first
    lat1 = p1.get('lat')
    lon1 = p1.get('lon')
    lat2 = p2.get('lat')
    lon2 = p2.get('lon')

    # If not present, parse on the fly (less efficient, mainly for fallback)
    if lat1 is None: lat1 = parse_coordinate(p1.get('FRA Point Latitude', ''))
    if lon1 is None: lon1 = parse_coordinate(p1.get('FRA Point Longitude', ''))
    if lat2 is None: lat2 = parse_coordinate(p2.get('FRA Point Latitude', ''))
    if lon2 is None: lon2 = parse_coordinate(p2.get('FRA Point Longitude', ''))

    R = 6371.0 # Radius of Earth in km
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c
