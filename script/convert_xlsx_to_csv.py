import pandas as pd
import os
from glob import glob

xlsx_files = glob('**/*.xlsx', recursive=True)

for xlsx in xlsx_files:
    basename = os.path.splitext(xlsx)[0]
    excel = pd.ExcelFile(xlsx)
    for sheet in excel.sheet_names:
        df = excel.parse(sheet)
        # Create unique CSV per worksheet
        csv_name = f"{basename}_{sheet}.csv"
        # Sanitize sheet name for filename
        csv_name = csv_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
        df.to_csv(csv_name, index=False)
        print(f"Converted {xlsx} [{sheet}] -> {csv_name}")
