from .utils import parse_fl

def is_point_valid(point_data, intended_fl=320, direction='EAST'):
    """
    Checks if a point is valid based on FRA constraints:
    1. Level Availability
    2. FLOS (Flight Level Orientation Scheme)
    3. FRA Status (En-Route vs Arr/Dep)
    """
    # 1. Level Availability check
    lvl_avail = point_data.get('Level Availability', '-')
    if lvl_avail and '/' in lvl_avail:
        parts = lvl_avail.split('/')
        min_fl = parse_fl(parts[0].strip())
        max_fl = parse_fl(parts[1].strip())
        
        if intended_fl < min_fl or intended_fl > max_fl:
            return False

    # 2. FLOS Check
    # "ODD", "EVEN", "ALL", "ODD/EVEN", etc.
    flos = point_data.get('FLOS', 'ALL')
    if flos == 'EVEN' and direction == 'EAST':
        return False # Eastbound usually Odd
    # Add more complex FLOS logic if needed (e.g. ODD/EVEN depends on entry/exit)
    
    # 3. Status Check (Optional strictness)
    # enroute_status = point_data.get('FRA Status En-Route', '-')
    # arr_dep_status = point_data.get('FRA Status ARR/DEP', '-')
    # For now, we assume if it exists in the DB, it's usable, subject to connectivity.
    
    return True

def allow_simulated_connection(p1, p2):
    """
    Determines if a direct simulated connection is allowed between two points.
    Returns: (is_allowed, reason_string)
    """
    # Rule 1: Same Airspace
    as1 = p1.get('Airspace Location Indicators', '').strip()
    as2 = p2.get('Airspace Location Indicators', '').strip()
    
    if as1 and as2 and as1 == as2:
        return True, "Same Airspace"
    
    # Rule 2: Cross-Border Logic (Strict P1 "Push")
    # P1 must explicitly list P2's airspace in its Cross-Border list.
    cb1 = p1.get('Cross-Border FRA States', '')
    
    if as2 and cb1 and as2 in cb1: 
        return True, f"Cross-Border > {as2}"
    
    return False, None
