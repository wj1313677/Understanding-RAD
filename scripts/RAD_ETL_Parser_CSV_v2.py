#!/usr/bin/env python
#
# NAME: RAD_ETL_Parser_CSV_v2.py
# AUTH: RAD-Advisor
# DESC: Parses a set of 9 RAD CSV files and loads them into a normalized 
#       SQLite database for FPL validation.

import sqlite3
import pandas as pd
import re
import sys
import glob

# --- REGEX DEFINITIONS FOR RAD CONDITIONAL GRAMMAR ---
# This list of tuples (token_name, regex_pattern) defines the RAD DSL.
# It is used by the _parse_condition_string method.
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
    ('FLT_TYPE', re.compile(r'FLT-TYPE \((M)\)')), # Specific case for some rules
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
        # This schema is normalized and unchanged from the previous design.
        # It is robust and supports all Annex rules.
        schema = """
        PRAGMA foreign_keys = ON; -- Enforce foreign key constraints

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
        CREATE TABLE IF NOT EXISTS jct_Annex3A_Conn_Time (conn_rule_id INTEGER NOT NULL, time_cond_id INTEGER NOT NULL, PRIMARY KEY(conn_rule_id, time_cond_id), FOREIGN KEY (conn_rule_id) REFERENCES tbl_Rules_Annex3A_Connectivity(conn_rule_id), FOREIGN KEY (time_cond_id) REFERENCES tbl_Cond_Time(time_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex3A_Cond_Level (cond_rule_id INTEGER NOT NULL, level_cond_id INTEGER NOT NULL, PRIMARY KEY(cond_rule_id, level_cond_id), FOREIGN KEY (cond_rule_id) REFERENCES tbl_Rules_Annex3A_Conditions(cond_rule_id), FOREIGN KEY (level_cond_id) REFERENCES tbl_Cond_Level(level_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex3A_Conn_Level (conn_rule_id INTEGER NOT NULL, level_cond_id INTEGER NOT NULL, PRIMARY KEY(conn_rule_id, level_cond_id), FOREIGN KEY (conn_rule_id) REFERENCES tbl_Rules_Annex3A_Connectivity(conn_rule_id), FOREIGN KEY (level_cond_id) REFERENCES tbl_Cond_Level(level_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex3A_Conn_Operational (conn_rule_id INTEGER NOT NULL, op_cond_id INTEGER NOT NULL, PRIMARY KEY(conn_rule_id, op_cond_id), FOREIGN KEY (conn_rule_id) REFERENCES tbl_Rules_Annex3A_Connectivity(conn_rule_id), FOREIGN KEY (op_cond_id) REFERENCES tbl_Cond_Operational(op_cond_id));
        CREATE TABLE IF NOT EXISTS jct_Annex3A_Conn_Flow (conn_rule_id INTEGER NOT NULL, flow_cond_id INTEGER NOT NULL, PRIMARY KEY(conn_rule_id, flow_cond_id), FOREIGN KEY (conn_rule_id) REFERENCES tbl_Rules_Annex3A_Connectivity(conn_rule_id), FOREIGN KEY (flow_cond_id) REFERENCES tbl_Cond_Flow(flow_cond_id));

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
    
    def _get_or_create(self, cache, table, key_col, key_val):
        """Generic helper to get or create an entity ID."""
        if not key_val or pd.isna(key_val):
            return None
        key_val = str(key_val).strip()
        if key_val in cache:
            return cache[key_val]
        
        self.cursor.execute(f"SELECT {key_col}_id FROM {table} WHERE {key_col} = ?", (key_val,))
        row = self.cursor.fetchone()
        if row:
            entity_id = row[0]
        else:
            self.cursor.execute(f"INSERT INTO {table} ({key_col}) VALUES (?)", (key_val,))
            entity_id = self.cursor.lastrowid
        
        cache[key_val] = entity_id
        return entity_id

    def get_point(self, name):
        return self._get_or_create(self.point_cache, 'tbl_Points', 'identifier', name)
    
    def get_aerodrome(self, icao):
        if not icao or pd.isna(icao) or len(str(icao).strip()) != 4:
            return None
        return self._get_or_create(self.aerodrome_cache, 'tbl_Aerodromes', 'icao_code', icao)
        
    def get_area(self, name):
        return self._get_or_create(self.area_cache, 'tbl_Areas_Annex1', 'area_name', name)

    def get_ats_route(self, name):
        return self._get_or_create(self.ats_route_cache, 'tbl_ATS_Routes', 'identifier', name)

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
        
        # Format time if it's 0600
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
        if re.fullmatch(r'(\d{4})-(\d{4})', rem_str.strip()):
            groups = re.match(r'(\d{4})-(\d{4})', rem_str.strip()).groups()
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
            df = pd.read_csv(filename)
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

    def parse_annex_2a(self):
        print("Parsing Annex 2A (Flight Level Capping)...")
        df = self._read_csv("Annex_2A.csv")
        if df is None: return

        for _, row in df.iterrows():
            adep_str = str(row['From (ADEP)']).strip()
            ades_str = str(row['To (ADES)']).strip()
            
            adep_id, adep_area_id = (self.get_aerodrome(adep_str), None) if len(adep_str) == 4 else (None, self.get_area(adep_str))
            ades_id, ades_area_id = (self.get_aerodrome(ades_str), None) if len(ades_str) == 4 else (None, self.get_area(ades_str))
            
            max_fl_str = str(row['Flight Level Capping'])
            max_fl = int(re.search(r'FL(\d{3})', max_fl_str).group(1)) if 'FL' in max_fl_str else 0

            self.cursor.execute("""
                INSERT OR IGNORE INTO tbl_Rules_Annex2A 
                (rule_identifier, adep_aerodrome_id, adep_area_id, ades_aerodrome_id, ades_area_id, max_flight_level, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (row['ID'], adep_id, adep_area_id, ades_id, ades_area_id, max_fl, row['Remarks']))
            
            rule_id = self.cursor.lastrowid
            if rule_id == 0: # Rule already existed
                self.cursor.execute("SELECT rule_id FROM tbl_Rules_Annex2A WHERE rule_identifier = ?", (row['ID'],))
                rule_id = self.cursor.fetchone()[0]

            # Combine 'Condition' and 'Time Applicability' for parsing
            cond_str = str(row['Condition'])
            time_str = str(row['Time Applicability'])
            full_cond_str = f"{cond_str} {time_str}" if time_str != 'H24' else cond_str

            conditions = self._parse_condition_string(full_cond_str)
            self._load_conditions(rule_id, conditions, 'Annex2A', 'rule_id')

        self.conn.commit()
        print(f"Processed {len(df)} Annex 2A rules.")

    def parse_annex_2b(self):
        print("Parsing Annex 2B (En-route Structural)...")
        df = self._read_csv("Annex_2B.csv")
        if df is None: return

        for _, row in df.iterrows():
            route_id = self.get_ats_route(row['Airway'])
            from_id = self.get_point(row['From'])
            to_id = self.get_point(row['To'])
            point_id = self.get_point(row['Point or Airspace'])
            
            util_str = str(row['Utilization']).upper()
            if 'COMPULSORY' in util_str:
                availability = 'COMPULSORY'
            elif 'NOT AVBL' in util_str:
                availability = 'NOT AVBL'
            else:
                availability = 'AVBL'

            self.cursor.execute("""
                INSERT OR IGNORE INTO tbl_Rules_Annex2B 
                (rule_identifier, ats_route_id, from_point_id, to_point_id, point_or_airspace_id, availability, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (row['ID'], route_id, from_id, to_id, point_id, availability, row['Remarks']))
            
            rule_id = self.cursor.lastrowid
            if rule_id == 0:
                self.cursor.execute("SELECT rule_id FROM tbl_Rules_Annex2B WHERE rule_identifier = ?", (row['ID'],))
                rule_id = self.cursor.fetchone()[0]
            
            time_str = str(row['Time Applicability'])
            full_cond_str = f"{util_str} {time_str}" if time_str != 'H24' else util_str
            
            conditions = self._parse_condition_string(full_cond_str)
            self._load_conditions(rule_id, conditions, 'Annex2B', 'rule_id')

        self.conn.commit()
        print(f"Processed {len(df)} Annex 2B rules.")

    def parse_annex_2c(self):
        print("Parsing Annex 2C (FUA / AUP-UUP)...")
        df = self._read_csv("Annex_2C.csv")
        if df is None: return

        for _, row in df.iterrows():
            self.cursor.execute("""
                INSERT OR IGNORE INTO tbl_Rules_Annex2C
                (rule_identifier, airspace_name, description)
                VALUES (?, ?, ?)
            """, (row['ID'], row['AIP RSA ID'], row['Remarks']))
            
            rule_id = self.cursor.lastrowid
            if rule_id == 0:
                self.cursor.execute("SELECT rule_id FROM tbl_Rules_Annex2C WHERE rule_identifier = ?", (row['ID'],))
                rule_id = self.cursor.fetchone()[0]
                
            cond_str = str(row['Traffic Flow Rule applied during times and within vertical limits allocated at EAUP/EUUP'])
            conditions = self._parse_condition_string(cond_str)
            self._load_conditions(rule_id, conditions, 'Annex2C', 'rule_id')
        
        self.conn.commit()
        print(f"Processed {len(df)} Annex 2C rules.")
        
    def parse_annex_3a(self):
        print("Parsing Annex 3A (Aerodrome Connectivity)...")
        
        # --- Parse DEP ---
        df_dep = self._read_csv("Annex_3A_DEP.csv")
        if df_dep is not None:
            for _, row in df_dep.iterrows():
                ad_id = self.get_aerodrome(row['DEP AD'])
                proc_name = str(row['Last PT SID / SID ID'])
                pt_name = str(row['DCT DEP PT'])
                
                en_route_point_id = self.get_point(pt_name) if pd.notna(pt_name) else self.get_point(proc_name)
                
                self.cursor.execute("""
                    INSERT OR IGNORE INTO tbl_Rules_Annex3A_Connectivity
                    (rule_identifier, aerodrome_id, rule_type, en_route_point_id, required_procedure_name)
                    VALUES (?, ?, 'DEP', ?, ?)
                """, (row['DEP ID'], ad_id, en_route_point_id, proc_name if pd.notna(proc_name) else None))

                rule_id = self.cursor.lastrowid
                if rule_id == 0:
                    self.cursor.execute("SELECT conn_rule_id FROM tbl_Rules_Annex3A_Connectivity WHERE rule_identifier = ?", (row['DEP ID'],))
                    rule_id = self.cursor.fetchone()[0]

                time_str = str(row['DEP Time Applicability'])
                cond_str = str(row['DEP FPL Options'])
                full_cond_str = f"{cond_str} {time_str}" if time_str != 'H24' else cond_str
                
                conditions = self._parse_condition_string(full_cond_str)
                self._load_conditions(rule_id, conditions, 'Annex3A_Conn', 'conn_rule_id')
            print(f"Processed {len(df_dep)} Annex 3A-DEP rules.")

        # --- Parse ARR ---
        df_arr = self._read_csv("Annex_3A_ARR.csv")
        if df_arr is not None:
            for _, row in df_arr.iterrows():
                ad_id = self.get_aerodrome(row['ARR AD'])
                proc_name = str(row['First PT STAR / STAR ID'])
                pt_name = str(row['DCT ARR PT'])
                
                en_route_point_id = self.get_point(pt_name) if pd.notna(pt_name) else self.get_point(proc_name)

                self.cursor.execute("""
                    INSERT OR IGNORE INTO tbl_Rules_Annex3A_Connectivity
                    (rule_identifier, aerodrome_id, rule_type, en_route_point_id, required_procedure_name)
                    VALUES (?, ?, 'ARR', ?, ?)
                """, (row['ARR ID'], ad_id, en_route_point_id, proc_name if pd.notna(proc_name) else None))

                rule_id = self.cursor.lastrowid
                if rule_id == 0:
                    self.cursor.execute("SELECT conn_rule_id FROM tbl_Rules_Annex3A_Connectivity WHERE rule_identifier = ?", (row['ARR ID'],))
                    rule_id = self.cursor.fetchone()[0]

                time_str = str(row['ARR Time Applicability'])
                cond_str = str(row['ARR FPL Option'])
                full_cond_str = f"{cond_str} {time_str}" if time_str != 'H24' else cond_str
                
                conditions = self._parse_condition_string(full_cond_str)
                self._load_conditions(rule_id, conditions, 'Annex3A_Conn', 'conn_rule_id')
            print(f"Processed {len(df_arr)} Annex 3A-ARR rules.")

        # --- Parse Conditions (The complex ones) ---
        df_cond = self._read_csv("Annex_3A_Conditions.csv")
        if df_cond is not None:
            for _, row in df_cond.iterrows():
                # Extract the 2-letter country code (e.g., 'LG' from 'LG_LIM_AD')
                nas_fab = str(row['NAS / FAB']).strip()
                ad_id = None # This rule applies to an area, not one AD
                
                self.cursor.execute("""
                    INSERT OR IGNORE INTO tbl_Rules_Annex3A_Conditions
                    (rule_identifier, condition_type, value, description)
                    VALUES (?, ?, ?, ?)
                """, (row['RAD Application ID'], row['Condition'], row['Explanation'], row['Condition']))
            print(f"Processed {len(df_cond)} Annex 3A-COND rules.")

        self.conn.commit()

    def parse_annex_3b(self):
        print("Parsing Annex 3B (En-route DCT & FRA)...")
        
        # --- Parse DCT ---
        df_dct = self._read_csv("Annex_3B_DCT.csv")
        if df_dct is not None:
            for _, row in df_dct.iterrows():
                from_id = self.get_point(row['From'])
                to_id = self.get_point(row['To'])
                
                if not from_id or not to_id:
                    print(f"Skipping rule {row['ID']} due to missing point.")
                    continue
                    
                availability = 'AVBL' if str(row['Available or Not (Y/N)']).strip().lower() == 'yes' else 'NOT AVBL'
                
                self.cursor.execute("""
                    INSERT OR IGNORE INTO tbl_Rules_Annex3B
                    (rule_identifier, from_point_id, to_point_id, availability, rule_type, description)
                    VALUES (?, ?, ?, ?, 'DCT', ?)
                """, (row['ID'], from_id, to_id, availability, row['Remarks']))
                
                rule_id = self.cursor.lastrowid
                if rule_id == 0:
                    self.cursor.execute("SELECT rule_id FROM tbl_Rules_Annex3B WHERE rule_identifier = ?", (row['ID'],))
                    rule_id = self.cursor.fetchone()[0]
                
                # Manually build condition string from multiple columns
                cond_str = str(row['Utilization'])
                time_str = str(row['Time Availability'])
                
                level_cond = ""
                lower_fl = row['Lower Vert. Limit (FL)']
                upper_fl = row['Upper Vert. Limit (FL)']
                
                if pd.notna(lower_fl) and pd.notna(upper_fl):
                    level_cond = f"BTN {lower_fl} AND {upper_fl}"
                elif pd.notna(lower_fl):
                    level_cond = f"AT OR ABV {lower_fl}"
                elif pd.notna(upper_fl):
                    level_cond = f"AT OR BLW {upper_fl}"

                full_cond_str = f"{cond_str} {time_str if time_str != 'H24' else ''} {level_cond}"
                
                conditions = self._parse_condition_string(full_cond_str)
                self._load_conditions(rule_id, conditions, 'Annex3B', 'rule_id')
            print(f"Processed {len(df_dct)} Annex 3B-DCT rules.")

        # --- Parse FRA_LIM (Loading as 3A-Conditions) ---
        df_fra = self._read_csv("Annex_3B_FRA_LIM.csv")
        if df_fra is not None:
            for _, row in df_fra.iterrows():
                area_id = self.get_area(row['Airspace']) # This is an airspace, not an AD
                
                self.cursor.execute("""
                    INSERT OR IGNORE INTO tbl_Rules_Annex3A_Conditions
                    (rule_identifier, area_id, applicability, condition_type, value, description)
                    VALUES (?, ?, 'GENERAL', 'FRA LIM', ?, ?)
                """, (row['RAD Application ID'], area_id, row['DCT Horiz. Limit'], row['Remarks']))
            print(f"Processed {len(df_fra)} Annex 3B-FRA_LIM rules.")

        self.conn.commit()

    def run_all(self):
        """Runs the full ETL process in the correct order."""
        self._execute_schema()
        
        # --- Run Parsers ---
        # Prerequisites must run first
        self.parse_annex_1() 
        
        # Core rules
        self.parse_annex_2a()
        self.parse_annex_2b()
        self.parse_annex_2c()
        self.parse_annex_3a() # This now handles DEP, ARR, and COND
        self.parse_annex_3b() # This now handles DCT and FRA_LIM
        
        print("\n" + "="*80)
        print(f"--- RAD Database Load Complete ---")
        print(f"Database file is located at: {self.db_path}")
        print("="*80)
        self.conn.close()


if __name__ == "__main__":
    # --- CONFIGURATION ---
    # The script expects the 9 CSV files to be in the same directory.
    DATABASE_FILE = "rad_master.db"
    
    print(f"Starting RAD CSV Parser...")
    
    try:
        parser = RADParser(db_path=DATABASE_FILE)
        parser.run_all()
    except Exception as e:
        print(f"\n--- A FATAL ERROR OCCURRED ---")
        print(f"Error: {e}")
        sys.exit(1)
