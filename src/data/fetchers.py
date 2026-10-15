"""
File: src/classes/Fetcher.py
Purpose: Handle data fetching from NSE and Yahoo Finance for stock screening.

Dependencies:
External:
- pandas>=2.0.0: [data manipulation and storage]
- requests: [fetching stock codes and NSE APIs]
- yfinance: [downloading historical stock data]
Internal:
- classes.ColorText: [CLI output styling]
- classes.ConfigLoader: [loading indices and US stock lists]
- classes.DataRepository: [local data caching and management]
- classes.SuppressOutput: [silent background execution]

Key Components:
Classes:
- Fetcher: Unified provider for all stock data (NSE v1 API + Yahoo Finance Fallback).
- StockDataEmptyException: Custom error for missing or delisted stock symbols.
Functions:
- fetchStockCodes: Retrieve list of symbols.
- fetchStockData: Legacy entry point for CLI.
- fetch_data: Unified entry point for Scanners/ML (supports caching).

Last Modified: 2026-02-19
Modified By: LLM

Open Tasks:
- [ ] [MEDIUM] Implement concurrent fetching for multiple stocks [5h]
- [ ] [LOW] Add proxy rotation for NSE API

Related Files:
- src/classes/DataRepository.py: [manages local storage]
"""

import csv
import datetime
import io
import os
import random
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import requests
import yfinance as yf

from src.data.storage import DataRepository
from src.utils.SuppressOutput import SuppressOutput


class StockDataEmptyException(Exception):
    """
    Raised when downloaded stock data is empty or contains only NaNs.
    """


