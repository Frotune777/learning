"""
File: check_data_sources.py
Purpose: Utility to check availability and health of all data sources.

Dependencies:
External:
- pandas>=2.2.3: Used for structuring verified dataframes
- yfinance>=0.2.52: Yahoo Finance market data API
Internal:
- src.nse_bhavcopy.downloader: [BhavcopyDownloader]
- src.data.fetcher.prices.nse_charts: [NSEChartFetcher]
- src.data.fetcher.session.manager: [SessionManager]
- src.data.fetcher.session.nse_session: [NSESessionInitializer]
- src.data.fetcher.symbols.resolver: [SymbolResolver]

Key Components:
Classes:
- None
Functions:
- check_yfinance: Verify yfinance API connection and download success.
- check_nse_charts: Verify official NSE Charting API fetcher operations.
- check_bhavcopy: Verify NSE CM Bhavcopy archive downloader.
- main: Orchestrate the diagnostic sequence across all data sources.

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- None

Related Files:
- src/nse_bhavcopy/downloader.py: Core downloading module.
- src/data/fetcher/prices/nse_charts.py: High-resolution NSE charting fetcher.
"""

import logging
import sys
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from src.data.fetcher.prices.nse_charts import NSEChartFetcher
from src.data.fetcher.session.manager import SessionManager
from src.data.fetcher.session.nse_session import NSESessionInitializer
from src.data.fetcher.symbols.resolver import SymbolResolver
from src.nse_bhavcopy.downloader import BhavcopyDownloader

# Setup diagnostics logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER: logging.Logger = logging.getLogger("diagnostics")


def check_yfinance(symbol: str) -> bool:
    """
    Verify yfinance connection by pulling historical daily data for a symbol.

    Logic:
        Step 1: Instantiate Ticker object with target symbol.
        Step 2: Fetch history for last 1 month.
        Step 3: Validate returned dataframe is not empty and has OHLCV.

    Parameters:
        symbol (str): Ticker code to retrieve from yfinance. | Valid ticker.

    Returns:
        bool: True if data fetched successfully, False otherwise.

    Raises:
        None

    Example:
        >>> success = check_yfinance("RELIANCE.NS")
        >>> print(success)
        True

    Performance:
        Time Complexity: O(N) [Bounded by yfinance response latency]
        Space Complexity: O(N) [Historical dataframe storage]

    Edge Cases Handled:
        - Network failures or API changes (caught via Exception block).
        - Empty dataframe response.
    """
    LOGGER.info("Starting yfinance check for %s...", symbol)
    try:
        ticker = yf.Ticker(symbol)
        df: pd.DataFrame = ticker.history(period="1mo")
        if df.empty:
            LOGGER.error("yfinance returned an empty DataFrame for %s.", symbol)
            return False
        LOGGER.info(
            "SUCCESS: yfinance fetched %d rows for %s. Last Close: %.2f",
            len(df),
            symbol,
            df["Close"].iloc[-1],
        )
        return True
    except Exception as e:
        LOGGER.error("FAILED: yfinance diagnostic failed: %s", str(e))
        return False


def check_nse_charts(symbol: str) -> bool:
    """
    Verify connection to authoritative NSE Charting API.

    Logic:
        Step 1: Initialize SessionManager, NSESessionInitializer, SymbolResolver.
        Step 2: Warm up cookies and initialize NSEChartFetcher.
        Step 3: Query charting API for 1 year of daily history.
        Step 4: Confirm returned dataframe is structured correctly.

    Parameters:
        symbol (str): Stock code to query (without suffix). | Valid symbol.

    Returns:
        bool: True if official charts retrieved successfully, False otherwise.

    Raises:
        None

    Example:
        >>> success = check_nse_charts("RELIANCE")
        >>> print(success)
        True

    Performance:
        Time Complexity: O(N) [Official charting server latency]
        Space Complexity: O(N) [Parsed dataframe records]

    Edge Cases Handled:
        - Token unmapped in resolver (uses fallback or prints warning).
        - HTTP 403/401/500 connection failure (caught in generic catch block).
    """
    LOGGER.info("Starting NSE Charting API check for %s...", symbol)
    try:
        sm = SessionManager(rate_limit_delay=0.1)
        init = NSESessionInitializer(sm)
        resolver = SymbolResolver()

        token: str | None = resolver.get_token(symbol)
        if not token:
            LOGGER.error("SymbolResolver could not resolve token for %s", symbol)
            return False

        LOGGER.info("Warm up session cookies...")
        init.ensure_initialized()

        fetcher = NSEChartFetcher(sm, init, resolver)
        df: pd.DataFrame = fetcher.fetch(symbol, period="1y")

        if df.empty:
            LOGGER.error("NSEChartFetcher returned empty DataFrame for %s.", symbol)
            return False

        LOGGER.info(
            "SUCCESS: NSE Charting API returned %d rows. Last Close: %.2f",
            len(df),
            df["Close"].iloc[-1],
        )
        return True
    except Exception as e:
        LOGGER.error("FAILED: NSE Charting API check failed: %s", str(e))
        return False


