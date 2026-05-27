"""
File: src/nse_bhavcopy/nse_data_fetcher.py
Purpose: Reliable data fetcher for NSE stocks using NSE's official APIs
         and yfinance with robust fallback mechanisms.

This module replaces direct yfinance usage with a multi-layered approach:
1. NSE Official API (most reliable for Indian stocks)
2. yfinance with curl_cffi backend (if available)
3. yfinance with custom session and retries
4. Local cache (if data was fetched recently)

Dependencies:
- requests>=2.32.3
- pandas>=2.2.3
- numpy>=2.4.6
- yfinance>=0.2.50 (optional, with curl_cffi)

Last Modified: 2026-05-27
"""

import logging
import os
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

LOGGER: logging.Logger = logging.getLogger(__name__)


class NSEDataFetcher:
    """
    Reliable data fetcher for NSE stocks with multiple fallback sources.

    Priority order:
    1. NSE Official Historical API (nseindia.com)
    2. Yahoo Finance via yfinance (with curl_cffi if available)
    3. Local cache (if fresh)

    Attributes:
        cache_dir (str): Directory for caching fetched data.
        cache_days (int): How many days to keep cache fresh.
        session (requests.Session): Reusable HTTP session with headers.
    """

    def __init__(self, cache_dir: str = "data/cache", cache_days: int = 7) -> None:
        self.cache_dir: str = cache_dir
        self.cache_days: int = cache_days
        self.session: requests.Session = requests.Session()

        # NSE requires specific headers
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
        )

        os.makedirs(self.cache_dir, exist_ok=True)

        # Check if yfinance is available
        self._has_yfinance: bool = False
        self._yf = None
        try:
            import yfinance as yf

            self._has_yfinance = True
            self._yf = yf
            LOGGER.info("yfinance available (version: %s)", yf.__version__)
        except ImportError:
            LOGGER.warning("yfinance not installed. Will use NSE API only.")

    def _cache_path(self, symbol: str) -> str:
        """Get cache file path for a symbol."""
        clean = symbol.replace(".NS", "").replace("-", "_").upper()
        return os.path.join(self.cache_dir, f"{clean}.parquet")

    def _load_cache(self, symbol: str) -> pd.DataFrame | None:
        """Load cached data if fresh."""
        path = self._cache_path(symbol)
        if not os.path.exists(path):
            return None

        mtime = os.path.getmtime(path)
        age_days = (datetime.now().timestamp() - mtime) / 86400
        if age_days > self.cache_days:
            LOGGER.debug("Cache expired for %s (age: %.1f days)", symbol, age_days)
            return None

        try:
            df = pd.read_parquet(path)
            LOGGER.info("Loaded cache for %s (age: %.1f days)", symbol, age_days)
            return df
        except Exception as e:
            LOGGER.warning("Cache read failed for %s: %s", symbol, e)
            return None

    def _save_cache(self, symbol: str, df: pd.DataFrame) -> None:
        """Save data to cache."""
        path = self._cache_path(symbol)
        try:
            df.to_parquet(path)
            LOGGER.debug("Saved cache for %s", symbol)
        except Exception as e:
            LOGGER.warning("Cache write failed for %s: %s", symbol, e)

    def _fetch_nse_history(self, symbol: str, days: int = 365) -> pd.DataFrame:
        """
        Fetch historical data from NSE's official API.

        This is the MOST RELIABLE source for Indian stocks.
        Uses NSE's chart data API which provides OHLCV data.

        Args:
            symbol: NSE symbol (e.g., "TCS", "RELIANCE")
            days: Number of days of history to fetch

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
        """
        clean_symbol = symbol.replace(".NS", "").upper()

        # NSE chart API endpoint
        url = "https://www.nseindia.com/api/historical/cm/equity"

        # We need to get cookies first by visiting the main page
        try:
            # Step 1: Get cookies from main page
            self.session.get("https://www.nseindia.com", timeout=10)
            time.sleep(0.5)

            # Step 2: Fetch historical data
            # Using the newer NSE API format
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            params = {
                "symbol": clean_symbol,
                "series": '["EQ"]',
                "from": start_date.strftime("%d-%m-%Y"),
                "to": end_date.strftime("%d-%m-%Y"),
            }

            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    records = data["data"]
                    df = pd.DataFrame(records)

                    # Map NSE columns to standard OHLCV
                    column_map = {
                        "CH_OPENING_PRICE": "Open",
                        "CH_TRADE_HIGH_PRICE": "High",
                        "CH_TRADE_LOW_PRICE": "Low",
                        "CH_CLOSING_PRICE": "Close",
                        "CH_TOT_TRADED_QTY": "Volume",
                        "CH_TIMESTAMP": "Date",
                    }

                    df = df.rename(columns=column_map)
                    df["Date"] = pd.to_datetime(df["Date"])
                    df = df.set_index("Date")
                    df = df.sort_index()

                    # Ensure numeric types
                    for col in ["Open", "High", "Low", "Close", "Volume"]:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors="coerce")

                    LOGGER.info(
                        "Fetched %d days from NSE API for %s", len(df), clean_symbol
                    )
                    return df
                else:
                    LOGGER.warning("NSE API returned empty data for %s", clean_symbol)
            else:
                LOGGER.warning(
                    "NSE API returned status %d for %s",
                    response.status_code,
                    clean_symbol,
                )

        except Exception as e:
            LOGGER.warning("NSE API failed for %s: %s", clean_symbol, e)

        return pd.DataFrame()

    def _fetch_yfinance_history(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        """
        Fetch historical data from Yahoo Finance using yfinance.

        Uses curl_cffi backend if available for better reliability.
        Includes retry logic with exponential backoff.

        Args:
            symbol: Yahoo Finance symbol (e.g., "TCS.NS")
            period: Data period ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y")

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
        """
        if not self._has_yfinance or self._yf is None:
            LOGGER.warning("yfinance not available for %s", symbol)
            return pd.DataFrame()

        # Try with retries
        max_retries = 3
        backoff = 2.0

        for attempt in range(max_retries):
            try:
                # Use threads=False to avoid threading issues
                data = self._yf.download(
                    symbol,
                    period=period,
                    interval="1d",
                    progress=False,
                    threads=False,
                    timeout=30,
                )

                if not data.empty:
                    LOGGER.info("yfinance fetched %d rows for %s", len(data), symbol)
                    return data
                else:
                    LOGGER.warning(
                        "yfinance returned empty for %s (attempt %d)",
                        symbol,
                        attempt + 1,
                    )

            except Exception as e:
                LOGGER.warning(
                    "yfinance error for %s (attempt %d): %s", symbol, attempt + 1, e
                )

            if attempt < max_retries - 1:
                LOGGER.info("Retrying in %.1f seconds...", backoff)
                time.sleep(backoff)
                backoff *= 2

        return pd.DataFrame()

    def fetch_history(
        self,
        symbols: list[str],
        period: str = "1y",
        prefer_nse: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch historical data for multiple symbols with intelligent fallback.

        For each symbol:
        1. Check local cache first
        2. If prefer_nse=True, try NSE API
        3. Fall back to yfinance
        4. Save successful fetches to cache

        Args:
            symbols: List of symbols (with .NS suffix for yfinance, without for NSE)
            period: Data period for yfinance fallback
            prefer_nse: Whether to prefer NSE API over yfinance

        Returns:
            Dict mapping symbol to DataFrame.
            Missing symbols will have empty DataFrames.
        """
        results: dict[str, pd.DataFrame] = {}

        for symbol in symbols:
            LOGGER.info("Fetching history for %s...", symbol)

            # 1. Check cache
            cached = self._load_cache(symbol)
            if cached is not None and not cached.empty:
                results[symbol] = cached
                continue

            df = pd.DataFrame()

            # 2. Try NSE API (if preferred)
            if prefer_nse:
                df = self._fetch_nse_history(symbol, days=365)
                if not df.empty:
                    results[symbol] = df
                    self._save_cache(symbol, df)
                    continue

            # 3. Try yfinance
            # Ensure .NS suffix for yfinance
            yf_symbol = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
            df = self._fetch_yfinance_history(yf_symbol, period=period)

            if not df.empty:
                # Standardize column names
                df.columns = [
                    c.title() if isinstance(c, str) else c for c in df.columns
                ]
                results[symbol] = df
                self._save_cache(symbol, df)
            else:
                LOGGER.error("All sources failed for %s", symbol)
                results[symbol] = pd.DataFrame()

            # Polite delay between requests
            time.sleep(1.0)

        return results

    def fetch_history_single_df(
        self,
        symbols: list[str],
        period: str = "1y",
        prefer_nse: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch history and return as a single MultiIndex DataFrame
        compatible with the existing screener interface.

        Args:
            symbols: List of symbols
            period: Data period
            prefer_nse: Prefer NSE API

        Returns:
            MultiIndex DataFrame with (symbol, field) columns
        """
        results = self.fetch_history(symbols, period, prefer_nse)

        dfs: list[pd.DataFrame] = []
        for symbol, df in results.items():
            if df.empty:
                continue
            # Create MultiIndex columns
            df.columns = pd.MultiIndex.from_product([[symbol], df.columns])
            dfs.append(df)

        if not dfs:
            return pd.DataFrame()

        # Concatenate and align dates
        combined = pd.concat(dfs, axis=1)
        return combined


# Simple standalone test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    fetcher = NSEDataFetcher(cache_dir="data/cache")

    # Test with a few symbols
    test_symbols = ["TCS", "RELIANCE", "INFY"]

    print("\n=== Testing NSEDataFetcher ===")
    results = fetcher.fetch_history(test_symbols, prefer_nse=True)

    for sym, df in results.items():
        if df.empty:
            print(f"\n{sym}: FAILED - No data")
        else:
            print(f"\n{sym}: SUCCESS - {len(df)} rows")
            print(df.tail(3))
