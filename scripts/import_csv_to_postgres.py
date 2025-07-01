import os
import glob
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, ForeignKey
from sqlalchemy.types import Integer, Float, String
from sqlalchemy.exc import ProgrammingError

# Connect to PostgreSQL
engine = create_engine('postgresql+psycopg2://postgres:postgres@localhost:5432/testdb')
metadata = MetaData()

# Find all CSV files
csv_files = glob.glob('**/*.csv', recursive=True)

tables = {}

# Step 1: Infer schema and create tables
for csv_file in csv_files:
    df = pd.read_csv(csv_file)
    table_name = os.path.splitext(os.path.basename(csv_file))[0].lower()
    columns = []

    # Infer column types
    for col in df.columns:
        dtype = df[col].dtype
        if 'int' in str(dtype):
            col_type = Integer
        elif 'float' in str(dtype):
            col_type = Float
        else:
            col_type = String(255)
        columns.append(Column(col, col_type))

    # Basic foreign key detection: columns ending with '_id'
    for col in df.columns:
        if col.endswith('_id'):
            ref_table = col[:-3]
            if ref_table in tables:
                columns.append(ForeignKey(f"{ref_table}.id"))

    table = Table(table_name, metadata, *columns, extend_existing=True)
    tables[table_name] = table

# Create tables
metadata.create_all(engine)

# Step 2: Import data
with engine.connect() as conn:
    for csv_file in csv_files:
        table_name = os.path.splitext(os.path.basename(csv_file))[0].lower()
        df = pd.read_csv(csv_file)
        df.to_sql(table_name, conn, if_exists='replace', index=False)

print("All CSVs imported successfully.")
