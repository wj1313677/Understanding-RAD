# Route Engine

A modular Python package for finding optimal flight routes between airports and waypoints in Free Route Airspace (FRA), with full compliance validation.

## Features

- **Flexible Input**: Find routes between any combination of:
  - Airport → Airport (e.g., `EDDF` → `LGAV`)
  - Waypoint → Waypoint (e.g., `KOMIB` → `TALAS`)
  - Airport → Waypoint or Waypoint → Airport
  
- **A* Pathfinding**: Optimized shortest-path algorithm with:
  - Haversine distance heuristic
  - Spatial grid indexing for performance
  - Simulated FRA connectivity (400km range)
  
- **FRA Rule Validation**:
  - ✅ FLOS (Flight Level Orientation Scheme) compliance
  - ✅ Airspace boundary rules (Same Airspace / Cross-Border)
  - ✅ Level availability checks
  - ✅ En-route and Arrival/Departure status verification
  
- **Detailed Output**: 
  - Comprehensive route tables with all waypoint details
  - Connectivity rule explanations for each segment
  - Total distance calculation
  - Departure/Arrival requirements from Annexes

## Installation

No installation required. The module is self-contained in the `route_engine/` directory.

## Usage

### Basic Example

```python
from route_engine import find_route, print_route

# Quick table output
print_route("EDDF", "LGAV")

# Programmatic access
result = find_route("KOMIB", "TALAS")
if result:
    print(f"Distance: {result['total_distance']:.1f} km")
    print(f"Waypoints: {result['waypoint_count']}")
    for wp in result['route']:
        print(f"  {wp['name']} ({wp['airspace']})")
```

### Output Format

The `find_route()` function returns a dictionary:

```python
{
    'success': True,
    'route': [
        {
            'seq': 1,
            'name': 'KOMIB',
            'type': 'Waypoint',
            'airspace': 'EDUU',
            'cross_border': '',
            'flos': '-',
            'levels': 'FL245 / FL660',
            'status_enr': 'EX',
            'status_ad': '-',
            'dist': '259.9',
            'connectivity_rule': 'Same Airspace',
            'remarks': '-'
        },
        # ... more waypoints
    ],
    'total_distance': 1357.7,
    'start': 'KOMIB',
    'end': 'TALAS',
    'waypoint_count': 9
}
```

### Table Output

Use `output_format='table'` to get a formatted markdown table:

```python
result = find_route("EDDF", "LGAV", output_format='table')
print(result['table'])
```

Output:
```
### Route Details Table
| Seq | Point | Type | Airspace | Cross-Border | FLOS | Levels | Status (Enr) | Status (A/D) | Dist (km) | Connectivity Rule | Remarks |
|-----|-------|------|----------|--------------|------|--------|--------------|--------------|-----------|-------------------|---------|
| 1   | EDDF  | Airport | ED    | -            | -    | -      | -            | -            | Transition | Departure Logic   | SID: SULUS... |
| 2   | SULUS | Waypoint | EDUU | -            | -    | FL315/660 | I         | -            | 260.6     | Same Airspace     | -         |
...
```

## Module Structure

```
route_engine/
├── __init__.py         # Main API (find_route, print_route)
├── config.py           # File paths and constants
├── data_loader.py      # CSV parsing and point resolution
├── router.py           # A* algorithm implementation
├── utils.py            # Math helpers (distance, coordinate parsing)
└── validator.py        # FRA rule validation
```

## Data Requirements

The module expects the following CSV files in the workspace root:

- `download_11487/FRA_Points.csv` - All FRA waypoints with attributes
- `Annex_3A_DEP.csv` - Departure procedures
- `Annex_3A_ARR.csv` - Arrival procedures (optional)
- `Annex_2B.csv` - Arrival fallback data
- `Annex_3B_DCT.csv` - Explicit direct routes

## Testing

Run the comprehensive test suite:

```bash
python3 test_route_engine.py
```

Tests include:
1. Airport to Airport (EDDF → LGAV)
2. Waypoint to Waypoint (KOMIB → TALAS)
3. Waypoint to Airport (KOMIB → LGAV)
4. Airport to Waypoint (EDDF → TALAS)
5. Dictionary output format
6. Error handling

## FRA Connectivity Rules

The router enforces strict P1-driven cross-border logic:

1. **Same Airspace**: Direct connection allowed if both points share the same `Airspace Location Indicators`
2. **Cross-Border**: Connection allowed only if P1's `Cross-Border FRA States` explicitly lists P2's airspace
3. **Distance Limit**: Simulated connections limited to 400km

Example connectivity validation:
- `NENUM` (EDUU, Cross-Border: LOVV) → `NIDLO` (LOVV) ✅ "Cross-Border > LOVV"
- `KOMIB` (EDUU) → `NENUM` (EDUU) ✅ "Same Airspace"

## Performance

- **Spatial Grid**: O(1) neighbor lookup using 2° grid cells
- **A* Heuristic**: Haversine distance to nearest goal
- **Typical Runtime**: <1 second for 1000+ waypoint searches

## License

Part of the Understanding-RAD project.
