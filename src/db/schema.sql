-- ============================================================================
-- PostgreSQL Schema for Route Restrictions Database
-- Generated: 2025-12-08
-- Purpose: Store and query ANNEX restriction data for route planning
-- ============================================================================

-- ============================================================================
-- CORE ENTITY TABLES
-- ============================================================================

-- Airports (extracted from multiple sources)
CREATE TABLE IF NOT EXISTS airports (
    icao_code CHAR(4) PRIMARY KEY,
    name VARCHAR(100),
    country_code CHAR(2),
    nas_fab VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_airports_country ON airports(country_code);
CREATE INDEX IF NOT EXISTS idx_airports_nas ON airports(nas_fab);

-- Waypoints (link to existing FRA_Points)
CREATE TABLE IF NOT EXISTS waypoints (
    waypoint_name VARCHAR(10) PRIMARY KEY,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(11, 7),
    airspace_location_1 VARCHAR(10),
    airspace_location_2 VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_waypoints_airspace1 ON waypoints(airspace_location_1);
CREATE INDEX IF NOT EXISTS idx_waypoints_airspace2 ON waypoints(airspace_location_2);

-- Airways
CREATE TABLE IF NOT EXISTS airways (
    airway_id VARCHAR(20) PRIMARY KEY,
    airway_type VARCHAR(10),  -- 'ATS', 'DCT', 'FRA'
    nas_fab VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Airspaces
CREATE TABLE IF NOT EXISTS airspaces (
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

CREATE TABLE IF NOT EXISTS airport_groups (
    group_id VARCHAR(50) PRIMARY KEY,
    definition TEXT NOT NULL,
    remarks TEXT,
    owner VARCHAR(10),
    release_date DATE,
    special_event VARCHAR(100),
    cacd_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_airport_groups_owner ON airport_groups(owner);

-- Junction table for group membership
CREATE TABLE IF NOT EXISTS airport_group_members (
    group_id VARCHAR(50) REFERENCES airport_groups(group_id) ON DELETE CASCADE,
    airport_icao CHAR(4) REFERENCES airports(icao_code) ON DELETE CASCADE,
    PRIMARY KEY (group_id, airport_icao),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_group_members_airport ON airport_group_members(airport_icao);

-- ============================================================================
-- RESTRICTIONS (Normalized - Simplified Approach)
-- ============================================================================

CREATE TABLE IF NOT EXISTS route_restrictions (
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
CREATE INDEX IF NOT EXISTS idx_rest_from_apt ON route_restrictions(from_airport) WHERE from_airport IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rest_to_apt ON route_restrictions(to_airport) WHERE to_airport IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rest_from_wpt ON route_restrictions(from_waypoint) WHERE from_waypoint IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rest_to_wpt ON route_restrictions(to_waypoint) WHERE to_waypoint IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rest_airspace ON route_restrictions(airspace_id) WHERE airspace_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rest_fl ON route_restrictions(fl_min, fl_max) WHERE fl_min IS NOT NULL OR fl_max IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rest_type ON route_restrictions(restriction_type);
CREATE INDEX IF NOT EXISTS idx_rest_source ON route_restrictions(source_annex, source_id);

-- GIN indexes for array columns (fast containment queries)
CREATE INDEX IF NOT EXISTS idx_rest_exc_arr_gin ON route_restrictions USING GIN(exception_arr_airports);
CREATE INDEX IF NOT EXISTS idx_rest_exc_dep_gin ON route_restrictions USING GIN(exception_dep_airports);
CREATE INDEX IF NOT EXISTS idx_rest_via_wpt_gin ON route_restrictions USING GIN(via_waypoints);
CREATE INDEX IF NOT EXISTS idx_rest_aircraft_gin ON route_restrictions USING GIN(aircraft_types);

-- ============================================================================
-- AIRPORT PROCEDURES (Merged DEP/ARR from Annex_3A)
-- ============================================================================

CREATE TABLE IF NOT EXISTS airport_procedures (
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

CREATE INDEX IF NOT EXISTS idx_proc_airport ON airport_procedures(airport_icao, procedure_type);
CREATE INDEX IF NOT EXISTS idx_proc_waypoint ON airport_procedures(waypoint_name);
CREATE INDEX IF NOT EXISTS idx_proc_type ON airport_procedures(procedure_type);

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- View: All departure points for airports
CREATE OR REPLACE VIEW v_departure_points AS
SELECT 
    airport_icao,
    waypoint_name,
    sid_star_name,
    time_applicability
FROM airport_procedures
WHERE procedure_type = 'DEP';

-- View: All arrival points for airports
CREATE OR REPLACE VIEW v_arrival_points AS
SELECT 
    airport_icao,
    waypoint_name,
    sid_star_name,
    time_applicability
FROM airport_procedures
WHERE procedure_type = 'ARR';

-- View: Expanded airport groups (for queries)
CREATE OR REPLACE VIEW v_airport_group_expanded AS
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

DROP TRIGGER IF EXISTS update_route_restrictions_updated_at ON route_restrictions;
CREATE TRIGGER update_route_restrictions_updated_at
    BEFORE UPDATE ON route_restrictions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- STATISTICS & MAINTENANCE
-- ============================================================================

-- Analyze tables after bulk load
-- Run: ANALYZE airports, waypoints, route_restrictions, airport_procedures;