class Fetcher:
    """
    Unified Data Fetcher handling NSE v1 API, Yahoo Finance fallback, and local caching.

    Design Pattern: Facade + DAO
    - Facade: Hides complexity of choosing between NSE/YF APIs.
    - DAO: Manages data access and caching via DataRepository.

    Attributes:
        configManager (Any): System configuration instance
        dataRepository (DataRepository): Local data persistence service
        indices (Dict): Mapping of index names to descriptions
        indices_urls (Dict): Mapping of ticker options to source URLs
        token_cache (Dict): Cache for NSE instrument tokens

    Public Methods:
        - fetch_data(symbol, timeframe, ...): Primary unified API (replaces UnifiedDataFetcher).
        - fetchStockData(...): Legacy CLI API.
        - fetchStockCodes(...): Get universe symbols.

    Private Methods:
        - _fetch_from_nse(...): NSE v1 Charting API.
        - _fetch_from_yf(...): Yahoo Finance API.
        - _get_token(...): Resolve NSE tokens.

    Dependencies:
        External: requests, yfinance, pandas
        Internal: DataRepository, ConfigLoader
    """

    INSTRUMENTS_FILE = "user_data/instruments.csv"
    INSTRUMENTS_URL = "https://api.kite.trade/instruments"

    def __init__(self, configManager: Any = None) -> None:
        """
        Initialize Fetcher with optional config.

        Parameters:
            configManager (Any): Reference to system configuration.
                                 If None, some legacy features might be disabled.
        """
        self.configManager = configManager
        self.dataRepository = DataRepository()
        self.indices = {
            "Nifty 50": "Nifty 50",
            "Nifty Next 50": "Nifty Next 50",
            "Nifty 100": "Nifty 100",
            "Nifty 200": "Nifty 200",
            "Nifty 500": "Nifty 500",
            "Nifty Smallcap 50": "Nifty Smallcap 50",
            "Nifty Smallcap 100": "Nifty Smallcap 100",
            "Nifty Smallcap 250": "Nifty Smallcap 250",
            "Nifty Midcap 50": "Nifty Midcap 50",
            "Nifty Midcap 100": "Nifty Midcap 100",
            "Nifty Midcap 150": "Nifty Midcap 150",
        }
        self.indices_urls = {}  # URLs are handled dynamically or not used directly in this refactor
        self.token_cache: Dict[str, str] = {}

    def _get_request(
        self,
        url: str,
        params: Optional[Dict] = None,
        json_payload: Optional[Dict] = None,
        method: str = "GET",
        timeout: int = 30,
        retries: int = 3,
        proxyServer: Optional[str] = None,
    ) -> Optional[requests.Response]:
        """
        Centralized request handler with retries, headers, and timeout.

        Logic:
            Step 1: Set standard browser-like headers.
            Step 2: Loop through retry attempts.
            Step 3: Execute request (GET/POST) and return response on success.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }

        proxies = {"https": proxyServer} if proxyServer else None

        for attempt in range(retries):
            try:
                if method.upper() == "POST":
                    res = requests.post(
                        url,
                        json=json_payload,
                        params=params,
                        headers=headers,
                        proxies=proxies,
                        timeout=timeout,
                    )
                else:
                    res = requests.get(
                        url,
                        params=params,
                        headers=headers,
                        proxies=proxies,
                        timeout=timeout,
                    )

                res.raise_for_status()
                return res
            except (
                requests.exceptions.RequestException,
                requests.exceptions.Timeout,
            ) as e:
                if attempt == retries - 1:
                    print(f"❌ Request failed after {retries} attempts: {e}")
                    return None
                wait = (attempt + 1) * 2
                print(
                    f"⚠️  Request failed, retrying in {wait}s... ({attempt+1}/{retries})"
                )
                time.sleep(wait)
        return None

    def fetch_data(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "1y",
        source: str = "auto",
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """
        Unified method to fetch data with intelligent caching and source selection.
        Replaces UnifiedDataFetcher.fetch_data and CachedDataFetcher.fetch_data.

        Args:
            symbol (str): Stock ticker.
            timeframe (str): Candle interval ('1d', '5m', etc).
            period (str): Lookback period ('1y', '5d').
            source (str): 'auto', 'nse', or 'yfinance'.
            force_refresh (bool): Ignore cache if True.

        Returns:
            pd.DataFrame: OHLCV data.
        """
        symbol = symbol.upper()
        # repo_timeframe = timeframe  # Map to repo convention if needed

        # 1. Try Cache (if not forced)
        if not force_refresh:
            cached_data = self.dataRepository.load_data(symbol)  # Repo handles storage
            # TODO: DataRepository might need update to handle timeframe-specific paths if they differ
            # For now assuming repo handles standard daily data primarily, or we adapt repo later.
            # Adaptation: DataRepository logic in current codebase seems to use a single dir.
            # If we need multi-timeframe support in repo, that's a separate task.
            # Current Repo implementation simply loads parquet/csv by symbol.

            if cached_data is not None and not cached_data.empty:
                # Check staleness
                last_date = cached_data.index[-1]
                if isinstance(last_date, pd.Timestamp):
                    last_date = last_date.to_pydatetime()

                days_since = (datetime.datetime.now() - last_date).days

                # If fresh enough for the requested period?
                # Simplification: If asking for intraday, cache might not be enough unless updated recently.
                # For daily, if < 1 day old, return cache.
                is_intraday = timeframe in ["1m", "5m", "15m", "30m", "1h"]
                freshness_threshold = 0 if is_intraday else 1

                if days_since <= freshness_threshold:
                    return cached_data

                # Incremental Fetch
                # Calculate period for delta
                delta_days = days_since + 5  # Buffer
                new_period = f"{delta_days}d"

                print(f"  🔄 Fetching {delta_days} days of new data for {symbol}...")
                new_data = self._fetch_internal(symbol, timeframe, new_period, source)

                if not new_data.empty:
                    # Merge
                    combined = pd.concat([cached_data, new_data])
                    combined = combined[~combined.index.duplicated(keep="last")]
                    combined = combined.sort_index()
                    self.dataRepository.save_data(symbol, combined)
                    return combined
                return cached_data

        # 2. Full Fetch
        print(f"  🌐 Fetching full {period} data for {symbol}...")
        data = self._fetch_internal(symbol, timeframe, period, source)
        if not data.empty:
            self.dataRepository.save_data(symbol, data)
        return data

    def _fetch_internal(
        self, symbol: str, timeframe: str, period: str, source: str
    ) -> pd.DataFrame:
        """Internal router for data source."""
        if source == "auto":
            if timeframe in ["1m", "5m", "15m", "30m", "1h"]:
                source = "nse"
            else:
                source = "yfinance"

        if source == "nse":
            return self._fetch_from_nse(symbol, timeframe, period)
        return self._fetch_from_yfinance(symbol, timeframe, period)

    def _get_token(self, symbol: str) -> Optional[str]:
        """Resolve NSE instrument token."""
        if symbol in self.token_cache:
            return self.token_cache[symbol]

        if not os.path.exists(self.INSTRUMENTS_FILE):
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.INSTRUMENTS_FILE), exist_ok=True)
            try:
                print("Downloading instruments list...")
                response = requests.get(self.INSTRUMENTS_URL, timeout=15)
                response.raise_for_status()
                with open(self.INSTRUMENTS_FILE, "wb") as f:
                    f.write(response.content)
            except Exception as e:
                print(f"Failed to download instruments: {e}")
                return None

        target_symbol = symbol.replace("-EQ", "")
        try:
            with open(self.INSTRUMENTS_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (
                        row["exchange"] == "NSE"
                        and row["tradingsymbol"] == target_symbol
                    ):
                        token = row["exchange_token"]
                        self.token_cache[symbol] = token
                        return token
        except Exception:
            return None
        return None

    def _fetch_from_nse(self, symbol: str, timeframe: str, period: str) -> pd.DataFrame:
        """Fetch from NSE v1 API."""
        token = self._get_token(symbol)
        if not token:
            return pd.DataFrame()

        # Parse period to days logic
        days = 365
        if "d" in period:
            days = int(period.replace("d", ""))
        elif "y" in period:
            days = int(period.replace("y", "")) * 365

        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=days)

        timeframe_map = {
            "1m": ("I", 1),
            "5m": ("I", 5),
            "15m": ("I", 15),
            "30m": ("I", 30),
            "1h": ("I", 60),
            "1d": ("D", 1),
            "1w": ("W", 1),
        }
        chart_type, time_interval = timeframe_map.get(timeframe, ("D", 1))

        display_symbol = symbol if symbol.endswith("-EQ") else f"{symbol}-EQ"
        url = "https://charting.nseindia.com/v1/charts/symbolHistoricalData"
        payload = {
            "token": token,
            "fromDate": int(start_date.timestamp()),
            "toDate": int(end_date.timestamp()),
            "symbol": display_symbol,
            "symbolType": "Equity",
            "chartType": chart_type,
            "timeInterval": time_interval,
        }

        try:
            res = self._get_request(
                url, method="POST", json_payload=payload, proxyServer=None
            )
            if not res or "data" not in (data := res.json()) or not data["data"]:
                return pd.DataFrame()

            df = pd.DataFrame(data["data"])
            df = df.rename(
                columns={
                    "time": "Timestamp",
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume",
                }
            )
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="ms")
            df = df.set_index("Timestamp").sort_index()
            cols = ["Open", "High", "Low", "Close", "Volume"]
            df = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
            return df
        except Exception as e:
            print(f"NSE Fetch Error: {e}")
            return pd.DataFrame()

    def _fetch_from_yfinance(
        self, symbol: str, timeframe: str, period: str
    ) -> pd.DataFrame:
        """Fetch from Yahoo Finance."""
        try:
            ticker = f"{symbol}.NS"
            interval_map = {"1d": "1d", "1w": "1wk"}
            interval = interval_map.get(timeframe, "1d")

            data = yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=False,
            )
            if data.empty:
                return pd.DataFrame()

            return self.makeDataBackwardCompatible(data)
        except Exception:
            return pd.DataFrame()

    def getAllNiftyIndices(self) -> Dict[str, str]:
        """
        Retrieve all supported Nifty indices and their descriptions.

        Returns:
            Dict[str, str]: Mapping of index code to name.
        """
        return self.indices

    def _getBacktestDate(
        self, backtest: datetime.date
    ) -> List[Optional[datetime.date]]:
        """
        Calculate start and end dates for a backtest window.

        Logic:
            Step 1: Determine the lookback delta based on config period unit.
            Step 2: Calculate start date by subtracting delta from backtest date.
            Step 3: Return range as list [start, end].

        Parameters:
            backtest (datetime.date): The target date for the backtest.

        Returns:
            List[Optional[datetime.date]]: [start_date, end_date] or [None, None] on error.
        """
        if not self.configManager:
            return [None, None]

        try:
            end = backtest + datetime.timedelta(days=1)
            if "d" in self.configManager.period:
                delta = datetime.timedelta(days=self.configManager.getPeriodNumeric())
            elif "wk" in self.configManager.period:
                delta = datetime.timedelta(
                    days=self.configManager.getPeriodNumeric() * 7
                )
            elif "m" in self.configManager.period:
                delta = datetime.timedelta(
                    minutes=self.configManager.getPeriodNumeric()
                )
            elif "h" in self.configManager.period:
                delta = datetime.timedelta(hours=self.configManager.getPeriodNumeric())
            start = end - delta
            return [start, end]
        except Exception:
            return [None, None]

    def _getDatesForBacktestReport(
        self, backtest: datetime.date
    ) -> Dict[str, Optional[Union[datetime.date, float]]]:
        """
        Identify benchmark dates for post-signal performance tracking.

        Logic:
            Step 1: Calculate target dates (T+1d, T+1wk, T+1mo, etc.).
            Step 2: Adjust dates for weekends (Saturday/Sunday -> Monday).
            Step 3: Return dictionary of labels to dates.

        Parameters:
            backtest (datetime.date): The date when the signal was generated.

        Returns:
            Dict[str, Optional[Union[datetime.date, float]]]: Mapping of timeframes to target dates.
        """
        dateDict = {}
        try:
            today = datetime.date.today()
            dateDict["T+1d"] = (
                backtest + datetime.timedelta(days=1)
                if backtest + datetime.timedelta(days=1) < today
                else None
            )
            dateDict["T+1wk"] = (
                backtest + datetime.timedelta(weeks=1)
                if backtest + datetime.timedelta(weeks=1) < today
                else None
            )
            dateDict["T+1mo"] = (
                backtest + datetime.timedelta(days=30)
                if backtest + datetime.timedelta(days=30) < today
                else None
            )
            dateDict["T+6mo"] = (
                backtest + datetime.timedelta(days=180)
                if backtest + datetime.timedelta(days=180) < today
                else None
            )
            dateDict["T+1y"] = (
                backtest + datetime.timedelta(days=365)
                if backtest + datetime.timedelta(days=365) < today
                else None
            )
            for key, val in dateDict.copy().items():
                if val is not None and isinstance(val, datetime.date):
                    if val.weekday() == 5:  # 5 is Saturday, 6 is Sunday
                        adjusted_date = val + datetime.timedelta(days=2)
                        dateDict[key] = adjusted_date
                    elif val.weekday() == 6:
                        adjusted_date = val + datetime.timedelta(days=1)
                        dateDict[key] = adjusted_date
        except Exception:
            pass
        return dateDict

    def fetchCodes(
        self, tickerOption: int, proxyServer: Optional[str] = None
    ) -> List[str]:
        """
        Fetch stock symbols from external NSE CSV sources.

        Parameters:
            tickerOption (int): Integer key for the index/segment.
            proxyServer (Optional[str]): Proxy server configuration.

        Returns:
            List[str]: List of stock symbols retrieved.
        """
        listStockCodes = []

        # Hardcoded mapping of options to NSE URLs
        indices_map = {
            1: "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv",
            2: "https://nsearchives.nseindia.com/content/indices/ind_niftynext50list.csv",
            3: "https://nsearchives.nseindia.com/content/indices/ind_nifty100list.csv",
            4: "https://nsearchives.nseindia.com/content/indices/ind_nifty200list.csv",
            5: "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
            6: "https://nsearchives.nseindia.com/content/indices/ind_niftysmallcap50list.csv",
            7: "https://nsearchives.nseindia.com/content/indices/ind_niftysmallcap100list.csv",
            8: "https://nsearchives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
            9: "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap50list.csv",
            10: "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
            11: "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
            14: "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv",
        }

        if tickerOption == 12:  # All Stocks
            url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
            try:
                res = self._get_request(url, proxyServer=proxyServer)
                if res:
                    return list(
                        pd.read_csv(io.StringIO(res.content.decode("utf-8")))[
                            "SYMBOL"
                        ].values
                    )
                return []
            except Exception as e:
                print(f"Error fetching all stocks: {e}")
                return []

        if tickerOption == 15:  # US Stocks
            # Placeholder for US stocks as ConfigLoader is removed
            return ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

        if tickerOption == 16:  # Sectoral Indices
            return list(self.indices.keys())

        url = indices_map.get(tickerOption)

        if not url:
            return []

        try:
            res = self._get_request(url, proxyServer=proxyServer)

            if res:
                # Handle different CSV formats
                csv_content = res.content.decode("utf-8")

                if tickerOption == 14:  # F&O
                    df = pd.read_csv(io.StringIO(csv_content))
                    # Cleanup headers
                    df.columns = [c.strip() for c in df.columns]
                    # Filter for futures
                    listStockCodes = list(
                        set(df[df["UNDERLYING"] != ""]["SYMBOL"].to_list())
                    )  # Heuristic
                    # Actual NSE F&O csv structure varies, usually 'SYMBOL' or 'UNDERLYING'
                    if "SYMBOL" in df.columns:
                        listStockCodes = list(set(df["SYMBOL"].dropna().tolist()))
                    listStockCodes.sort()
                else:
                    df = pd.read_csv(io.StringIO(csv_content))
                    if "Symbol" in df.columns:
                        listStockCodes = df["Symbol"].tolist()
                    elif "SYMBOL" in df.columns:
                        listStockCodes = df["SYMBOL"].tolist()
                    else:
                        # Fallback to column index 2
                        if len(df.columns) > 2:
                            listStockCodes = df.iloc[:, 2].tolist()

        except Exception as error:
            print(f"Error fetching codes: {error}")

        return listStockCodes

    def fetchStockCodes(
        self, tickerOption: int, proxyServer: Optional[str] = None
    ) -> List[str]:
        """
        Fetch stock symbols with integrated CLI messaging and configuration.

        Logic:
            Step 1: Handle custom manual input if option is 0.
            Step 2: Delegate to fetchCodes for standard segments.
            Step 3: Apply shuffling and stage filtering based on config.

        Parameters:
            tickerOption (int): Selection ID for stock universe.
            proxyServer (Optional[str]): Optional proxy settings.

        Returns:
            List[str]: Final processed list of symbols.
        """
        from src.ui.ColorText import colorText
        listStockCodes = []
        if tickerOption == 0:
            stockCode = None
            while stockCode is None or stockCode == "":
                stockCode = str(
                    input(
                        colorText.BOLD
                        + colorText.BLUE
                        + "[+] Enter Stock Code(s) for screening (comma-separated): "
                    )
                ).upper()
            stockCode = stockCode.replace(" ", "")
            listStockCodes = stockCode.split(",")
        else:
            print(colorText.BOLD + "[+] Getting Stock Codes From NSE... ", end="")
            listStockCodes = self.fetchCodes(tickerOption, proxyServer=proxyServer)
            if isinstance(listStockCodes, dict):
                listStockCodes = list(listStockCodes.keys())
            if len(listStockCodes) > 10:
                print(
                    colorText.GREEN
                    + (f"=> Done! Fetched {len(listStockCodes)} stock codes.")
                    + colorText.END
                )
                if self.configManager and self.configManager.shuffleEnabled:
                    random.shuffle(listStockCodes)
                    print(
                        colorText.BLUE
                        + "[+] Stock shuffling is active."
                        + colorText.END
                    )
                else:
                    print(
                        colorText.FAIL
                        + "[+] Stock shuffling is inactive."
                        + colorText.END
                    )
            else:
                print(
                    colorText.FAIL
                    + "=> Error getting stock codes from NSE!"
                    + colorText.END
                )

        return listStockCodes

    def fetchStockData(
        self,
        stockCode: str,
        period: str = "1y",
        duration: str = "1d",
        proxyServer: Optional[str] = None,
        backtestDate: Optional[datetime.date] = None,
        tickerOption: Optional[int] = None,
    ) -> Tuple[Optional[pd.DataFrame], Optional[Dict[str, Any]]]:
        """
        Retrieve historical price data (Legacy CLI Method).
        Wrapper around `fetch_data` to maintain CLI compatibility.
        """
        dateDict = None
        data = None

        append_exchange = ".NS"
        if tickerOption in [15, 16]:
            append_exchange = ""

        # Use unified fetch_data logic where possible
        # CLI currently only supports Yahoo for most things, but we can now enable cache
        # Logic mismatch: CLI uses 'duration' (interval), unified uses 'timeframe'

        # Backward compatibility translation
        timeframe = duration

        try:
            # If backtest, use special logic (or just download YF directly as backtest requires future data)
            if backtestDate:
                # Keep legacy logic for backtest for now to avoid breaking it
                with SuppressOutput(suppress_stdout=True, suppress_stderr=True):
                    start_date, end_date = self._getBacktestDate(backtest=backtestDate)
                    if start_date and end_date:
                        data = yf.download(
                            tickers=stockCode + append_exchange,
                            interval=duration,
                            start=start_date,
                            end=end_date,
                            progress=False,
                            auto_adjust=False,
                        )
                        data = self.makeDataBackwardCompatible(data)

                        dateDict = self._getDatesForBacktestReport(
                            backtest=backtestDate
                        )
                        backtestData = yf.download(
                            tickers=stockCode + append_exchange,
                            start=backtestDate - datetime.timedelta(days=1),
                            end=backtestDate + datetime.timedelta(days=370),
                            progress=False,
                            auto_adjust=False,
                        )
                        # Fill dateDict ... (copying legacy logic)
                        if not backtestData.empty:
                            backtestData = self.makeDataBackwardCompatible(backtestData)
                            for key, value in dateDict.copy().items():
                                if value is not None and isinstance(
                                    value, datetime.date
                                ):
                                    try:
                                        ts = pd.Timestamp(value)
                                        # Find nearest date
                                        idx = backtestData.index.get_indexer(
                                            [ts], method="nearest"
                                        )[0]
                                        dateDict[key] = backtestData.iloc[idx]["Close"]
                                    except Exception:
                                        continue
                            dateDict["T+52wkH"] = float(backtestData["High"].max())
                            dateDict["T+52wkL"] = float(backtestData["Low"].min())

            else:
                # Standard fetch
                data = self.fetch_data(
                    stockCode,
                    timeframe=timeframe,
                    period=period,
                    source="yfinance" if tickerOption in [15, 16] else "auto",
                )

        except Exception:
            pass

        if data is None or data.empty:
            raise StockDataEmptyException

        return data, dateDict

    def fetchLatestNiftyDaily(self, proxyServer: Optional[str] = None) -> pd.DataFrame:
        """
        Fetch most recent daily data for Nifty 50, Gold, and Crude oil.

        Parameters:
            proxyServer (Optional[Dict]): Proxy settings.

        Returns:
            pd.DataFrame: Merged daily benchmark data.
        """
        if proxyServer:
            yf.config.network.proxy = proxyServer

        common_args = {
            "auto_adjust": False,
            "period": "5d",
            "interval": "1d",
            "progress": False,
            "timeout": 10,
        }
        data = yf.download(tickers="^NSEI", **common_args)
        gold = yf.download(tickers="GC=F", **common_args).add_prefix("gold_")
        crude = yf.download(tickers="CL=F", **common_args).add_prefix("crude_")

        data = self.makeDataBackwardCompatible(data)
        gold = self.makeDataBackwardCompatible(gold, column_prefix="gold_")
        crude = self.makeDataBackwardCompatible(crude, column_prefix="crude_")
        return pd.concat([data, gold, crude], axis=1)

    def fetchNiftyData(
        self, period: str = "1y", proxyServer: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch historical daily data for the Nifty 50 index.

        Parameters:
            period (str): Lookback period.
            proxyServer (Optional[Dict]): Proxy settings.

        Returns:
            pd.DataFrame: Standardized Nifty OHLCV data.
        """
        if proxyServer:
            yf.config.network.proxy = proxyServer

        data = yf.download(
            auto_adjust=False,
            tickers="^NSEI",
            period=period,
            interval="1d",
            progress=False,
            timeout=10,
        )
        return self.makeDataBackwardCompatible(data)

    def fetchFiveEmaData(
        self, proxyServer: Optional[str] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Retrieve 5m and 15m data for Nifty and Bank Nifty (5-EMA strategy).

        Returns:
            Tuple[pd.DataFrame, ...]: (Nifty_15m, BankNifty_15m, Nifty_5m, BankNifty_5m)
        """
        if proxyServer:
            yf.config.network.proxy = proxyServer

        def d(ticker, interval):
            return self.makeDataBackwardCompatible(
                yf.download(
                    auto_adjust=False,
                    tickers=ticker,
                    period="5d",
                    interval=interval,
                    progress=False,
                    timeout=10,
                )
            )

        return (
            d("^NSEI", "15m"),
            d("^NSEBANK", "15m"),
            d("^NSEI", "5m"),
            d("^NSEBANK", "5m"),
        )

    def fetchWatchlist(self) -> Optional[List[str]]:
        """
        Load stock symbols from the local 'watchlist.xlsx' file.

        Logic:
            Step 1: Attempt to read Excel file.
            Step 2: Create template if file is missing or malformed.
            Step 3: Return list of symbols from 'Stock Code' column.

        Returns:
            Optional[List[str]]: List of symbols or None if template was created.
        """
        createTemplate = False
        data_df = pd.DataFrame()
        try:
            data_df = pd.read_excel("watchlist.xlsx")
            if "Stock Code" in data_df.columns:
                return data_df["Stock Code"].values.tolist()
            createTemplate = True
        except FileNotFoundError:
            createTemplate = True
        except Exception:
            createTemplate = True

        if createTemplate:
            sample = {"Stock Code": ["SBIN", "INFY", "TATAMOTORS", "ITC"]}
            sample_data = pd.DataFrame(sample)
            sample_data.to_excel("watchlist_template.xlsx", index=False)
            return None
        return []

    def makeDataBackwardCompatible(
        self, data: pd.DataFrame, column_prefix: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Standardize yfinance v3+ MultiIndex columns for internal consistency.

        Logic:
            Step 1: Flatten MultiIndex columns if present.
            Step 2: Rename columns to remove duplicate levels.
            Step 3: Filter for standard OHLCV columns.

        Parameters:
            data (pd.DataFrame): Raw yfinance DataFrame.
            column_prefix (Optional[str]): Optional prefix for column names.

        Returns:
            pd.DataFrame: Cleaned DataFrame with standard headers.
        """
        if isinstance(data.columns, pd.MultiIndex):
            # Check if levels contain OHLC names
            found = False
            for level in [0, 1]:
                if any(
                    x in data.columns.get_level_values(level)
                    for x in ["Close", "Adj Close", "Open"]
                ):
                    data.columns = data.columns.get_level_values(level)
                    found = True
                    break
            if not found:
                # Fallback
                data.columns = [f"{c[0]}_{c[1]}" for c in data.columns]

        if not data.empty and isinstance(data.columns[0], tuple):
            # Handle remaining tuples
            data.columns = [str(c[0]) for c in data.columns]

        data = data.rename_axis(None, axis=1)
        data = data.loc[:, ~data.columns.duplicated()]

        prefix = column_prefix or ""
        cols_to_keep = [
            f"{prefix}{c}"
            for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
        ]

        # Fuzzy match columns
        final_cols = []
        for target in cols_to_keep:
            if target in data.columns:
                final_cols.append(target)
            else:
                # Try to find match
                for col in data.columns:
                    if target.lower() == col.lower():
                        data = data.rename(columns={col: target})
                        final_cols.append(target)
                        break

        return data[final_cols]
