# Understanding-RAD
The workspace to document everything needed to build a GPT based knowledge base for EuroControl RAD 

EuroControl RAD https://www.nm.eurocontrol.int/RAD/index.html
AIXM standard https://www.aixm.aero/

Action#1:
Generate a GitHub Actions workflow file (.github/workflows/convert.yml) that does the following on push:

Finds all .doc files in the repository and converts each to a .md file using pandoc.
Finds all .xlsx files in the repository and for each file, exports each worksheet as a separate .csv file using Python (with pandas).
The workflow should run on Ubuntu, and install all necessary dependencies (pandoc, python, pip, pandas, openpyxl).

Please include separate steps for each conversion process.

Action#2:
Generate a GitHub Actions workflow YAML file with the following requirements:

Trigger: On push or pull request to main branch
Environment: Use Ubuntu runner
Steps:
Check out the repository
Set up Python (latest version)
Install needed Python packages: pandas, psycopg2-binary, sqlalchemy, eralchemy, matplotlib
Set up PostgreSQL service with default user/password and database (e.g., user: postgres, password: postgres, db: testdb)
Find all .csv files in the repository (recursively)
For each .csv file:
Read with pandas
Infer the schema (columns and types)
Detect relationships by matching column names (e.g., “*_id” columns to primary keys in other tables)
Create the tables in PostgreSQL using SQLAlchemy, including foreign keys where inferred
Import the data from the CSV into the corresponding table
Export the final schema (as SQL) and save as an artifact
Generate an ER diagram (using eralchemy or similar), save as an artifact
Additional notes:

Use Python scripts for schema inference, table creation, and ER diagram generation.
Save the schema as schema.sql and the ER diagram as er_diagram.png in the workflow artifacts.
