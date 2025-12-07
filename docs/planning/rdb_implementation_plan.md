# ANNEX Data to Relational Database - Implementation Plan

## Executive Summary

This plan proposes converting 9 ANNEX CSV files (~68,000 rows, 5.5MB) into a normalized relational database to enable efficient route searching and restriction checking for the FRA route engine.

## Data Inventory

| File | Rows | Size | Purpose |
|------|------|------|---------|
| **Annex_1.csv** | 117 | 12KB | Airport/Airspace Group Definitions |
| **Annex_2A.csv** | 1,654 | 174KB | Flight Level Capping Rules (City Pairs) |
| **Annex_2B.csv** | 46,181 | 2.7MB | Route Utilization Restrictions |
| **Annex_2C.csv** | 5,427 | 594KB | Restricted Airspace (RSA) Rules |
| **Annex_3A_ARR.csv** | 4,667 | 246KB | Arrival Procedures |
| **Annex_3A_Conditions.csv** | 226 | 17KB | RAD Application Conditions |
| **Annex_3A_DEP.csv** | 5,277 | 270KB | Departure Procedures |
| **Annex_3B_DCT.csv** | 9,968 | 712KB | Direct Route Restrictions |
| **Annex_3B_FRA_LIM.csv** | 637 | 24KB | FRA Airspace Limitations |

**Total**: 73,154 rows, 5.5MB

---

## Proposed Database Schema

### Core Tables

#### 1. **`airport_groups`** (from Annex_1)
```sql
CREATE TABLE airport_groups (
    group_id VARCHAR(50) PRIMARY KEY,
    definition TEXT NOT NULL,
    remarks TEXT,
    owner VARCHAR(10),
    release_date DATE,
    special_event VARCHAR(100),
    cacd_id VARCHAR(50)
);
CREATE INDEX idx_airport_groups_owner ON airport_groups(owner);
```

**Purpose**: Define reusable airport/airspace groups for rule matching  
**Rows**: ~117

---

#### 2. **`flight_level_caps`** (from Annex_2A)
```sql
CREATE TABLE flight_level_caps (
    id VARCHAR(20) PRIMARY KEY,
    from_adep VARCHAR(200),  -- Can be airport or group
    crossing_airspace VARCHAR(100),
    to_ades VARCHAR(200),
    condition TEXT,
    flight_level_capping VARCHAR(50),
    time_applicability VARCHAR(100),
    categorisation CHAR(1),  -- C=Capacity, S=Structural
    operational_goal TEXT,
    remarks TEXT,
    release_date DATE,
    special_event VARCHAR(100)
);
CREATE INDEX idx_fl_caps_from ON flight_level_caps(from_adep);
CREATE INDEX idx_fl_caps_to ON flight_level_caps(to_ades);
CREATE INDEX idx_fl_caps_airspace ON flight_level_caps(crossing_airspace);
```

**Purpose**: Enforce maximum flight levels for city pairs  
**Rows**: ~1,654  
**Key for**: Route validation, FL restriction checking

---

#### 3. **`route_restrictions`** (from Annex_2B)
```sql
CREATE TABLE route_restrictions (
    id VARCHAR(20) PRIMARY KEY,
    airway VARCHAR(50),
    from_point VARCHAR(50),
    to_point VARCHAR(50),
    point_or_airspace VARCHAR(100),
    utilization VARCHAR(500),
    time_applicability VARCHAR(100),
    categorisation CHAR(1),
    operational_goal TEXT,
    remarks TEXT,
    release_date DATE,
    special_event VARCHAR(100)
);
CREATE INDEX idx_route_rest_airway ON route_restrictions(airway);
CREATE INDEX idx_route_rest_from ON route_restrictions(from_point);
CREATE INDEX idx_route_rest_to ON route_restrictions(to_point);
```

**Purpose**: Define route utilization restrictions  
**Rows**: ~46,181 (largest table)  
**Key for**: Airway availability checking

---

