"""
File: nse_charting_fetcher.py
Purpose: Fetch historical data from NSE Charting API (charting.nseindia.com)

Uses the EXACT endpoint from browser network trace:
  GET https://charting.nseindia.com/v1/charts/symbolHistoricalData

Fixed date parsing for NSE charting API response format.

Last Modified: 2026-05-27
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests

LOGGER: logging.Logger = logging.getLogger(__name__)


class NSEChartingFetcher:
    """
    Fetch historical stock data from NSE Charting API.

    Uses the exact endpoint discovered from browser network trace:
    https://charting.nseindia.com/v1/charts/symbolHistoricalData

    The API returns data with dates that need special parsing.
    """

    BASE_URL: str = "https://charting.nseindia.com"
    API_ENDPOINT: str = "/v1/charts/symbolHistoricalData"

    def __init__(self, cache_dir: str = "data/cache") -> None:
        self.cache_dir: str = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

        self.session: requests.Session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) "
                    "Gecko/20100101 Firefox/150.0"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
        )

        self._cookies_ready: bool = False

    def _warmup_cookies(self) -> bool:
        """Visit charting page to get required cookies."""
        if self._cookies_ready:
            return True

        try:
            LOGGER.info("Warming up cookies from charting.nseindia.com...")

            resp = self.session.get(
                f"{self.BASE_URL}/",
                timeout=15,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                },
            )

            LOGGER.info("Charting page status: %d", resp.status_code)

            if resp.status_code == 200:
                time.sleep(0.5)
                resp2 = self.session.get(
                    f"{self.BASE_URL}/?symbol=TCS-EQ",
                    timeout=15,
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                    },
                )
                LOGGER.info("Symbol page status: %d", resp2.status_code)

                self._cookies_ready = True
                time.sleep(0.5)
                return True
            else:
                LOGGER.warning("Failed to get cookies: status %d", resp.status_code)

        except Exception as e:
            LOGGER.warning("Cookie warmup failed: %s", e)

        return False

    def _build_params(self, symbol: str, days: int = 365) -> dict[str, Any]:
        """Build API parameters matching the network trace exactly."""
        clean_symbol = symbol.replace(".NS", "").upper()

        to_date = int(datetime.now().timestamp())
        from_date = int((datetime.now() - timedelta(days=days)).timestamp())

        return {
            "token": "11536",
            "fromDate": str(from_date),
            "toDate": str(to_date),
            "symbol": f"{clean_symbol}-EQ",
            "symbolType": "Equity",
            "chartType": "I",
            "timeInterval": "1",
        }

    def _parse_response(self, data: dict, symbol: str) -> pd.DataFrame:
        """
        Parse the JSON response from NSE Charting API.

        The response format from the API is:
        {
            "data": [
                {
                    "timestamp": 1779857257,  # Unix timestamp
                    "open": 2278.7,
                    "high": 2279.0,
                    "low": 2277.4,
                    "close": 2278.0,
                    "volume": 25503
                },
                ...
            ]
        }

        Or sometimes the timestamp is in milliseconds.
        """
        if not data:
            LOGGER.warning("Empty response for %s", symbol)
            return pd.DataFrame()

        records = None

        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            if "data" in data:
                records = data["data"]
            elif "result" in data:
                records = data["result"]
            elif "records" in data:
                records = data["records"]
            else:
                for key, val in data.items():
                    if isinstance(val, list) and len(val) > 0:
                        records = val
                        LOGGER.info("Found records under key: %s", key)
                        break

        if records is None or not records:
            LOGGER.warning("Could not find records in response for %s", symbol)
            return pd.DataFrame()

        df = pd.DataFrame(records)

        # Check what columns we have
        LOGGER.debug("Raw columns: %s", df.columns.tolist())
        LOGGER.debug("First row: %s", df.iloc[0].to_dict() if not df.empty else "empty")

        # Standardize column names
        column_map = {
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "timestamp": "Timestamp",
            "date": "Date",
            "time": "Timestamp",
        }

        # Convert column names to lowercase for matching
        df.columns = [str(c).lower().strip() for c in df.columns]

        rename_dict = {}
        for old, new in column_map.items():
            if old in df.columns:
                rename_dict[old] = new

        if rename_dict:
            df = df.rename(columns=rename_dict)

        # Parse timestamp/date
        if "Timestamp" in df.columns:
            # NSE returns timestamps - could be seconds or milliseconds
            ts_values = df["Timestamp"].iloc[0]

            if ts_values > 1_000_000_000_000:  # Milliseconds
                LOGGER.info("Timestamps detected as milliseconds")
                df["Date"] = pd.to_datetime(df["Timestamp"], unit="ms")
            else:  # Seconds
                LOGGER.info("Timestamps detected as seconds")
                df["Date"] = pd.to_datetime(df["Timestamp"], unit="s")

            df = df.drop(columns=["Timestamp"])

        elif "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        if "Date" in df.columns:
            df = df.set_index("Date").sort_index()

        # Ensure numeric columns
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def fetch_symbol(self, symbol: str, days: int = 365) -> pd.DataFrame:
        """
        Fetch historical data for a single symbol from NSE Charting API.

        Args:
            symbol: NSE symbol (e.g., "TCS", "RELIANCE")
            days: Number of days of history to fetch

        Returns:
            DataFrame with OHLCV data
        """
        clean_symbol = symbol.replace(".NS", "").upper()

        if not self._warmup_cookies():
            LOGGER.error("Cannot fetch without cookies")
            return pd.DataFrame()

        params = self._build_params(clean_symbol, days)
        url = f"{self.BASE_URL}{self.API_ENDPOINT}"

        headers = {
            "Referer": f"{self.BASE_URL}/?symbol={clean_symbol}-EQ",
        }

        try:
            LOGGER.info("Fetching %s from NSE Charting API...", clean_symbol)

            resp = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=30,
            )

            LOGGER.info(
                "Response status: %d, size: %d bytes",
                resp.status_code,
                len(resp.content),
            )

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    df = self._parse_response(data, clean_symbol)

                    if not df.empty:
                        LOGGER.info(
                            "Successfully fetched %d rows for %s", len(df), clean_symbol
                        )
                        LOGGER.info(
                            "Date range: %s to %s", df.index.min(), df.index.max()
                        )
                        return df
                    else:
                        LOGGER.warning("Parsed DataFrame is empty for %s", clean_symbol)

                except json.JSONDecodeError as e:
                    LOGGER.warning("JSON decode error for %s: %s", clean_symbol, e)
            else:
                LOGGER.warning(
                    "API returned status %d for %s", resp.status_code, clean_symbol
                )

        except Exception as e:
            LOGGER.error("Fetch failed for %s: %s", clean_symbol, e)

        return pd.DataFrame()

    def fetch_symbols(
        self, symbols: list[str], days: int = 365
    ) -> dict[str, pd.DataFrame]:
        """Fetch historical data for multiple symbols."""
        results: dict[str, pd.DataFrame] = {}

        for symbol in symbols:
            clean = symbol.replace(".NS", "").upper()
            ns_symbol = f"{clean}.NS"

            df = self.fetch_symbol(clean, days)
            if not df.empty:
                results[ns_symbol] = df
            else:
                LOGGER.error("Failed to fetch %s", clean)
                results[ns_symbol] = pd.DataFrame()

            time.sleep(1.0)

        return results

    def fetch_multiindex(self, symbols: list[str], days: int = 365) -> pd.DataFrame:
        """Fetch and return as MultiIndex DataFrame for screener compatibility."""
        results = self.fetch_symbols(symbols, days)

        dfs: list[pd.DataFrame] = []
        for symbol, df in results.items():
            if df.empty:
                continue
            df.columns = pd.MultiIndex.from_product([[symbol], df.columns])
            dfs.append(df)

        if not dfs:
            return pd.DataFrame()

        return pd.concat(dfs, axis=1)


# Standalone test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    fetcher = NSEChartingFetcher(cache_dir="data/cache")

    print("\n=== Testing NSEChartingFetcher ===")
    df = fetcher.fetch_symbol("TCS", days=30)

    if df.empty:
        print("\nTCS: FAILED - No data")
    else:
        print(f"\nTCS: SUCCESS - {len(df)} rows")
        print(f"Date range: {df.index.min()} to {df.index.max()}")
        print("\nLast 5 rows:")
        print(df.tail(5))
        print(f"\nColumns: {df.columns.tolist()}")
