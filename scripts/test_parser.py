#!/usr/bin/env python
#
# NAME: test_parser.py
# AUTH: RAD-Advisor
# DESC: Unit test suite for the RAD_ETL_Parser_CSV_v2

import unittest
import sqlite3
import pandas as pd
from unittest.mock import patch, MagicMock

# Import the class to be tested
# Assumes the parser is in a file named 'RAD_ETL_Parser_CSV_v2.py'
try:
    from RAD_ETL_Parser_CSV_v2 import RADParser
except ImportError:
    print("FATAL: Could not import RADParser from RAD_ETL_Parser_CSV_v2.py")
    print("Ensure the parser script is in the same directory.")
    exit(1)

class TestRADParser(unittest.TestCase):

    def setUp(self):
        """
        Set up a fresh, in-memory database for every single test.
        This ensures tests are isolated and do not interfere with each other.
        """
        self.db_path = ":memory:" # Use in-memory SQLite database
        self.parser = RADParser(db_path=self.db_path)
        # Manually create the schema for the in-memory DB
        self.parser._execute_schema()
        # Get a direct cursor for assertions
        self.cursor = self.parser.conn.cursor()

    def tearDown(self):
        """
        Close the database connection after each test.
        """
        self.parser.conn.close()

    # --- Test 1: Entity Resolution Helpers ---

    def test_get_or_create_point(self):
        """Tests that points are created once and retrieved correctly."""
        point_id_1 = self.parser.get_point("LOPIK")
        point_id_2 = self.parser.get_point("SUTAL")
        point_id_3 = self.parser.get_point("LOPIK") # Should be a cache/DB hit

        self.assertEqual(point_id_1, 1)
        self.assertEqual(point_id_2, 2)
        self.assertEqual(point_id_3, 1) # Must return the original ID

        # Verify against the database
        self.cursor.execute("SELECT COUNT(*) FROM tbl_Points")
        self.assertEqual(self.cursor.fetchone()[0], 2)

    def test_get_or_create_aerodrome(self):
        """Tests aerodrome creation and retrieval."""
        ad_id_1 = self.parser.get_aerodrome("EHAM")
        ad_id_2 = self.parser.get_aerodrome("LIRF")
        ad_id_3 = self.parser.get_aerodrome("EHAM")

        self.assertEqual(ad_id_1, 1)
        self.assertEqual(ad_id_2, 2)
        self.assertEqual(ad_id_3, 1)
        
        # Test invalid input
        invalid_ad = self.parser.get_aerodrome("INVALID")
        self.assertIsNone(invalid_ad)
        
        self.cursor.execute("SELECT COUNT(*) FROM tbl_Aerodromes")
        self.assertEqual(self.cursor.fetchone()[0], 2)

    # --- Test 2: Condition Palette Helpers ---

    def test_get_cond_level(self):
        """Tests creation of level conditions in the palette."""
        cond_id_1 = self.parser.get_cond_level("AT_OR_ABV", "FL285")
        cond_id_2 = self.parser.get_cond_level("BETWEEN", "FL200", "FL300")
        cond_id_3 = self.parser.get_cond_level("AT_OR_ABV", "FL285") # Cache hit

        self.assertEqual(cond_id_1, 1)
        self.assertEqual(cond_id_2, 2)
        self.assertEqual(cond_id_3, 1)

        # Verify DB content
        self.cursor.execute("SELECT logic, level_1, level_2 FROM tbl_Cond_Level WHERE level_cond_id = 2")
        self.assertEqual(self.cursor.fetchone(), ("BETWEEN", 200, 300))

    def test_get_cond_time(self):
        """Tests creation of time conditions in the palette."""
        cond_id_1 = self.parser.get_cond_time("DLY", "0600", "2200")
        
        # Verify DB content
        self.cursor.execute("SELECT availability_days, time_start, time_end FROM tbl_Cond_Time WHERE time_cond_id = 1")
        self.assertEqual(self.cursor.fetchone(), ("DLY", "06:00", "22:00"))

    def test_get_cond_flow(self):
        """Tests creation of flow conditions (ADEP/ADES)."""
        # Pre-load entities
        self.parser.get_aerodrome("EHAM")
        self.parser.get_area("TEST_GROUP")
        
        cond_id_1 = self.parser.get_cond_flow("ADEP", "ONLY", "EHAM")
        cond_id_2 = self.parser.get_cond_flow("ADES", "EXC", "TEST_GROUP")
        
        self.assertEqual(cond_id_1, 1)
        self.assertEqual(cond_id_2, 2)
        
        # Verify DB content
        self.cursor.execute("SELECT flow_type, logic, aerodrome_id, area_id FROM tbl_Cond_Flow WHERE flow_cond_id = 1")
        self.assertEqual(self.cursor.fetchone(), ("ADEP", "ONLY", 1, None)) # 1 is ID for EHAM
        
        self.cursor.execute("SELECT flow_type, logic, aerodrome_id, area_id FROM tbl_Cond_Flow WHERE flow_cond_id = 2")
        self.assertEqual(self.cursor.fetchone(), ("ADES", "EXC", None, 1)) # 1 is ID for TEST_GROUP

    # --- Test 3: Core Parser Engine ---

    def test_parse_condition_string_simple_level(self):
        """Tests parsing a single level string."""
        cond_str = "AT OR ABV FL285"
        conditions = self.parser._parse_condition_string(cond_str)
        
        self.assertIn('level', conditions)
        self.assertEqual(len(conditions['level']), 1)
        self.assertEqual(conditions['level'][0], 1) # It's the first condition
        
        self.cursor.execute("SELECT logic, level_1 FROM tbl_Cond_Level WHERE level_cond_id = 1")
        self.assertEqual(self.cursor.fetchone(), ("AT_OR_ABV", 285))

    def test_parse_condition_string_simple_time(self):
        """Tests parsing a simple time string (DLY)."""
        cond_str = "DLY 0600-2200"
        conditions = self.parser._parse_condition_string(cond_str)
        
        self.assertIn('time', conditions)
        self.assertEqual(len(conditions['time']), 1)
        self.assertEqual(conditions['time'][0], 1)

    def test_parse_condition_string_h24(self):
        """Tests that 'H24' and empty strings result in no conditions."""
        cond_h24 = self.parser._parse_condition_string("H24")
        cond_none = self.parser._parse_condition_string(None)
        cond_nan = self.parser._parse_condition_string(pd.NA)
        cond_empty = self.parser._parse_condition_string(" ")
        
        self.assertEqual(len(cond_h24), 0)
        self.assertEqual(len(cond_none), 0)
        self.assertEqual(len(cond_nan), 0)
        self.assertEqual(len(cond_empty), 0)

    def test_parse_condition_string_complex(self):
        """Tests parsing a complex, multi-token string."""
        # Pre-load the aerodrome entity
        self.parser.get_aerodrome("EHAM")
        
        cond_str = "ONLY ADEP EHAM AT OR ABV FL300 DLY 0800-1600 EXC ACFT TYPE A320 EXC OAT"
        conditions = self.parser._parse_condition_string(cond_str)
        
        # Check that all categories were populated
        self.assertEqual(len(conditions['flow']), 1)
        self.assertEqual(len(conditions['level']), 1)
        self.assertEqual(len(conditions['time']), 1)
        self.assertEqual(len(conditions['aircraft']), 1)
        self.assertEqual(len(conditions['operational']), 1)

        # Check the database values
        self.cursor.execute("SELECT logic, level_1 FROM tbl_Cond_Level")
        self.assertEqual(self.cursor.fetchone(), ("AT_OR_ABV", 300))

        self.cursor.execute("SELECT time_start, time_end FROM tbl_Cond_Time")
        self.assertEqual(self.cursor.fetchone(), ("08:00", "16:00"))
        
        self.cursor.execute("SELECT aircraft_type, logic FROM tbl_Cond_Aircraft")
        self.assertEqual(self.cursor.fetchone(), ("A320", "EXC"))
        
        self.cursor.execute("SELECT condition_code, logic FROM tbl_Cond_Operational")
        self.assertEqual(self.cursor.fetchone(), ("OAT", "EXC"))

        self.cursor.execute("SELECT flow_type, logic, aerodrome_id FROM tbl_Cond_Flow")
        self.assertEqual(self.cursor.fetchone(), ("ADEP", "ONLY", 1)) # 1 is ID for EHAM
        
    def test_parse_condition_string_with_newlines_and_garbage(self):
        """Tests robustness to messy strings."""
        cond_str = "ONLY TFC VIA KOKSY \nTHIS IS A REMARK NOT TO BE PARSED\n ABV FL195"
        conditions = self.parser._parse_condition_string(cond_str)

        self.assertEqual(len(conditions['flow']), 1)
        self.assertEqual(len(conditions['level']), 1)
        
        self.cursor.execute("SELECT logic, level_1 FROM tbl_Cond_Level")
        self.assertEqual(self.cursor.fetchone(), ("AT_OR_ABV", 195))
        
        self.cursor.execute("SELECT flow_type, logic, point_id FROM tbl_Cond_Flow")
        self.assertEqual(self.cursor.fetchone(), ("VIA", "ONLY", 1)) # 1 is ID for KOKSY

    # --- Test 4: High-Level Annex Parsers (Integration) ---

    @patch('pandas.read_csv')
    def test_parse_annex_1(self, mock_read_csv):
        """Tests the Annex 1 parser logic."""
        # 1. Setup mock data
        mock_data = {
            "ID": ["AMSTERDAM_GROUP", "ROME_GROUP"],
            "Definition": ["(EHAM, EHBK)", "(LIRF)"]
        }
        mock_df = pd.DataFrame(mock_data)
        mock_read_csv.return_value = mock_df
        
        # 2. Action
        self.parser.parse_annex_1()
        
        # 3. Assert
        self.cursor.execute("SELECT area_name FROM tbl_Areas_Annex1")
        self.assertEqual(len(self.cursor.fetchall()), 2)
        
        self.cursor.execute("SELECT icao_code FROM tbl_Aerodromes")
        self.assertEqual(len(self.cursor.fetchall()), 3) # EHAM, EHBK, LIRF
        
        self.cursor.execute("SELECT COUNT(*) FROM jct_Area_Aerodromes")
        self.assertEqual(self.cursor.fetchone()[0], 3) # 3 links total
        
        # Check one link specifically
        self.cursor.execute("""
            SELECT T1.area_name, T3.icao_code
            FROM tbl_Areas_Annex1 AS T1
            JOIN jct_Area_Aerodromes AS T2 ON T1.area_id = T2.area_id
            JOIN tbl_Aerodromes AS T3 ON T2.aerodrome_id = T3.aerodrome_id
            WHERE T1.area_name = 'AMSTERDAM_GROUP' AND T3.icao_code = 'EHAM'
        """)
        self.assertIsNotNone(self.cursor.fetchone())

    @patch('pandas.read_csv')
    def test_parse_annex_3b_dct(self, mock_read_csv):
        """Tests the Annex 3B DCT parser and its linking."""
        # 1. Setup mock data
        mock_data = {
            "ID": ["TEST_DCT_01"],
            "From": ["POINTA"],
            "To": ["POINTB"],
            "Lower Vert. Limit (FL)": ["FL245"],
            "Upper Vert. Limit (FL)": [pd.NA],
            "Available or Not (Y/N)": ["Yes"],
            "Utilization": ["ONLY AVBL FOR TFC ARR EDDV"],
            "Time Availability": ["0600-2200"],
            "Remarks": ["Test remark"]
        }
        mock_df = pd.DataFrame(mock_data)
        mock_read_csv.return_value = mock_df # Mock Annex_3B_DCT.csv
        
        # Pre-load the 'EDDV' aerodrome so the flow condition can be created
        self.parser.get_aerodrome("EDDV")
        
        # 2. Action
        # We call the main 3B parser, but only the DCT file will be "found"
        with patch.object(self.parser, '_read_csv') as mock_read_helper:
            mock_read_helper.side_effect = [
                mock_df, # Return mock for Annex_3B_DCT.csv
                None     # Return None for Annex_3B_FRA_LIM.csv
            ]
            self.parser.parse_annex_3b()

        # 3. Assert
        # Check that the main rule was created
        self.cursor.execute("SELECT rule_identifier, availability, from_point_id, to_point_id FROM tbl_Rules_Annex3B")
        rule = self.cursor.fetchone()
        self.assertIsNotNone(rule)
        self.assertEqual(rule[0], "TEST_DCT_01")
        self.assertEqual(rule[1], "AVBL")
        
        rule_id = 1
        
        # Check Level Condition Link
        self.cursor.execute("SELECT level_cond_id FROM jct_Annex3B_Level WHERE rule_id = ?", (rule_id,))
        level_cond_id = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT logic, level_1 FROM tbl_Cond_Level WHERE level_cond_id = ?", (level_cond_id,))
        self.assertEqual(self.cursor.fetchone(), ("AT_OR_ABV", 245))

        # Check Time Condition Link
        self.cursor.execute("SELECT time_cond_id FROM jct_Annex3B_Time WHERE rule_id = ?", (rule_id,))
        time_cond_id = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT availability_days, time_start, time_end FROM tbl_Cond_Time WHERE time_cond_id = ?", (time_cond_id,))
        self.assertEqual(self.cursor.fetchone(), ("DLY", "06:00", "22:00"))
        
        # Check Flow Condition Link
        self.cursor.execute("SELECT flow_cond_id FROM jct_Annex3B_Flow WHERE rule_id = ?", (rule_id,))
        flow_cond_id = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT flow_type, logic, aerodrome_id FROM tbl_Cond_Flow WHERE flow_cond_id = ?", (flow_cond_id,))
        self.assertEqual(self.cursor.fetchone(), ("ADES", "ONLY", 1)) # 1 is ID for EDDV


if __name__ == '__main__':
    print("Running RAD Parser Unit Tests...\n")
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