#### 4. **`restricted_airspace`** (from Annex_2C)
```sql
CREATE TABLE restricted_airspace (
    id VARCHAR(20) PRIMARY KEY,
    aip_rsa_id VARCHAR(50),
    cacd_rsa_id VARCHAR(50),
    traffic_flow_rule TEXT,
    affected_routes TEXT,
    categorisation CHAR(1),
    operational_goal TEXT,
    remarks TEXT,
    nas_fab VARCHAR(10),
    release_date DATE,
    group_id VARCHAR(50),
    group_description TEXT,
    special_event VARCHAR(100)
);
CREATE INDEX idx_rsa_aip_id ON restricted_airspace(aip_rsa_id);
CREATE INDEX idx_rsa_cacd_id ON restricted_airspace(cacd_rsa_id);
CREATE INDEX idx_rsa_nas ON restricted_airspace(nas_fab);
```

**Purpose**: Military/danger areas that block flight planning  
**Rows**: ~5,427  
**Key for**: Airspace availability (dynamic via AUP/UUP)

---

#### 5. **`departure_procedures`** (from Annex_3A_DEP)
```sql
CREATE TABLE departure_procedures (
    dep_id VARCHAR(20) PRIMARY KEY,
    dep_ad VARCHAR(10) NOT NULL,
    last_pt_sid VARCHAR(100),
    dct_dep_pt VARCHAR(100),
    dep_fpl_options TEXT,
    dep_time_applicability VARCHAR(100),
    dep_operational_goal TEXT,
    dep_remarks TEXT,
    nas_fab VARCHAR(10),
    release_date DATE,
    special_event VARCHAR(100)
);
CREATE INDEX idx_dep_airport ON departure_procedures(dep_ad);
CREATE INDEX idx_dep_pt ON departure_procedures(dct_dep_pt);
```

**Purpose**: Departure point resolution for airports  
**Rows**: ~5,277  
**Key for**: Start node resolution in route_engine

---

#### 6. **`arrival_procedures`** (from Annex_3A_ARR)
```sql
CREATE TABLE arrival_procedures (
    arr_id VARCHAR(20) PRIMARY KEY,
    arr_ad VARCHAR(10) NOT NULL,
    first_pt_star VARCHAR(100),
    dct_arr_pt VARCHAR(100),
    arr_fpl_option TEXT,
    arr_time_applicability VARCHAR(100),
    arr_operational_goal TEXT,
    arr_remarks TEXT,
    nas_fab VARCHAR(10),
    release_date DATE,
    special_event VARCHAR(100)
);
CREATE INDEX idx_arr_airport ON arrival_procedures(arr_ad);
CREATE INDEX idx_arr_pt ON arrival_procedures(dct_arr_pt);
```

**Purpose**: Arrival point resolution for airports  
**Rows**: ~4,667  
**Key for**: End node resolution in route_engine

---

#### 7. **`rad_conditions`** (from Annex_3A_Conditions)
```sql
CREATE TABLE rad_conditions (
    rad_application_id VARCHAR(50),
    condition TEXT,
    explanation TEXT,
    time_applicability VARCHAR(100),
    nas_fab VARCHAR(10),
    release_date DATE,
    special_event VARCHAR(100),
    PRIMARY KEY (rad_application_id, condition)
);
CREATE INDEX idx_rad_cond_id ON rad_conditions(rad_application_id);
```

**Purpose**: Conditional logic for RAD applications  
**Rows**: ~226

---

#### 8. **`dct_restrictions`** (from Annex_3B_DCT)
```sql
CREATE TABLE dct_restrictions (
    id VARCHAR(20) PRIMARY KEY,
    from_point VARCHAR(50),
    to_point VARCHAR(50),
    lower_vert_limit VARCHAR(20),
    upper_vert_limit VARCHAR(20),
    available_or_not VARCHAR(50),
    time_applicability VARCHAR(100),
    categorisation CHAR(1),
    operational_goal TEXT,
    remarks TEXT,
    nas_fab VARCHAR(10),
    release_date DATE,
    special_event VARCHAR(100)
);
CREATE INDEX idx_dct_from ON dct_restrictions(from_point);
CREATE INDEX idx_dct_to ON dct_restrictions(to_point);
CREATE INDEX idx_dct_vertical ON dct_restrictions(lower_vert_limit, upper_vert_limit);
```

**Purpose**: Direct route (DCT) availability between waypoints  
**Rows**: ~9,968  
**Key for**: Explicit DCT edge validation

---

