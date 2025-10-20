#!/usr/bin/env python
#
# NAME: RAD_ETL_Parser_CSV_v2.py
# AUTH: RAD-Advisor
# DESC: Parses a set of 9 RAD CSV files and loads them into a normalized 
#       SQLite database for FPL validation. (Full Bugfix Version)

import sqlite3
import pandas as pd
import re
import sys
import glob
import os

# --- REGEX DEFINITIONS FOR RAD CONDITIONAL GRAMMAR ---
RAD_GRAMMAR = [
    ('LEVEL_BTN', re.compile(r'BTN (FL\d{3}) AND (FL\d{3})')),
    ('LEVEL_ABV', re.compile(r'(AT OR ABV|ABV) (FL\d{3})')),
    ('LEVEL_BLW', re.compile(r'(AT OR BLW|BLW) (FL\d{3})')),
    ('TIME_DLY', re.compile(r'DLY (\d{4})-(\d{4})')),
    ('TIME_DAYS', re.compile(r'(MON|TUE|WED|THU|FRI|SAT|SUN)-(MON|TUE|WED|THU|FRI|SAT|SUN) (\d{4})-(\d{4})')),
    ('FLOW_ADEP', re.compile(r'(ONLY|EXC) ADEP ([A-Z]{4})')),
    ('FLOW_ADES', re.compile(r'(ONLY|EXC) ADES ([A-Z]{4})')),
    ('FLOW_ADEP_AREA', re.compile(r'(ONLY|EXC) ADEP (\w+_AD|\w+_GROUP)')),
    ('FLOW_ADES_AREA', re.compile(r'(ONLY|EXC) ADES (\w+_AD|\w+_GROUP)')),
    ('FLOW_VIA', re.compile(r'(ONLY|EXC) (TFC VIA|VIA) ([A-Z0-9]+)')),
    ('ACFT_TYPE', re.compile(r'(ONLY|EXC) ACFT TYPE ([A-Z0-9]{3,4})')),
    ('OPERATIONAL', re.compile(r'(ONLY|EXC) (OAT|STATE ACFT|MIL TFC|RNAV\s?\d|PBN/[A-Z0-9]+|FLT-TYPE \([M]\))')),
    ('FLT_TYPE', re.compile(r'FLT-TYPE \((M)\)')), # Specific case
]