def check_bhavcopy() -> bool:
    """
    Verify NSE CM Bhavcopy file downloading and local cleaning pipeline.

    Logic:
        Step 1: Instantiate BhavcopyDownloader with test directories.
        Step 2: Generate target date cursor (going back past weekends/holidays).
        Step 3: Trigger download of ZIP bytes from archives.
        Step 4: Save and process ZIP to output standard cleaned CSV.

    Parameters:
        None

    Returns:
        bool: True if Bhavcopy downloaded and processed, False otherwise.

    Raises:
        None

    Example:
        >>> success = check_bhavcopy()
        >>> print(success)
        True

    Performance:
        Time Complexity: O(N) [Archive file download and clean]
        Space Complexity: O(M) [Dataframe slicing operations]

    Edge Cases Handled:
        - Skipping current date 404s (loops backward up to 7 calendar days).
        - Invalid ZIP structures.
    """
    LOGGER.info("Starting NSE Bhavcopy Downloader check...")
    try:
        downloader = BhavcopyDownloader(
            raw_dir="data/raw_test",
            processed_dir="data/processed_test",
            top_n=10,
        )

        date_cursor = datetime.now()
        success = False

        for i in range(7):
            test_date = date_cursor - timedelta(days=i)
            # Skip Saturday/Sunday
            if test_date.weekday() >= 5:
                continue

            date_str = test_date.strftime("%Y-%m-%d")
            LOGGER.info("Trying download for date: %s", date_str)

            try:
                zip_bytes = downloader.download_raw_bhavcopy(test_date)
                downloader.save_raw_bhavcopy(test_date, zip_bytes)
                rows = downloader.process_bhavcopy(test_date, zip_bytes)
                LOGGER.info(
                    "SUCCESS: Bhavcopy downloaded. Processed %d records.",
                    len(rows),
                )
                success = True
                break
            except Exception as e:
                LOGGER.warning("Date %s not available: %s", date_str, str(e))

        return success
    except Exception as e:
        LOGGER.error("FAILED: Bhavcopy check failed: %s", str(e))
        return False


def main() -> None:
    """
    Execute complete market data source diagnostics.

    Logic:
        Step 1: Check Yahoo Finance API.
        Step 2: Check authoritative NSE Charting API.
        Step 3: Check NSE Bhavcopy archive downloader.
        Step 4: Output summary status block and set exit status code.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> main()
    """
    LOGGER.info("=== STARTING MARKET DATA SOURCES DIAGNOSTICS ===")

    yf_ok: bool = check_yfinance("RELIANCE.NS")
    nse_ok: bool = check_nse_charts("RELIANCE")
    bhav_ok: bool = check_bhavcopy()

    LOGGER.info("=== DIAGNOSTICS RESULTS SUMMARY ===")
    LOGGER.info("Yahoo Finance API (yfinance):   %s", "WORKING" if yf_ok else "FAILED")
    LOGGER.info("NSE Charting API (nse_charts):  %s", "WORKING" if nse_ok else "FAILED")
    LOGGER.info(
        "NSE Bhavcopy Downloader (bhav): %s", "WORKING" if bhav_ok else "FAILED"
    )

    if yf_ok and nse_ok and bhav_ok:
        LOGGER.info("STATUS: All market data sources are 100% operational!")
        sys.exit(0)
    else:
        LOGGER.error("STATUS: Diagnostics detected one or more failures.")
        sys.exit(1)


if __name__ == "__main__":
    main()
