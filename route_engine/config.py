import os

# Define base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Input Files
FRA_POINTS_FILE = os.path.join(BASE_DIR, 'download_11487', 'FRA_Points.csv')
ANNEX_3B_DCT_FILE = os.path.join(BASE_DIR, 'Annex_3B_DCT.csv')
ANNEX_3A_DEP_FILE = os.path.join(BASE_DIR, 'Annex_3A_DEP.csv')
ANNEX_3A_ARR_FILE = os.path.join(BASE_DIR, 'Annex_3A_ARR.csv')
ANNEX_2B_FILE = os.path.join(BASE_DIR, 'Annex_2B.csv')

# Defaults
DEFAULT_INTENDED_FL = 320
DEFAULT_FLOS_DIRECTION = 'EAST'
