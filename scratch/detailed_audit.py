"""
File: scratch/detailed_audit.py
Purpose: Get precise tickers/dates for nulls, extreme returns, and date ranges.

Dependencies:
    External:
        - pandas>=2.2.3: DataFrame time-series calculations
        - numpy>=2.4.6: Numerical calculations

Last Modified: 2026-06-17
Modified By: Fortune
"""

import glob
import os

import pandas as pd


def run_detailed_audit() -> None:
    parquet_files = glob.glob("data/historical/1d/*.parquet")

    null_rows = []
    extreme_returns = []
    date_ranges = []

    for file_path in parquet_files:
        ticker = os.path.basename(file_path).replace(".parquet", "")
        df = pd.read_parquet(file_path)
        if df.empty:
            continue

        # Check nulls
        null_mask = df.isna().any(axis=1)
        if null_mask.any():
            for idx in df[null_mask].index:
                null_rows.append((ticker, str(idx)))

        # Check extreme returns (>50%)
        if "Close" in df.columns:
            pct = df["Close"].pct_change()
            extreme_mask = pct.abs() > 0.50
            if extreme_mask.any():
                for idx, val in pct[extreme_mask].items():
                    extreme_returns.append((ticker, str(idx), float(val)))

        # Date range
        date_ranges.append((ticker, df.index.min(), df.index.max(), len(df)))

    print(f"Total null rows found: {len(null_rows)}")
    print("Null rows sample:")
    for nr in null_rows[:15]:
        print(f"  Ticker: {nr[0]}, Date: {nr[1]}")

    print(f"\nTotal extreme returns found: {len(extreme_returns)}")
    for er in extreme_returns:
        print(f"  Ticker: {er[0]}, Date: {er[1]}, Return: {er[2]:.2%}")

    df_ranges = pd.DataFrame(
        date_ranges, columns=["Ticker", "MinDate", "MaxDate", "Length"]
    )
    print("\nDate range summary:")
    print(f"  Overall Min Date: {df_ranges['MinDate'].min()}")
    print(f"  Overall Max Date: {df_ranges['MaxDate'].max()}")
    print(f"  Average history length: {df_ranges['Length'].mean():.1f} days")
    print(f"  Shortest history length: {df_ranges['Length'].min()} days")
    print(f"  Longest history length: {df_ranges['Length'].max()} days")


if __name__ == "__main__":
    run_detailed_audit()