#### 9. **`fra_limitations`** (from Annex_3B_FRA_LIM)
```sql
CREATE TABLE fra_limitations (
    rad_application_id VARCHAR(50) PRIMARY KEY,
    airspace VARCHAR(100),
    airspace_vert_limit VARCHAR(100),
    time_applicability VARCHAR(100),
    dct_horiz_limit VARCHAR(50),
    cross_border_dct_limits VARCHAR(500),
    id_dct_limit VARCHAR(50),
    id_not_allowed_cross_border_dct TEXT,
    remarks TEXT,
    release_date DATE,
    special_event VARCHAR(100)
);
CREATE INDEX idx_fra_lim_airspace ON fra_limitations(airspace);
```

**Purpose**: FRA airspace-specific DCT limitations  
**Rows**: ~637  
**Key for**: FRA boundary crossing rules

---

## Normalization Strategy

### Extracted Lookup Tables

#### 10. **`airports`** (extracted from multiple sources)
```sql
CREATE TABLE airports (
    icao_code CHAR(4) PRIMARY KEY,
    name VARCHAR(100),
    country_code CHAR(2),
    nas_fab VARCHAR(10)
);
```

**Source**: Extract unique airports from `dep_ad`, `arr_ad`, group definitions  
**Rows**: ~500-1000 estimated

---

#### 11. **`waypoints`** (link to existing FRA_Points)
```sql
CREATE TABLE waypoints (
    waypoint_name VARCHAR(10) PRIMARY KEY,
    -- Foreign key to existing FRA_Points table
    FOREIGN KEY (waypoint_name) REFERENCES fra_points(fra_name)
);
```

**Source**: Extract from `from_point`, `to_point`, `dct_dep_pt`, `dct_arr_pt`  
**Purpose**: Link ANNEX data to FRA_Points master data

---

#### 12. **`time_periods`** (normalized time applicability)
```sql
CREATE TABLE time_periods (
    id SERIAL PRIMARY KEY,
    time_spec VARCHAR(200) UNIQUE NOT NULL,
    -- Parsed fields
    start_time TIME,
    end_time TIME,
    days_of_week VARCHAR(50),
    airac_period VARCHAR(100),
    is_h24 BOOLEAN DEFAULT FALSE
);
```

**Source**: Parse `time_applicability` columns across all tables  
**Purpose**: Enable time-based filtering

---

## Database Technology Recommendation

### Option 1: **SQLite** (Recommended for Embedded Use)
**Pros**:
- Zero configuration, file-based
- Perfect for Python integration
- Fast for <100K rows
- No server required

**Cons**:
- Single-writer limitation
- No built-in spatial indexing

**Use Case**: Embedded in `route_engine` for local validation

---

### Option 2: **PostgreSQL** (Recommended for Production)
**Pros**:
- Full ACID compliance
- PostGIS extension for spatial queries
- Advanced indexing (GiST, GIN)
- Concurrent access

**Cons**:
- Requires server setup
- More complex deployment

**Use Case**: Centralized route validation service

---

## Implementation Phases

### Phase 1: Schema Creation & Data Import
**Deliverables**:
1. SQL DDL scripts for all 12 tables
2. Python ETL script to parse CSVs and populate DB
3. Data validation report (row counts, constraint violations)

**Estimated Effort**: 2-3 days

---

### Phase 2: Query Optimization
**Deliverables**:
1. Composite indexes for common query patterns
2. Materialized views for complex joins
3. Query performance benchmarks

**Key Queries**:
```sql
-- Q1: Find FL caps for a city pair
SELECT flight_level_capping 
FROM flight_level_caps 
WHERE from_adep = ? AND to_ades = ? AND crossing_airspace = ?;

-- Q2: Check DCT availability
SELECT available_or_not 
FROM dct_restrictions 
WHERE from_point = ? AND to_point = ? 
  AND ? BETWEEN lower_vert_limit AND upper_vert_limit;

-- Q3: Get departure points for airport
SELECT dct_dep_pt 
FROM departure_procedures 
WHERE dep_ad = ?;
```

**Estimated Effort**: 1-2 days

---

### Phase 3: Integration with `route_engine`
**Deliverables**:
1. `route_engine/db_connector.py` - Database access layer
2. Update `validator.py` to query DB for restrictions
3. Update `data_loader.py` to use DB instead of CSV parsing

