import pandas as pd

f = "/media/fortune/Data/Python Project/learning/scratch/sample/OV Proven & Tested methods & Strategies .xlsx"
print(f"\n{'='*80}\nFILE: {f}\n{'='*80}")
try:
    xl = pd.ExcelFile(f)
    print(f"Sheets: {xl.sheet_names}")
    for sheet in xl.sheet_names:
        print(f"\n--- Sheet: {sheet} ---")
        df = xl.parse(sheet, nrows=5)
        print(f"Columns: {list(df.columns)}")
        if not df.empty:
            print("Row 0:", df.iloc[0].to_dict())
except Exception as e:
    print(f"Error: {e}")
