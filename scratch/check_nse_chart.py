"""
File: scratch/check_nse_chart.py
Purpose: Scratch script to verify live NSE Charting API warm-up and retrieval.

Dependencies:
External:
- pandas>=2.2.3: Data manipulation
Internal:
- src.data.fetcher.prices.nse_charts: Authoritative chart fetcher module

Key Components:
Classes:
- None
Functions:
- check_nse: Warm up and query RELIANCE chart data.

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- None

Related Files:
- src/data/fetcher/prices/nse_charts.py: Target charting engine.
"""

from src.data.fetcher.prices.nse_charts import NSEChartFetcher
from src.data.fetcher.session.manager import SessionManager
from src.data.fetcher.session.nse_session import NSESessionInitializer
from src.data.fetcher.symbols.resolver import SymbolResolver


def check_nse() -> None:
    """
    Perform cookie warm-up and fetch live chart data for RELIANCE from NSE Charting API.

    Logic:
        Step 1: Initialize session manager, nse session warmup, and resolver.
        Step 2: Query 5 days of history for RELIANCE.
        Step 3: Print result head if successful.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> check_nse()
    """
    print("Initializing NSE Charting API components...")
    try:
        session_manager = SessionManager()
        nse_initializer = NSESessionInitializer(session_manager)
        symbol_resolver = SymbolResolver()
        fetcher = NSEChartFetcher(session_manager, nse_initializer, symbol_resolver)

        print("Fetching RELIANCE (token 2885) historical data from NSE Charting API...")
        df = fetcher.fetch(symbol="RELIANCE", period="1y")

        if df.empty:
            print("FAILED: NSE Charting API returned empty DataFrame.")
        else:
            print("SUCCESS: NSE Charting API successfully fetched data:")
            print(df)
    except Exception as e:
        print(f"FAILED: An error occurred during NSE Charting fetch: {e}")


if __name__ == "__main__":
    check_nse()
