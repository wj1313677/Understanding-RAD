"""
Update database configuration to use environment variables
This allows the same code to work in Docker and local environments
"""

import os
from dotenv import load_dotenv

# Load .env file if it exists (for local development)
load_dotenv()

# PostgreSQL connection settings
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'route_restrictions'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
}

# File paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ANNEX_FILES = {
    'Annex_1': os.path.join(BASE_DIR, 'Annex_1.csv'),
    'Annex_2A': os.path.join(BASE_DIR, 'Annex_2A.csv'),
    'Annex_2B': os.path.join(BASE_DIR, 'Annex_2B.csv'),
    'Annex_2C': os.path.join(BASE_DIR, 'Annex_2C.csv'),
    'Annex_3A_ARR': os.path.join(BASE_DIR, 'Annex_3A_ARR.csv'),
    'Annex_3A_Conditions': os.path.join(BASE_DIR, 'Annex_3A_Conditions.csv'),
    'Annex_3A_DEP': os.path.join(BASE_DIR, 'Annex_3A_DEP.csv'),
    'Annex_3B_DCT': os.path.join(BASE_DIR, 'Annex_3B_DCT.csv'),
    'Annex_3B_FRA_LIM': os.path.join(BASE_DIR, 'Annex_3B_FRA_LIM.csv'),
}

FRA_POINTS_FILE = os.path.join(BASE_DIR, 'download_11487', 'FRA_Points.csv')
