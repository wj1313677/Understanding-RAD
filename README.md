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