class RADParser:
    """
    Parses a directory of structured RAD CSV files and loads them into a
    normalized SQLite database.
    """
    def __init__(self, db_path="rad_master.db"):
        self.db_path = db_path
        print(f"Initializing parser. Database will be created at: {self.db_path}")
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON;") # Enforce foreign keys
        self.cursor = self.conn.cursor()
        
        # Caches for fast ID lookups (Entity Resolution)
        self.point_cache = {}
        self.aerodrome_cache = {}
        self.area_cache = {}
        self.ats_route_cache = {}
        self.procedure_cache = {}
        
        # Condition "Palette" Caches
        self.cond_time_cache = {}
        self.cond_level_cache = {}
        self.cond_flow_cache = {}
        self.cond_aircraft_cache = {}
        self.cond_op_cache = {}
        
        # Function to clean CSV headers
        self.clean_header = lambda c: c.strip().replace('\n', ' ')

    def _execute_schema(self):
        """Creates all database tables based on our design."""
        print("Creating database schema...")
        schema = """
        -- SHARED ENTITIES
        CREATE TABLE IF NOT EXISTS tbl_Points (
            point_id INTEGER PRIMARY KEY, identifier TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS tbl_Aerodromes (
            aerodrome_id INTEGER PRIMARY KEY, icao_code CHAR(4) NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS tbl_ATS_Routes (
            route_id INTEGER PRIMARY KEY, identifier TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS tbl_Areas_Annex1 (
            area_id INTEGER PRIMARY KEY, area_name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS jct_Area_Aerodromes (
            area_id INTEGER NOT NULL, aerodrome_id INTEGER NOT NULL,
            PRIMARY KEY (area_id, aerodrome_id),
            FOREIGN KEY (area_id) REFERENCES tbl_Areas_Annex1(area_id),
            FOREIGN KEY (aerodrome_id) REFERENCES tbl_Aerodromes(aerodrome_id)
        );
        CREATE TABLE IF NOT EXISTS tbl_Procedures (
            procedure_id INTEGER PRIMARY KEY,
            procedure_name TEXT NOT NULL,
            procedure_type TEXT NOT NULL, -- 'SID' or 'STAR'
            aerodrome_id INTEGER NOT NULL,
            point_id INTEGER NOT NULL, -- The point the procedure is named for/transitions to/from
            UNIQUE(procedure_name, procedure_type, aerodrome_id),
            FOREIGN KEY (aerodrome_id) REFERENCES tbl_Aerodromes(aerodrome_id),
            FOREIGN KEY (point_id) REFERENCES tbl_Points(point_id)
        );

        -- CONDITION PALETTE TABLES (REUSABLE)
        CREATE TABLE IF NOT EXISTS tbl_Cond_Time (
            time_cond_id INTEGER PRIMARY KEY, availability_days TEXT, time_start TEXT, time_end TEXT, UNIQUE(availability_days, time_start, time_end)
        );
        CREATE TABLE IF NOT EXISTS tbl_Cond_Level (
            level_cond_id INTEGER PRIMARY KEY, logic TEXT, level_1 INTEGER, level_2 INTEGER, UNIQUE(logic, level_1, level_2)
        );
        CREATE TABLE IF NOT EXISTS tbl_Cond_Flow (
            flow_cond_id INTEGER PRIMARY KEY, flow_type TEXT, logic TEXT, aerodrome_id INTEGER, area_id INTEGER, point_id INTEGER,
            FOREIGN KEY (aerodrome_id) REFERENCES tbl_Aerodromes(aerodrome_id),
            FOREIGN KEY (area_id) REFERENCES tbl_Areas_Annex1(area_id),
            FOREIGN KEY (point_id) REFERENCES tbl_Points(point_id),
            UNIQUE(flow_type, logic, aerodrome_id, area_id, point_id)
        );
        CREATE TABLE IF NOT EXISTS tbl_Cond_Aircraft (
            aircraft_cond_id INTEGER PRIMARY KEY, aircraft_type TEXT, logic TEXT, UNIQUE(aircraft_type, logic)
        );
        CREATE TABLE IF NOT EXISTS tbl_Cond_Operational (
            op_cond_id INTEGER PRIMARY KEY, condition_code TEXT, logic TEXT, UNIQUE(condition_code, logic)
        );
        
        -- ANNEX 2A RULES (Level Capping)
        CREATE TABLE IF NOT EXISTS tbl_Rules_Annex2A (
            rule_id INTEGER PRIMARY KEY, rule_identifier TEXT UNIQUE,
            adep_aerodrome_id INTEGER, adep_area_id INTEGER,
            ades_aerodrome_id INTEGER, ades_area_id INTEGER,
            max_flight_level INTEGER NOT NULL, description TEXT,
            FOREIGN KEY (adep_aerodrome_id) REFERENCES tbl_Aerodromes(aerodrome_id),
            FOREIGN KEY (adep_area_id) REFERENCES tbl_Areas_Annex1(area_id),
            FOREIGN KEY (ades_aerodrome_id) REFERENCES tbl_Aerodromes(aerodrome_id),
            FOREIGN KEY (ades_area_id) REFERENCES tbl_Areas_Annex1(area_id)
        );
        CREATE TABLE IF NOT EXISTS jct_Annex2A_Time (rule_id INTEGER NOT NULL, time_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, time_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex2A(rule_id), FOREIGN KEY (time_cond_id) REFERENCES tbl_Cond_Time(time_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex2A_Aircraft (rule_id INTEGER NOT NULL, aircraft_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, aircraft_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex2A(rule_id), FOREIGN KEY (aircraft_cond_id) REFERENCES tbl_Cond_Aircraft(aircraft_cond_id));

        -- ANNEX 2B RULES (En-route Structural)
        CREATE TABLE IF NOT EXISTS tbl_Rules_Annex2B (
            rule_id INTEGER PRIMARY KEY, rule_identifier TEXT UNIQUE,
            ats_route_id INTEGER, from_point_id INTEGER, to_point_id INTEGER,
            point_or_airspace_id INTEGER, -- For rules applying to a point, not a segment
            availability TEXT NOT NULL, -- AVBL, NOT AVBL, COMPULSORY
            description TEXT,
            FOREIGN KEY (ats_route_id) REFERENCES tbl_ATS_Routes(route_id),
            FOREIGN KEY (from_point_id) REFERENCES tbl_Points(point_id),
            FOREIGN KEY (to_point_id) REFERENCES tbl_Points(point_id),
            FOREIGN KEY (point_or_airspace_id) REFERENCES tbl_Points(point_id)
        );
        CREATE TABLE IF NOT EXISTS jct_Annex2B_Time (rule_id INTEGER NOT NULL, time_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, time_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex2B(rule_id), FOREIGN KEY (time_cond_id) REFERENCES tbl_Cond_Time(time_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex2B_Level (rule_id INTEGER NOT NULL, level_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, level_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex2B(rule_id), FOREIGN KEY (level_cond_id) REFERENCES tbl_Cond_Level(level_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex2B_Flow (rule_id INTEGER NOT NULL, flow_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, flow_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex2B(rule_id), FOREIGN KEY (flow_cond_id) REFERENCES tbl_Cond_Flow(flow_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex2B_Aircraft (rule_id INTEGER NOT NULL, aircraft_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, aircraft_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex2B(rule_id), FOREIGN KEY (aircraft_cond_id) REFERENCES tbl_Cond_Aircraft(aircraft_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex2B_Operational (rule_id INTEGER NOT NULL, op_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, op_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex2B(rule_id), FOREIGN KEY (op_cond_id) REFERENCES tbl_Cond_Operational(op_cond_id));
        
        -- ANNEX 2C RULES (FUA / AUP-UUP)
        CREATE TABLE IF NOT EXISTS tbl_Rules_Annex2C (
            rule_id INTEGER PRIMARY KEY, rule_identifier TEXT UNIQUE,
            airspace_name TEXT UNIQUE NOT NULL, airspace_type TEXT,
            default_lower_fl INTEGER, default_upper_fl INTEGER, description TEXT
        );
        CREATE TABLE IF NOT EXISTS tbl_AUP_Activations (
            activation_id INTEGER PRIMARY KEY, rule_id INTEGER NOT NULL, valid_date TEXT NOT NULL,
            time_start TEXT NOT NULL, time_end TEXT NOT NULL,
            active_lower_fl INTEGER NOT NULL, active_upper_fl INTEGER NOT NULL,
            aup_publication_timestamp TEXT,
            FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex2C(rule_id)
        );
        CREATE TABLE IF NOT EXISTS jct_Annex2C_Flow (rule_id INTEGER NOT NULL, flow_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, flow_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex2C(rule_id), FOREIGN KEY (flow_cond_id) REFERENCES tbl_Cond_Flow(flow_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex2C_Operational (rule_id INTEGER NOT NULL, op_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, op_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex2C(rule_id), FOREIGN KEY (op_cond_id) REFERENCES tbl_Cond_Operational(op_cond_id));

        -- ANNEX 3A RULES (Terminal Connectivity & Conditions)
        CREATE TABLE IF NOT EXISTS tbl_Rules_Annex3A_Connectivity (
            conn_rule_id INTEGER PRIMARY KEY, rule_identifier TEXT UNIQUE,
            aerodrome_id INTEGER NOT NULL, rule_type TEXT NOT NULL, -- DEP, ARR
            en_route_point_id INTEGER, -- The point defining the transition
            required_procedure_name TEXT, -- The name of the SID/STAR
            FOREIGN KEY (aerodrome_id) REFERENCES tbl_Aerodromes(aerodrome_id),
            FOREIGN KEY (en_route_point_id) REFERENCES tbl_Points(point_id)
        );
        CREATE TABLE IF NOT EXISTS tbl_Rules_Annex3A_Conditions (
            cond_rule_id INTEGER PRIMARY KEY, rule_identifier TEXT UNIQUE,
            aerodrome_id INTEGER, -- Can be null if it's an airspace rule
            area_id INTEGER, -- For FRA_LIM rules
            applicability TEXT, -- DEP, ARR, GENERAL
            condition_type TEXT NOT NULL, -- e.g., 'Limits', 'FRA LIM'
            value TEXT, -- e.g., '0NM' or the complex 'Explanation' string
            description TEXT,
            FOREIGN KEY (aerodrome_id) REFERENCES tbl_Aerodromes(aerodrome_id),
            FOREIGN KEY (area_id) REFERENCES tbl_Areas_Annex1(area_id)
        );
        -- *** START SCHEMA FIX FOR BUG 4 ***
        -- These tables are required to correctly parse DEP/ARR rules
        -- that have level, flow, or operational conditions.
        CREATE TABLE IF NOT EXISTS jct_Annex3A_Conn_Time (conn_rule_id INTEGER NOT NULL, time_cond_id INTEGER NOT NULL, PRIMARY KEY(conn_rule_id, time_cond_id), FOREIGN KEY (conn_rule_id) REFERENCES tbl_Rules_Annex3A_Connectivity(conn_rule_id), FOREIGN KEY (time_cond_id) REFERENCES tbl_Cond_Time(time_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex3A_Conn_Level (conn_rule_id INTEGER NOT NULL, level_cond_id INTEGER NOT NULL, PRIMARY KEY(conn_rule_id, level_cond_id), FOREIGN KEY (conn_rule_id) REFERENCES tbl_Rules_Annex3A_Connectivity(conn_rule_id), FOREIGN KEY (level_cond_id) REFERENCES tbl_Cond_Level(level_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex3A_Conn_Flow (conn_rule_id INTEGER NOT NULL, flow_cond_id INTEGER NOT NULL, PRIMARY KEY(conn_rule_id, flow_cond_id), FOREIGN KEY (conn_rule_id) REFERENCES tbl_Rules_Annex3A_Connectivity(conn_rule_id), FOREIGN KEY (flow_cond_id) REFERENCES tbl_Cond_Flow(flow_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex3A_Conn_Operational (conn_rule_id INTEGER NOT NULL, op_cond_id INTEGER NOT NULL, PRIMARY KEY(conn_rule_id, op_cond_id), FOREIGN KEY (conn_rule_id) REFERENCES tbl_Rules_Annex3A_Connectivity(conn_rule_id), FOREIGN KEY (op_cond_id) REFERENCES tbl_Cond_Operational(op_cond_id));
        -- This table is for the "Conditions" file (e.g., "LG_LIM_AD")
        CREATE TABLE IF NOT EXISTS jct_Annex3A_Cond_Time (cond_rule_id INTEGER NOT NULL, time_cond_id INTEGER NOT NULL, PRIMARY KEY(cond_rule_id, time_cond_id), FOREIGN KEY (cond_rule_id) REFERENCES tbl_Rules_Annex3A_Conditions(cond_rule_id), FOREIGN KEY (time_cond_id) REFERENCES tbl_Cond_Time(time_cond_id));
        -- *** END SCHEMA FIX FOR BUG 4 ***

        -- ANNEX 3B RULES (En-route DCT)
        CREATE TABLE IF NOT EXISTS tbl_Rules_Annex3B (
            rule_id INTEGER PRIMARY KEY, rule_identifier TEXT UNIQUE,
            from_point_id INTEGER NOT NULL, to_point_id INTEGER NOT NULL,
            availability TEXT NOT NULL, rule_type TEXT NOT NULL, -- DCT, FRA LIM
            description TEXT,
            FOREIGN KEY (from_point_id) REFERENCES tbl_Points(point_id),
            FOREIGN KEY (to_point_id) REFERENCES tbl_Points(point_id)
        );
        CREATE TABLE IF NOT EXISTS jct_Annex3B_Time (rule_id INTEGER NOT NULL, time_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, time_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex3B(rule_id), FOREIGN KEY (time_cond_id) REFERENCES tbl_Cond_Time(time_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex3B_Level (rule_id INTEGER NOT NULL, level_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, level_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex3B(rule_id), FOREIGN KEY (level_cond_id) REFERENCES tbl_Cond_Level(level_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex3B_Flow (rule_id INTEGER NOT NULL, flow_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, flow_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex3B(rule_id), FOREIGN KEY (flow_cond_id) REFERENCES tbl_Cond_Flow(flow_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex3B_Aircraft (rule_id INTEGER NOT NULL, aircraft_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, aircraft_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex3B(rule_id), FOREIGN KEY (aircraft_cond_id) REFERENCES tbl_Cond_Aircraft(aircraft_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex3B_Operational (rule_id INTEGER NOT NULL, op_cond_id INTEGER NOT NULL, PRIMARY KEY(rule_id, op_cond_id), FOREIGN KEY (rule_id) REFERENCES tbl_Rules_Annex3B(rule_id), FOREIGN KEY (op_cond_id) REFERENCES tbl_Cond_Operational(op_cond_id));
        """
        self.cursor.executescript(schema)
        self.conn.commit()
        print("Schema created successfully.")

    # --- ENTITY RESOLUTION (GET-OR-CREATE) HELPERS ---

    def _get_or_create(self, cache, table, pk_col, lookup_col, lookup_val):
        """
        Generic helper to get or create an entity ID.
        (Corrected Version)
        """
        if not lookup_val or pd.isna(lookup_val):
            return None
        lookup_val = str(lookup_val).strip()
        if lookup_val in cache:
            return cache[lookup_val]
        
        self.cursor.execute(f"SELECT {pk_col} FROM {table} WHERE {lookup_col} = ?", (lookup_val,))
        row = self.cursor.fetchone()
        if row:
            entity_id = row[0]
        else:
            self.cursor.execute(f"INSERT INTO {table} ({lookup_col}) VALUES (?)", (lookup_val,))
            entity_id = self.cursor.lastrowid
        
        cache[lookup_val] = entity_id
        return entity_id

    def get_point(self, name):
        return self._get_or_create(self.point_cache, 'tbl_Points', 'point_id', 'identifier', name)
    
    def get_aerodrome(self, icao):
        if not icao or pd.isna(icao) or len(str(icao).strip()) != 4:
            return None
        return self._get_or_create(self.aerodrome_cache, 'tbl_Aerodromes', 'aerodrome_id', 'icao_code', icao)
        
    def get_area(self, name):
        return self._get_or_create(self.area_cache, 'tbl_Areas_Annex1', 'area_id', 'area_name', name)

    def get_ats_route(self, name):
        return self._get_or_create(self.ats_route_cache, 'tbl_ATS_Routes', 'route_id', 'identifier', name)

    def get_procedure(self, name, type, ad_id, pt_id):
        """
        Get-or-create helper for Procedures. This one is more complex
        as it doesn't fit the simple get_or_create pattern.
        """
        if not name or pd.isna(name) or not ad_id:
            return None # Cannot create a procedure without a name and AD
        
        # A procedure is uniquely identified by its name, type, and aerodrome
        cache_key = (name, type, ad_id)
        if cache_key in self.procedure_cache:
            return self.procedure_cache[cache_key]

        # Use a real point ID if available, otherwise use a placeholder (e.g., -1)
        # This handles cases where a SID/STAR name (e.g., 'LOPIK2R') is given
        # but the en-route point ('LOPIK') isn't explicitly listed.
        db_point_id = pt_id if pt_id else -1 

        self.cursor.execute("""
            SELECT procedure_id FROM tbl_Procedures 
            WHERE procedure_name = ? AND procedure_type = ? AND aerodrome_id = ?
        """, (name, type, ad_id))
        row = self.cursor.fetchone()
        if row:
            proc_id = row[0]
        else:
            self.cursor.execute("""
                INSERT INTO tbl_Procedures (procedure_name, procedure_type, aerodrome_id, point_id)
                VALUES (?, ?, ?, ?)
            """, (name, type, ad_id, db_point_id))
            proc_id = self.cursor.lastrowid
        
        self.procedure_cache[cache_key] = proc_id
        return proc_id

    # --- CONDITION PALETTE (GET-OR-CREATE) HELPERS ---
    
    def get_cond_level(self, logic, lvl_1, lvl_2=None):
        try:
            lvl_1 = int(str(lvl_1).replace('FL', ''))
            lvl_2 = int(str(lvl_2).replace('FL', '')) if lvl_2 and pd.notna(lvl_2) else None
        except ValueError:
            return None # Invalid level format
            
        key = (logic, lvl_1, lvl_2)
        if key in self.cond_level_cache:
            return self.cond_level_cache[key]
        
        self.cursor.execute("INSERT OR IGNORE INTO tbl_Cond_Level (logic, level_1, level_2) VALUES (?, ?, ?)", key)
        self.cursor.execute("SELECT level_cond_id FROM tbl_Cond_Level WHERE logic = ? AND level_1 = ? AND (level_2 = ? OR (level_2 IS NULL AND ? IS NULL))", (logic, lvl_1, lvl_2, lvl_2))
        cond_id = self.cursor.fetchone()[0]
        self.cond_level_cache[key] = cond_id
        return cond_id

    def get_cond_time(self, days, start, end):
        if not start or pd.isna(start) or not end or pd.isna(end):
            return None
        start = str(start).strip()
        end = str(end).strip()
        days = str(days).strip()
        
        start = f"{start[:2]}:{start[2:]}" if len(start) == 4 else start
        end = f"{end[:2]}:{end[2:]}" if len(end) == 4 else end
        
        key = (days, start, end)
        if key in self.cond_time_cache:
            return self.cond_time_cache[key]
            
        self.cursor.execute("INSERT OR IGNORE INTO tbl_Cond_Time (availability_days, time_start, time_end) VALUES (?, ?, ?)", key)
        self.cursor.execute("SELECT time_cond_id FROM tbl_Cond_Time WHERE availability_days = ? AND time_start = ? AND time_end = ?", key)
        cond_id = self.cursor.fetchone()[0]
        self.cond_time_cache[key] = cond_id
        return cond_id

    def get_cond_flow(self, flow_type, logic, identifier):
        if not identifier or pd.isna(identifier):
            return None
        
        identifier = str(identifier).strip()
        ad_id, area_id, pt_id = None, None, None
        
        if len(identifier) == 4 and identifier.isalpha():
            ad_id = self.get_aerodrome(identifier)
        elif '_AD' in identifier or '_GROUP' in identifier:
            area_id = self.get_area(identifier)
        else:
            pt_id = self.get_point(identifier)
        
        key = (flow_type, logic, ad_id, area_id, pt_id)
        if key in self.cond_flow_cache:
            return self.cond_flow_cache[key]

        self.cursor.execute("INSERT OR IGNORE INTO tbl_Cond_Flow (flow_type, logic, aerodrome_id, area_id, point_id) VALUES (?, ?, ?, ?, ?)", key)
        self.cursor.execute("""
            SELECT flow_cond_id FROM tbl_Cond_Flow WHERE flow_type = ? AND logic = ? 
            AND (aerodrome_id = ? OR (aerodrome_id IS NULL AND ? IS NULL))
            AND (area_id = ? OR (area_id IS NULL AND ? IS NULL))
            AND (point_id = ? OR (point_id IS NULL AND ? IS NULL))
        """, (flow_type, logic, ad_id, ad_id, area_id, area_id, pt_id, pt_id))
        cond_id = self.cursor.fetchone()[0]
        self.cond_flow_cache[key] = cond_id
        return cond_id

    def get_cond_aircraft(self, logic, acft_type):
        key = (str(acft_type).strip(), str(logic).strip())
        if key in self.cond_aircraft_cache:
            return self.cond_aircraft_cache[key]
            
        self.cursor.execute("INSERT OR IGNORE INTO tbl_Cond_Aircraft (aircraft_type, logic) VALUES (?, ?)", key)
        self.cursor.execute("SELECT aircraft_cond_id FROM tbl_Cond_Aircraft WHERE aircraft_type = ? AND logic = ?", key)
        cond_id = self.cursor.fetchone()[0]
        self.cond_aircraft_cache[key] = cond_id
        return cond_id
        
    def get_cond_operational(self, logic, code):
        key = (str(code).strip(), str(logic).strip())
        if key in self.cond_op_cache:
            return self.cond_op_cache[key]
            
        self.cursor.execute("INSERT OR IGNORE INTO tbl_Cond_Operational (condition_code, logic) VALUES (?, ?)", key)
        self.cursor.execute("SELECT op_cond_id FROM tbl_Cond_Operational WHERE condition_code = ? AND logic = ?", key)
        cond_id = self.cursor.fetchone()[0]
        self.cond_op_cache[key] = cond_id
        return cond_id

    # --- CORE PARSING ENGINE ---

    def _parse_condition_string(self, cond_str):
        """
        Parses a raw RAD condition string into a list of condition IDs.
        Returns a dictionary of condition types and their corresponding IDs.
        """
        if not cond_str or pd.isna(cond_str):
            return {}

        conditions = {
            'level': [], 'time': [], 'flow': [], 'aircraft': [], 'operational': []
        }
        
        # Make string uppercase, replace newlines, and add space for easier regex
        rem_str = str(cond_str).upper().replace('\n', ' ').strip() + " "
        
        # Handle simple time-only strings
        time_only_match = re.fullmatch(r'(\d{4})-(\d{4})', rem_str.strip())
        if time_only_match:
            groups = time_only_match.groups()
            conditions['time'].append(self.get_cond_time('DLY', groups[0], groups[1]))
            return conditions
        if rem_str.strip() == 'H24':
            return {} # H24 is default, no condition needed

        while rem_str.strip():
            found_match = False
            for token_name, pattern in RAD_GRAMMAR:
                match = pattern.match(rem_str)
                if match:
                    found_match = True
                    groups = match.groups()
                    
                    try:
                        if token_name == 'LEVEL_BTN':
                            cond_id = self.get_cond_level('BETWEEN', groups[0], groups[1])
                            if cond_id: conditions['level'].append(cond_id)
                        elif token_name == 'LEVEL_ABV':
                            cond_id = self.get_cond_level('AT_OR_ABV', groups[1])
                            if cond_id: conditions['level'].append(cond_id)
                        elif token_name == 'LEVEL_BLW':
                            cond_id = self.get_cond_level('AT_OR_BLW', groups[1])
                            if cond_id: conditions['level'].append(cond_id)
                        elif token_name == 'TIME_DLY':
                            cond_id = self.get_cond_time('DLY', groups[0], groups[1])
                            if cond_id: conditions['time'].append(cond_id)
                        elif token_name == 'TIME_DAYS':
                            cond_id = self.get_cond_time(f"{groups[0]}-{groups[1]}", groups[2], groups[3])
                            if cond_id: conditions['time'].append(cond_id)
                        elif token_name == 'FLOW_ADEP':
                            cond_id = self.get_cond_flow('ADEP', groups[0], groups[1])
                            if cond_id: conditions['flow'].append(cond_id)
                        elif token_name == 'FLOW_ADES':
                            cond_id = self.get_cond_flow('ADES', groups[0], groups[1])
                            if cond_id: conditions['flow'].append(cond_id)
                        elif token_name in ('FLOW_ADEP_AREA', 'FLOW_ADES_AREA'):
                            flow_type = 'ADEP' if 'ADEP' in token_name else 'ADES'
                            cond_id = self.get_cond_flow(flow_type, groups[0], groups[1])
                            if cond_id: conditions['flow'].append(cond_id)
                        elif token_name == 'FLOW_VIA':
                            cond_id = self.get_cond_flow('VIA', groups[0], groups[2])
                            if cond_id: conditions['flow'].append(cond_id)
                        elif token_name == 'ACFT_TYPE':
                            cond_id = self.get_cond_aircraft(groups[0], groups[1])
                            if cond_id: conditions['aircraft'].append(cond_id)
                        elif token_name == 'OPERATIONAL':
                            cond_id = self.get_cond_operational(groups[0], groups[1])
                            if cond_id: conditions['operational'].append(cond_id)
                        elif token_name == 'FLT_TYPE':
                             cond_id = self.get_cond_operational('ONLY', 'FLT-TYPE (M)')
                             if cond_id: conditions['operational'].append(cond_id)
                    except Exception as e:
                        print(f"Warning: Could not parse token {token_name} with groups {groups}. Error: {e}")

                    # Consume the matched part of the string
                    rem_str = rem_str[match.end():].strip()
                    break  # Restart scanning from the beginning
            
            if not found_match and rem_str.strip():
                # Discard un-parsable tokens (like descriptions) and continue
                rem_str = rem_str[1:].strip() 
                
        return conditions

    def _load_conditions(self, rule_id, conditions, jct_prefix, rule_table_id_col):
        """
        Loads parsed condition IDs into the correct junction tables
        for a given rule_id.
        """
        if not conditions:
            return

        jct_table_map = {
            'level': 'Level', 'time': 'Time', 'flow': 'Flow',
            'aircraft': 'Aircraft', 'operational': 'Operational'
        }
        cond_id_col_map = {
            'level': 'level_cond_id', 'time': 'time_cond_id', 'flow': 'flow_cond_id',
            'aircraft': 'aircraft_cond_id', 'operational': 'op_cond_id'
        }

        for cond_type, cond_ids in conditions.items():
            if cond_ids:
                table_suffix = jct_table_map.get(cond_type)
                cond_id_col = cond_id_col_map.get(cond_type)
                if table_suffix:
                    jct_table = f"jct_{jct_prefix}_{table_suffix}"
                    for cond_id in cond_ids:
                        self.cursor.execute(f"INSERT OR IGNORE INTO {jct_table} ({rule_table_id_col}, {cond_id_col}) VALUES (?, ?)", (rule_id, cond_id))

    # --- ANNEX-SPECIFIC PARSERS ---

    def _read_csv(self, filename):
        """Helper to read CSV, clean headers, and return DataFrame."""
        try:
            # Use os.path.join to build the path correctly
            # Assumes CSVs are in the root, one level up from the script dir
            # script_dir = os.path.dirname(__file__)
            # root_dir = os.path.abspath(os.path.join(script_dir, '..'))
            # file_path = os.path.join(root_dir, filename)
            
            # Simplified: Assumes script is run from root, CSVs are in root.
            file_path = filename 
            
            df = pd.read_csv(file_path)
            df.columns = [self.clean_header(c) for c in df.columns]
            return df
        except FileNotFoundError:
            print(f"Warning: File not found: {filename}. Skipping.")
            return None
        except pd.errors.EmptyDataError:
            print(f"Warning: File is empty: {filename}. Skipping.")
            return None
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            return None

    def parse_annex_1(self):
        print("Parsing Annex 1 (Area Definitions)...")
        df = self._read_csv("Annex_1.csv")
        if df is None: return
        
        count = 0
        for _, row in df.iterrows():
            area_name = str(row['ID']).strip()
            area_id = self.get_area(area_name)
            
            definition_str = str(row['Definition'])
            # Find all 4-letter ICAO codes in the definition string
            icao_codes = re.findall(r'([A-Z]{4})', definition_str)
            
            for code in icao_codes:
                ad_id = self.get_aerodrome(code)
                if area_id and ad_id:
                    self.cursor.execute("INSERT OR IGNORE INTO jct_Area_Aerodromes (area_id, aerodrome_id) VALUES (?, ?)", (area_id, ad_id))
                    count += 1
        
        self.conn.commit()
        print(f"Processed {len(df)} areas, {count} aerodrome links in Annex 1.")
