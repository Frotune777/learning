"""
File: src/data/fetcher/prices/nse_charts.py
Purpose: Acquisition of price data directly from NSE's charting API.

Dependencies:
External:
- pandas>=2.2.3: Data structuring and mapping operations
Internal:
- src.data.fetcher.prices.base: [AbstractPriceFetcher]
- src.data.fetcher.session.manager: [SessionManager]
- src.data.fetcher.session.nse_session: [NSESessionInitializer]
- src.data.fetcher.symbols.resolver: [SymbolResolver]
- src.data.fetcher.circuit_breaker: [CircuitBreaker]

Key Components:
Classes:
- NSEChartFetcher: Implementation for NSE V1 charting endpoint.
Functions:
- None

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- [ ] [HIGH] Add support for custom timeout limits in parameters

Related Files:
- src/data/fetcher/prices/base.py: Abstract base class interface.
"""

import logging
import time
from typing import ClassVar

import pandas as pd

from src.data.fetcher.circuit_breaker import CircuitBreaker
from src.data.fetcher.prices.base import AbstractPriceFetcher
from src.data.fetcher.session.manager import SessionManager
from src.data.fetcher.session.nse_session import NSESessionInitializer
from src.data.fetcher.symbols.resolver import SymbolResolver

logger = logging.getLogger(__name__)


