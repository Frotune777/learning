import os

import pandas as pd

files = [
    "/media/fortune/Data/Python Project/learning/scratch/sample/Automated Stock Screener with BOH.xlsx",
    "/media/fortune/Data/Python Project/learning/scratch/sample/Buy Low Sell High Trading System With BOH.xlsx",
    "/media/fortune/Data/Python Project/learning/scratch/sample/Copy of DMADMA For Reverse Traders .xlsx",
    "/media/fortune/Data/Python Project/learning/scratch/sample/Copy of DMADMA For Without Stop Loss Traders .xlsx",
    "/media/fortune/Data/Python Project/learning/scratch/sample/Turtle Trading With BOH.xlsx",
]

for f in files:
    print(f"\n{'='*80}\nFILE: {os.path.basename(f)}\n{'='*80}")
    try:
        xl = pd.ExcelFile(f)
        print(f"Sheets: {xl.sheet_names}")
        for sheet in xl.sheet_names:
            print(f"\n--- Sheet: {sheet} ---")
            df = xl.parse(sheet, nrows=5)
            print(f"Columns: {list(df.columns)}")

            # Print first row to see sample data or formula text if available
            if not df.empty:
                print("Row 0:", df.iloc[0].to_dict())
    except Exception as e:
        print(f"Error parsing {f}: {e}")
