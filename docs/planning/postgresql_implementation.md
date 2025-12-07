# PostgreSQL RDB Implementation Plan

## Phase 1: Database Setup & Schema Creation

### 1.1 PostgreSQL Installation & Configuration

**Prerequisites**:
```bash
# Install PostgreSQL (macOS)
brew install postgresql@18
brew services start postgresql@18

# Create database
createdb route_restrictions

# Verify connection
psql route_restrictions
```

**Connection Configuration**:
```python
# config/database.py
DATABASE_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'route_restrictions',
    'user': 'postgres',  # or your username
    'password': '',      # set if needed
}
```

---

### 1.2 Directory Structure

```
Understanding-RAD/
├── src/
│   ├── db/
│   │   ├── __init__.py
│   │   ├── schema.sql           # DDL for all tables
│   │   ├── connection.py        # PostgreSQL connection manager
│   │   └── models.py            # SQLAlchemy ORM models (optional)
│   ├── etl/
│   │   ├── __init__.py
│   │   ├── parsers.py           # Text parsing functions
│   │   ├── loaders.py           # CSV → DB loaders
│   │   └── validators.py       # Data quality checks
│   └── config/
│       ├── __init__.py
│       └── database.py          # DB configuration
├── scripts/
│   ├── 01_create_schema.py      # Run DDL
│   ├── 02_load_data.py          # ETL pipeline
│   └── 03_verify_data.py        # Data validation
└── requirements.txt
```

---

### 1.3 Database Schema (PostgreSQL DDL)

**File**: `src/db/schema.sql`