class NSEChartFetcher(AbstractPriceFetcher):
    """
    IMPLEMENTATION FOR NSE V1 CHARTING ENDPOINT.

    Design Pattern: Strategy - Standardizes price retrievals using the official
    NSE V1 charting symbolHistoricalData endpoint.

    Attributes:
        URL (str): The V1 symbols historical data endpoint.
        TF_MAP (dict): Timeframe conversion registry.
    """

    URL: ClassVar[str] = "https://charting.nseindia.com/v1/charts/symbolHistoricalData"

    TF_MAP: ClassVar[dict[str, tuple[str, int]]] = {
        "1m": ("I", 1),
        "5m": ("I", 5),
        "15m": ("I", 15),
        "30m": ("I", 30),
        "1h": ("I", 60),
        "1d": ("D", 1),
        "1w": ("W", 1),
        "1mo": ("M", 1),
    }

    def __init__(
        self,
        session_manager: SessionManager,
        nse_initializer: NSESessionInitializer,
        symbol_resolver: SymbolResolver,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        """Initialize with required session and metadata components."""
        self.sm = session_manager
        self.nse_init = nse_initializer
        self.resolver = symbol_resolver
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    def fetch(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "1y",
        from_date: int | None = None,
        to_date: int | None = None,
    ) -> pd.DataFrame:
        """
        FETCH OHLCV FROM NSE API WRAPPED IN A CIRCUIT BREAKER.

        Logic:
            Step 1: Delegate download logic execution to the circuit breaker.
            Step 2: Circuit breaker executes _fetch_raw internally.
            Step 3: Return parsed DataFrame on success, bubble exception on
                    open breaker.

        Parameters:
            symbol (str): Target stock ticker. | Must be non-empty string.
            timeframe (str): Interval timescale code. | Default '1d'.
            period (str): Scope length code. | Default '1y'.
            from_date (Optional[int]): Start epoch timestamp. | Default None.
            to_date (Optional[int]): End epoch timestamp. | Default None.

        Returns:
            pd.DataFrame: Normalized stock historical series.

        Raises:
            Exception: Raised on connection failures or open circuit state.

        Example:
            >>> sm = SessionManager()
            >>> init = NSESessionInitializer(sm)
            >>> resolver = SymbolResolver()
            >>> fetcher = NSEChartFetcher(sm, init, resolver)
            >>> df = fetcher.fetch("TCS", period="1y")

        Performance:
            Time Complexity: O(N) [Parsed records length N]
            Space Complexity: O(N) [Stored records size N]

        Edge Cases Handled:
            - Catches remote exceptions, logging and bubble them out safely.
        """
        try:
            return self.circuit_breaker.call(
                self._fetch_raw, symbol, timeframe, period, from_date, to_date
            )
        except Exception as e:
            # We log but raise so orchestrator can handle fallback
            logger.debug("Circuit breaker triggered or NSE fetch failed: %s", e)
            raise

    def _fetch_raw(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "1y",
        from_date: int | None = None,
        to_date: int | None = None,
    ) -> pd.DataFrame:
        """
        INTERNAL RAW FETCH IMPLEMENTATION QUERYING THE REMOTE CHART API.

        Logic:
            Step 1: Check symbol mapping token. If missing, return empty.
            Step 2: Calculate epoch boundaries from provided limits/timescales.
            Step 3: Respect session managers rate limit pacing.
            Step 4: Ensure connection cookies are warmed up and active.
            Step 5: Execute GET call and check status codes.
            Step 6: Rename and structure time fields into standardized Kolkatta.

        Parameters:
            symbol (str): Target stock ticker. | Non-empty string.
            timeframe (str): Interval code. | String.
            period (str): History scope code. | String.
            from_date (Optional[int]): Start epoch limit. | Default None.
            to_date (Optional[int]): End epoch limit. | Default None.

        Returns:
            pd.DataFrame: Clean sorted and index-normalized OHLCV.

        Raises:
            requests.exceptions.HTTPError: Raised on non-200 responses.

        Example:
            >>> # Called internally by self.fetch through the circuit breaker

        Performance:
            Time Complexity: O(N) [Mapping N time elements]
            Space Complexity: O(N) [DataFrame allocations]

        Edge Cases Handled:
            - Unmapped symbol maps return empty pandas DataFrames gracefully.
            - Bypasses fetch failures throwing errors on non-200 responses.
        """
        chart_type, time_interval = self.TF_MAP.get(timeframe, ("D", 1))

        # Resolve token
        token = self.resolver.get_token(symbol)
        if not token:
            logger.debug("No NSE token found for %s", symbol)
            return pd.DataFrame()

        # Handle dates
        if from_date is None:
            period_days = {
                "1d": 1,
                "5d": 5,
                "1mo": 30,
                "3mo": 90,
                "6mo": 180,
                "1y": 365,
                "max": 0,
            }
            days = period_days.get(period, 365)
            from_date = 0 if days == 0 else int(time.time()) - (days * 86400)

        if to_date is None:
            to_date = int(time.time()) + 30 * 86400

        # Rate limiting
        self.sm.respect_rate_limit()
        self.nse_init.ensure_initialized()

        params = {
            "token": token,
            "fromDate": str(from_date),
            "toDate": str(to_date),
            "symbol": f"{symbol.upper()}-EQ",
            "symbolType": "Equity",
            "chartType": chart_type,
            "timeInterval": str(time_interval),
        }

        session = self.sm.get_session()
        proxy = self.sm.get_proxy()
        resp = session.get(
            self.URL,
            params=params,
            headers={
                **self.sm.headers,
                "Origin": "https://charting.nseindia.com",
                "Referer": f"https://charting.nseindia.com/?symbol={symbol.upper()}-EQ",
            },
            timeout=25,
            proxies=proxy,
        )

        if resp.status_code != 200:
            # We raise for 4xx/5xx so circuit breaker counts it as failure
            resp.raise_for_status()

        records = resp.json().get("data", [])
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)

        # Rename standard columns using lowercase matching
        df.columns = [str(c).lower().strip() for c in df.columns]

        column_map = {
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "time": "Timestamp",
            "timestamp": "Timestamp",
            "date": "Date",
        }

        rename_dict = {}
        for old, new in column_map.items():
            if old in df.columns:
                rename_dict[old] = new

        if rename_dict:
            df = df.rename(columns=rename_dict)

        # Parse timestamp or date
        if "Timestamp" in df.columns:
            ts_val = df["Timestamp"].iloc[0]
            unit = "ms" if ts_val > 1_000_000_000_000 else "s"

            df["Date"] = (
                pd.to_datetime(df["Timestamp"], unit=unit, utc=True)
                .dt.tz_convert("Asia/Kolkata")
                .dt.tz_localize(None)
            )
            df = df.drop(columns=["Timestamp"])
        elif "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        if "Date" in df.columns:
            df = df.set_index("Date").sort_index()

        df = df[["Open", "High", "Low", "Close", "Volume"]]
        df = df.astype(float)
        return df.sort_index()
