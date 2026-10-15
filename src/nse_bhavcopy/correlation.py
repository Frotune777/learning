"""
File: src/nse_bhavcopy/correlation.py
Purpose: Calculates and displays a correlation matrix for selected market instruments.
Last Modified: 2026-05-27
"""

import os

import pandas as pd


def run_correlation_cli(
    tickers: list[str] | None = None, period: str = "1y", hist_dir: str = "data/historical/1d"
) -> pd.DataFrame:
    """
    Loads historical data from local offline Parquet files and computes a correlation matrix.

    Parameters:
        tickers (list[str] | None): List of symbols to analyze.
        period (str): The data period (e.g., '6mo', '1y').
        hist_dir (str): Directory containing local parquet files.

    Returns:
        pd.DataFrame: A formatted correlation matrix DataFrame.
    """
    if tickers is None:
        tickers = ["NIFTYBEES", "BANKBEES", "GOLDBEES", "INFY.NS", "RELIANCE.NS"]

    prices_dict = {}
    rows_needed = 252 if period == "1y" else (126 if period == "6mo" else 252)

    for symbol in tickers:
        clean_sym = symbol.replace("^", "").replace(".NS", "")
        path = os.path.join(hist_dir, f"{clean_sym.upper()}.parquet")
        
        if not os.path.exists(path):
            print(f"Warning: Local data file not found for {symbol}")
            continue
            
        try:
            df = pd.read_parquet(path)
            if not df.empty:
                col_mapping = {c.lower(): c for c in df.columns}
                if 'close' in col_mapping:
                    close_col = col_mapping['close']
                    if not isinstance(df.index, pd.DatetimeIndex):
                        df.index = pd.to_datetime(df.index)
                    prices_dict[symbol] = df[close_col].tail(rows_needed)
        except Exception as e:
            print(f"Error reading {symbol}: {e}")

    if not prices_dict:
        print("No data found for the provided tickers.")
        return pd.DataFrame()

    prices = pd.DataFrame(prices_dict)

    # Calculate daily returns
    returns = prices.pct_change().dropna()

    # Correlation matrix
    corr_matrix = returns.corr()

    # Format the matrix as percentages for CLI display
    corr_formatted = corr_matrix.map(lambda x: f"{x * 100:.1f}%")

    # Add the ticker symbols as a standard column for Rich Table display
    corr_formatted.reset_index(inplace=True)
    corr_formatted = corr_formatted.rename(columns={"index": "Ticker"})

    return corr_formatted
