import os
from glob import glob
import openpyxl
import pandas as pd

def remove_strikethrough_text(ws):
    cleaned_data = []
    for row in ws.iter_rows():
        cleaned_row = []
        for cell in row:
            if cell.value is not None:
                # Check if cell has a font and if strikethrough is True
                if cell.font is not None and getattr(cell.font, 'strike', False):
                    cleaned_row.append('')
                else:
                    cleaned_row.append(cell.value)
            else:
                cleaned_row.append('')
        cleaned_data.append(cleaned_row)
    return cleaned_data

xlsx_files = glob('**/*.xlsx', recursive=True)

for xlsx in xlsx_files:
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        cleaned_data = remove_strikethrough_text(ws)
        # Convert to DataFrame
        df = pd.DataFrame(cleaned_data)
        # Build CSV file name
        basename = os.path.splitext(xlsx)[0]
        csv_name = f"{basename}_{sheet_name}.csv"
        csv_name = csv_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
        df.to_csv(csv_name, index=False, header=False)
        print(f"Converted {xlsx} [{sheet_name}] -> {csv_name}")