```sql
-- ============================================================================
-- CORE ENTITY TABLES
-- ============================================================================

-- Airports (extracted from multiple sources)
CREATE TABLE airports (
    icao_code CHAR(4) PRIMARY KEY,
    name VARCHAR(100),
    country_code CHAR(2),
    nas_fab VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_airports_country ON airports(country_code);
CREATE INDEX idx_airports_nas ON airports(nas_fab);

-- Waypoints (link to existing FRA_Points)
CREATE TABLE waypoints (
    waypoint_name VARCHAR(10) PRIMARY KEY,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(11, 7),
    airspace_location_1 VARCHAR(10),
    airspace_location_2 VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_waypoints_airspace1 ON waypoints(airspace_location_1);
CREATE INDEX idx_waypoints_airspace2 ON waypoints(airspace_location_2);

-- Airways
CREATE TABLE airways (
    airway_id VARCHAR(20) PRIMARY KEY,
    airway_type VARCHAR(10),  -- 'ATS', 'DCT', 'FRA'
    nas_fab VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Airspaces
CREATE TABLE airspaces (
    airspace_id VARCHAR(50) PRIMARY KEY,
    airspace_type VARCHAR(20),  -- 'ACC', 'TMA', 'FRA', 'RSA'
    nas_fab VARCHAR(10),
    vertical_lower VARCHAR(20),
    vertical_upper VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- AIRPORT GROUPS (from Annex_1)
-- ============================================================================

CREATE TABLE airport_groups (
    group_id VARCHAR(50) PRIMARY KEY,
    definition TEXT NOT NULL,
    remarks TEXT,
    owner VARCHAR(10),
    release_date DATE,
    special_event VARCHAR(100),
    cacd_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_airport_groups_owner ON airport_groups(owner);

-- Junction table for group membership
CREATE TABLE airport_group_members (
    group_id VARCHAR(50) REFERENCES airport_groups(group_id) ON DELETE CASCADE,
    airport_icao CHAR(4) REFERENCES airports(icao_code) ON DELETE CASCADE,
    PRIMARY KEY (group_id, airport_icao),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_group_members_airport ON airport_group_members(airport_icao);

-- ============================================================================
-- RESTRICTIONS (Normalized - Simplified Approach)
-- ============================================================================

CREATE TABLE route_restrictions (
    id SERIAL PRIMARY KEY,
    
    -- Source reference
    source_annex VARCHAR(20),        -- 'Annex_2A', 'Annex_2B', etc.
    source_id VARCHAR(20),           -- Original ID from CSV
    
    -- Original text (for reference)
    utilization_text TEXT,
    condition_text TEXT,
    
    -- Parsed availability
    is_available BOOLEAN,            -- NULL = no restriction, TRUE = only avbl, FALSE = not avbl
    is_compulsory BOOLEAN DEFAULT FALSE,
    
    -- Parsed exceptions
    exception_arr_airports TEXT[],
    exception_dep_airports TEXT[],
    exception_waypoints TEXT[],
    
    -- Parsed VIA constraints
    via_waypoints TEXT[],
    via_airways TEXT[],
    
    -- Parsed FL constraints
    fl_min INTEGER,
    fl_max INTEGER,
    fl_constraint_location VARCHAR(50),  -- e.g., "AT KOMOB", "IN EDUUUTA"
    
    -- Parsed aircraft constraints
    aircraft_types TEXT[],
    flight_types TEXT[],              -- 'M' = Military, 'X' = Special, 'S' = Scheduled
    
    -- Spatial constraints
    from_airport CHAR(4) REFERENCES airports(icao_code),
    to_airport CHAR(4) REFERENCES airports(icao_code),
    from_waypoint VARCHAR(10) REFERENCES waypoints(waypoint_name),
    to_waypoint VARCHAR(10) REFERENCES waypoints(waypoint_name),
    airway_id VARCHAR(20) REFERENCES airways(airway_id),
    airspace_id VARCHAR(50) REFERENCES airspaces(airspace_id),
    crossing_airspace VARCHAR(100),
    
    -- Metadata
    restriction_type VARCHAR(20),     -- 'FL_CAP', 'ROUTE_UTIL', 'DCT', 'RSA', etc.
    categorisation CHAR(1),           -- 'C' = Capacity, 'S' = Structural
    operational_goal TEXT,
    remarks TEXT,
    time_applicability VARCHAR(100),
    nas_fab VARCHAR(10),
    release_date DATE,
    special_event VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for A* queries (critical for performance)
CREATE INDEX idx_rest_from_apt ON route_restrictions(from_airport) WHERE from_airport IS NOT NULL;
CREATE INDEX idx_rest_to_apt ON route_restrictions(to_airport) WHERE to_airport IS NOT NULL;
CREATE INDEX idx_rest_from_wpt ON route_restrictions(from_waypoint) WHERE from_waypoint IS NOT NULL;
CREATE INDEX idx_rest_to_wpt ON route_restrictions(to_waypoint) WHERE to_waypoint IS NOT NULL;
CREATE INDEX idx_rest_airspace ON route_restrictions(airspace_id) WHERE airspace_id IS NOT NULL;
CREATE INDEX idx_rest_fl ON route_restrictions(fl_min, fl_max) WHERE fl_min IS NOT NULL OR fl_max IS NOT NULL;
CREATE INDEX idx_rest_type ON route_restrictions(restriction_type);
CREATE INDEX idx_rest_source ON route_restrictions(source_annex, source_id);

-- GIN indexes for array columns (fast containment queries)
CREATE INDEX idx_rest_exc_arr_gin ON route_restrictions USING GIN(exception_arr_airports);
CREATE INDEX idx_rest_exc_dep_gin ON route_restrictions USING GIN(exception_dep_airports);
CREATE INDEX idx_rest_via_wpt_gin ON route_restrictions USING GIN(via_waypoints);
CREATE INDEX idx_rest_aircraft_gin ON route_restrictions USING GIN(aircraft_types);

-- ============================================================================
-- AIRPORT PROCEDURES (Merged DEP/ARR from Annex_3A)
-- ============================================================================

CREATE TABLE airport_procedures (
    id SERIAL PRIMARY KEY,
    
    -- Source reference
    source_annex VARCHAR(20),        -- 'Annex_3A_DEP' or 'Annex_3A_ARR'
    source_id VARCHAR(20),
    
    -- Core fields
    airport_icao CHAR(4) NOT NULL REFERENCES airports(icao_code),
    procedure_type VARCHAR(10) NOT NULL,  -- 'DEP', 'ARR'
    waypoint_name VARCHAR(10) NOT NULL REFERENCES waypoints(waypoint_name),
    
    -- Procedure details
    sid_star_name VARCHAR(100),
    fpl_options TEXT,
    time_applicability VARCHAR(100),
    operational_goal TEXT,
    remarks TEXT,
    
    -- Metadata
    nas_fab VARCHAR(10),
    release_date DATE,
    special_event VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_procedure_type CHECK (procedure_type IN ('DEP', 'ARR'))
);

CREATE INDEX idx_proc_airport ON airport_procedures(airport_icao, procedure_type);
CREATE INDEX idx_proc_waypoint ON airport_procedures(waypoint_name);
CREATE INDEX idx_proc_type ON airport_procedures(procedure_type);

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- View: All departure points for airports
CREATE VIEW v_departure_points AS
SELECT 
    airport_icao,
    waypoint_name,
    sid_star_name,
    time_applicability
FROM airport_procedures
WHERE procedure_type = 'DEP';

-- View: All arrival points for airports
CREATE VIEW v_arrival_points AS
SELECT 
    airport_icao,
    waypoint_name,
    sid_star_name,
    time_applicability
FROM airport_procedures
WHERE procedure_type = 'ARR';

-- View: Expanded airport groups (for queries)
CREATE VIEW v_airport_group_expanded AS
SELECT 
    g.group_id,
    g.definition,
    m.airport_icao,
    a.name AS airport_name
FROM airport_groups g
JOIN airport_group_members m ON g.group_id = m.group_id
JOIN airports a ON m.airport_icao = a.icao_code;

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_route_restrictions_updated_at
    BEFORE UPDATE ON route_restrictions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- STATISTICS & MAINTENANCE
-- ============================================================================

-- Analyze tables after bulk load
-- Run: ANALYZE airports, waypoints, route_restrictions, airport_procedures;
```

---

### 1.4 Connection Manager

**File**: `src/db/connection.py`

```python
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import os

class DatabaseConnection:
    def __init__(self, config=None):
        self.config = config or {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_NAME', 'route_restrictions'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', ''),
        }
        self._conn = None
    
    def connect(self):
        """Establish database connection"""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(**self.config)
        return self._conn
    
    def close(self):
        """Close database connection"""
        if self._conn and not self._conn.closed:
            self._conn.close()
    
    @contextmanager
    def get_cursor(self, dict_cursor=True):
        """Context manager for database cursor"""
        conn = self.connect()
        cursor_factory = RealDictCursor if dict_cursor else None
        cursor = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def execute_script(self, sql_file_path):
        """Execute SQL script from file"""
        with open(sql_file_path, 'r') as f:
            sql = f.read()
        
        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(sql)
        print(f"✅ Executed: {sql_file_path}")

# Singleton instance
db = DatabaseConnection()
```

---

### 1.5 Requirements

**File**: `requirements.txt`

```
psycopg2-binary==2.9.9
pandas==2.1.4
python-dotenv==1.0.0
```

---

## Next Steps

1. **Install PostgreSQL** and create database
2. **Run schema creation**: `python scripts/01_create_schema.py`
3. **Implement ETL parsers** (Phase 2)
4. **Load data** from ANNEX CSVs
5. **Integrate with route_engine**