**Example Integration**:
```python
# route_engine/db_connector.py
import sqlite3

class RouteRestrictionDB:
    def __init__(self, db_path='route_restrictions.db'):
        self.conn = sqlite3.connect(db_path)
    
    def check_fl_cap(self, from_adep, to_ades, crossing_airspace):
        cursor = self.conn.execute(
            "SELECT flight_level_capping FROM flight_level_caps "
            "WHERE from_adep = ? AND to_ades = ? AND crossing_airspace = ?",
            (from_adep, to_ades, crossing_airspace)
        )
        return cursor.fetchone()
    
    def get_departure_points(self, airport):
        cursor = self.conn.execute(
            "SELECT dct_dep_pt FROM departure_procedures WHERE dep_ad = ?",
            (airport,)
        )
        return [row[0] for row in cursor.fetchall()]
```

**Estimated Effort**: 2-3 days

---

### Phase 4: Advanced Features
**Deliverables**:
1. Time-based filtering (AIRAC cycles, time-of-day)
2. Group expansion (resolve `PARIS_GROUP` to individual airports)
3. Conditional logic evaluation (RAD conditions)
4. Caching layer for frequent queries

**Estimated Effort**: 3-4 days

---

## Data Quality Considerations

### Issues Identified

1. **Multi-line Headers** (Annex_3A_ARR, Annex_2A)
   - **Impact**: CSV parsing failures
   - **Solution**: Pre-process CSVs to flatten headers

2. **Complex Group References** (Annex_1)
   - **Example**: `PARIS_GROUP` = `(LFPB, LFPG, LFPN, LFPO, LFPT, LFPV)`
   - **Solution**: Create `airport_group_members` junction table

3. **Conditional Logic in Text Fields**
   - **Example**: `"NOT AVBL FOR TFC EXC ARR/DEP EDDB & VIA BATEL"`
   - **Solution**: Parse into structured conditions or use full-text search

4. **Time Format Variations**
   - **Examples**: `H24`, `MON..FRI 06:30..10:00 (05:30..09:00)`, `AIRAC APR - FIRST AIRAC OCT`
   - **Solution**: Normalize to `time_periods` table with parser

---

## Recommended Next Steps

1. **User Review** of schema design
2. **Confirm** database technology (SQLite vs PostgreSQL)
3. **Prioritize** tables for Phase 1 (suggest: Annex_3A_DEP, Annex_3A_ARR, Annex_3B_DCT)
4. **Develop** ETL script for CSV → DB conversion
5. **Test** query performance with sample route searches

---

## Appendix: Junction Tables

### A. **`airport_group_members`**
```sql
CREATE TABLE airport_group_members (
    group_id VARCHAR(50),
    airport_icao CHAR(4),
    PRIMARY KEY (group_id, airport_icao),
    FOREIGN KEY (group_id) REFERENCES airport_groups(group_id),
    FOREIGN KEY (airport_icao) REFERENCES airports(icao_code)
);
```

**Purpose**: Expand group references like `PARIS_GROUP` to individual airports  
**Rows**: ~2,000-3,000 (estimated from 117 groups × avg 20 airports)

---

### B. **`restriction_conditions`** (parsed from text)
```sql
CREATE TABLE restriction_conditions (
    id SERIAL PRIMARY KEY,
    restriction_id VARCHAR(20),
    restriction_type VARCHAR(20), -- 'FL_CAP', 'RSA', 'DCT', etc.
    condition_type VARCHAR(50),   -- 'EXC_ARR_DEP', 'VIA', 'FLT_TYPE', etc.
    condition_value TEXT,
    FOREIGN KEY (restriction_id, restriction_type) 
        REFERENCES <dynamic based on type>
);
```

**Purpose**: Enable programmatic evaluation of complex conditions  
**Rows**: ~10,000-15,000 (many restrictions have multiple conditions)

---

## Performance Estimates

| Query Type | Expected Latency | Optimization |
|------------|------------------|--------------|
| FL Cap Lookup | <1ms | Indexed on (from, to, airspace) |
| DCT Availability | <2ms | Composite index on (from, to, FL) |
| Departure Points | <1ms | Indexed on airport code |
| RSA Check | <5ms | Spatial index (if using PostGIS) |
| Group Expansion | <10ms | Cached in memory |

**Total DB Size**: ~10-15MB (with indexes)  
**Memory Footprint**: ~50-100MB (with query cache)

