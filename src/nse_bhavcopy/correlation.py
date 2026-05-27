"""
File: src/nse_bhavcopy/correlation.py
Purpose: Calculates and displays a correlation matrix for selected market instruments.
Last Modified: 2026-05-27
"""

from typing import Any

import pandas as pd
import yfinance as yf


def run_correlation_cli(
    tickers: list[str] | None = None, period: str = "1y"
) -> pd.DataFrame:
    """
    Downloads historical data and computes a correlation matrix.

    Parameters:
        tickers (list[str] | None): List of symbols to analyze.
        period (str): The data period (e.g., '6mo', '1y').

    Returns:
        pd.DataFrame: A formatted correlation matrix DataFrame.
    """
    if tickers is None:
        tickers = ["^NSEI", "INR=X", "^NSEBANK", "GOLD", "INFY.NS", "RELIANCE.NS"]

    try:
        data: Any = yf.download(
            tickers, period=period, auto_adjust=True, progress=False
        )
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

    if data.empty:
        print("No data found for the provided tickers.")
        return pd.DataFrame()

    # If multiple tickers, yfinance returns MultiIndex columns.
    # We want just the Close prices.
    if isinstance(data.columns, pd.MultiIndex):
        try:
            prices = data["Close"]
        except KeyError:
            print("Close price data missing from yfinance payload.")
            return pd.DataFrame()
    else:
        # Single ticker case
        prices = data[["Close"]]

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
