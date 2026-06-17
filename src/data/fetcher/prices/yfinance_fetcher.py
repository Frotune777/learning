"""
File: src/data/fetcher/prices/yfinance_fetcher.py
Purpose: Yahoo Finance implementation of AbstractPriceFetcher for NSE equities.

Dependencies:
External:
- pandas>=2.2.3: DataFrame normalization
- yfinance>=0.2.52: Historical price retrieval via download/Ticker/Tickers
Internal:
- src.data.fetcher.prices.base: [AbstractPriceFetcher]

Key Components:
Classes:
- YFinanceFetcher: Fetches OHLCV from Yahoo Finance for NSE symbols.

Last Modified: 2026-06-17
Modified By: Kimi

Open Tasks:
- [ ] [MEDIUM] Add proxy rotation support for rate-limit evasion

Related Files:
- src/nse_bhavcopy/historical_sync.py: Uses fetch() for single-symbol sync.
- src/nse_bhavcopy/screener.py: Uses fetch_batch() for multi-symbol screening.
- src/data/fetcher/prices/nse_charts.py: Alternative NSE data source.
"""

import logging
import time
from typing import ClassVar

import pandas as pd
import yfinance as yf

from src.data.fetcher.prices.base import AbstractPriceFetcher

logger = logging.getLogger(__name__)


class YFinanceFetcher(AbstractPriceFetcher):
    """
    Yahoo Finance price fetcher for NSE equities.

    Design Pattern: Strategy — plugs into HistoricalSync and StockScreener
    via AbstractPriceFetcher. Coexists with NSEChartFetcher as an alternative
    data source.

    Bulk Download Strategy:
        - fetch_batch() uses yf.download() for TRUE BULK download (single HTTP
          request to Yahoo's multi-ticker endpoint) when group_by='ticker'.
        - Falls back to yf.Tickers().history() for edge cases.
        - Chunked at 50 symbols per request to stay within Yahoo's URL limits.

    Attributes:
        INTERVAL_MAP (dict): Internal timeframe codes to yfinance interval strings.
        BULK_CHUNK_SIZE (int): Max symbols per yf.download() call. Yahoo's
            multi-ticker endpoint handles ~50-100 symbols before URL length limits.
    """

    INTERVAL_MAP: ClassVar[dict[str, str]] = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "60m",
        "1d": "1d",
        "1w": "1wk",
        "1mo": "1mo",
    }

    BULK_CHUNK_SIZE: int = 50  # Yahoo multi-ticker endpoint limit

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Append .NS suffix for NSE equities if missing."""
        s = symbol.strip().upper()
        return s if s.endswith(".NS") else f"{s}.NS"

    def fetch(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "1y",
        from_date: int | None = None,
        to_date: int | None = None,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV from Yahoo Finance for a single NSE symbol.

        Uses yfinance.Ticker.history() for reliable EOD data.

        Parameters:
            symbol (str): NSE equity symbol (e.g. "TCS" or "TCS.NS").
            timeframe (str): Candle resolution. | Default "1d".
            period (str): History scope when from/to are omitted. | Default "1y".
            from_date (int | None): Start epoch timestamp.
            to_date (int | None): End epoch timestamp.

        Returns:
            pd.DataFrame: Clean OHLCV with tz-naive DatetimeIndex.
        """
        ticker_str = self._normalize_symbol(symbol)
        interval = self.INTERVAL_MAP.get(timeframe, "1d")

        try:
            ticker = yf.Ticker(ticker_str)

            if from_date is not None and to_date is not None:
                start = pd.to_datetime(from_date, unit="s")
                end = pd.to_datetime(to_date, unit="s") + pd.Timedelta(days=1)
                df = ticker.history(
                    start=start.strftime("%Y-%m-%d"),
                    end=end.strftime("%Y-%m-%d"),
                    interval=interval,
                )
            else:
                df = ticker.history(period=period, interval=interval)

            if df.empty:
                logger.warning("YFinance returned empty data for %s", ticker_str)
                return pd.DataFrame()

            # Normalize index to tz-naive to match pipeline convention
            if hasattr(df.index, "tz") and df.index.tz is not None:
                df.index = df.index.tz_convert(None)

            # Keep only standard OHLCV columns
            target_cols = ["Open", "High", "Low", "Close", "Volume"]
            available = [c for c in target_cols if c in df.columns]
            if not available:
                logger.warning("YFinance data for %s missing OHLCV columns", ticker_str)
                return pd.DataFrame()

            df = df[available].astype(float)
            df.index.name = "Date"
            return df.sort_index()

        except Exception as exc:
            logger.error("YFinance fetch failed for %s: %s", ticker_str, exc)
            return pd.DataFrame()

    def fetch_batch(
        self,
        symbols: list[str],
        timeframe: str = "1d",
        period: str = "1y",
        from_date: int | None = None,
        to_date: int | None = None,
        chunk_size: int = 50,
        rate_delay: float = 1.0,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV for multiple symbols via TRUE BULK download.

        Uses yf.download() which hits Yahoo's native multi-ticker endpoint in
        a single HTTP request per chunk. This is significantly faster than
        looping over individual Ticker objects.

        Column structure: MultiIndex where level 0 = symbol, level 1 = metric
        (Open, High, Low, Close, Volume) — matching pipeline convention.

        Parameters:
            symbols (list[str]): NSE equity symbols. | Non-empty list.
            timeframe (str): Candle resolution. | Default "1d".
            period (str): History scope. | Default "1y".
            from_date (int | None): Start epoch timestamp.
            to_date (int | None): End epoch timestamp.
            chunk_size (int): Symbols per bulk request. | Default 50 (Yahoo limit).
            rate_delay (float): Seconds between chunks. | Default 1.0.

        Returns:
            pd.DataFrame: MultiIndex columns (symbol, metric), tz-naive DatetimeIndex.

        Raises:
            None

        Notes:
            yf.download() with group_by='ticker' returns:
                Columns: MultiIndex([(AAPL, Open), (AAPL, High), ...])
            We normalize to our convention: level 0 = symbol, level 1 = metric.
        """
        interval = self.INTERVAL_MAP.get(timeframe, "1d")
        all_dfs: list[pd.DataFrame] = []

        # Normalize all symbols
        ns_symbols = [self._normalize_symbol(s) for s in symbols]

        for i in range(0, len(ns_symbols), chunk_size):
            chunk = ns_symbols[i : i + chunk_size]
            chunk_str = " ".join(chunk)

            logger.info(
                "YFinance BULK download chunk %d-%d of %d (%d symbols)",
                i + 1,
                i + len(chunk),
                len(ns_symbols),
                len(chunk),
            )

            try:
                # === TRUE BULK: yf.download() hits Yahoo multi-ticker endpoint ===
                download_kwargs: dict = {
                    "tickers": chunk_str,
                    "interval": interval,
                    "group_by": "ticker",
                    "auto_adjust": False,
                    "progress": False,
                    "threads": False,  # FIX: threads=True causes race conditions in yfinance 0.2.x
                    "actions": False,  # FIX: exclude Dividends/Stock Splits columns
                }

                if from_date is not None and to_date is not None:
                    start = pd.to_datetime(from_date, unit="s")
                    end = pd.to_datetime(to_date, unit="s") + pd.Timedelta(days=1)
                    download_kwargs["start"] = start.strftime("%Y-%m-%d")
                    download_kwargs["end"] = end.strftime("%Y-%m-%d")
                else:
                    download_kwargs["period"] = period

                df = yf.download(**download_kwargs)

                if df.empty:
                    logger.warning("YFinance bulk returned empty for chunk %s", chunk)
                    continue

                # yfinance 0.2.66 returns MultiIndex with named levels ['Ticker', 'Price']
                # where level 0 = ticker, level 1 = metric (Open, High, Low, Close, Adj Close, Volume)
                if isinstance(df.columns, pd.MultiIndex):
                    # Extract level values regardless of level names
                    tickers = df.columns.get_level_values(0)
                    metrics = df.columns.get_level_values(1)

                    # Keep only OHLCV metrics — drop Adj Close, Dividends, Splits, etc.
                    ohlcv_metrics = {"Open", "High", "Low", "Close", "Volume"}
                    mask = metrics.isin(ohlcv_metrics)
                    df = df.loc[:, mask]

                    if df.empty:
                        logger.warning(
                            "YFinance bulk chunk %s: no OHLCV columns after filter",
                            chunk,
                        )
                        continue

                    # Rebuild MultiIndex with our convention: level 0 = symbol, level 1 = metric
                    # This ensures consistent column names even if yfinance changes its level names
                    new_cols = pd.MultiIndex.from_tuples(
                        [(str(ticker), str(metric)) for ticker, metric in df.columns],
                        names=["symbol", "metric"],
                    )
                    df.columns = new_cols

                    # Sort for consistency
                    df = df.sort_index(axis=1)
                else:
                    # Single symbol fallback — wrap defensively
                    if len(chunk) == 1:
                        df.columns = pd.MultiIndex.from_product(
                            [chunk, df.columns],
                            names=["symbol", "metric"],
                        )
                    else:
                        logger.warning(
                            "Unexpected flat columns from yf.download for multi-ticker chunk %s, skipping",
                            chunk,
                        )
                        continue

                # Normalize timezone to tz-naive
                if hasattr(df.index, "tz") and df.index.tz is not None:
                    df.index = df.index.tz_convert(None)
                df.index.name = "Date"

                all_dfs.append(df)
                logger.info(
                    "Bulk chunk %d-%d: fetched %d rows x %d columns",
                    i + 1,
                    i + len(chunk),
                    len(df),
                    len(df.columns),
                )

            except Exception as exc:
                logger.error(
                    "YFinance bulk download failed for chunk %s: %s", chunk, exc
                )
                # Fallback: try sequential per-symbol for this chunk
                logger.info("Falling back to sequential fetch for failed chunk...")
                for sym in chunk:
                    try:
                        df_single = self.fetch(
                            sym,
                            timeframe=timeframe,
                            period=period,
                            from_date=from_date,
                            to_date=to_date,
                        )
                        if not df_single.empty:
                            # fetch() already returns flat OHLCV columns
                            df_single.columns = pd.MultiIndex.from_product(
                                [[sym], df_single.columns],
                                names=["symbol", "metric"],
                            )
                            all_dfs.append(df_single)
                    except Exception as exc2:
                        logger.error("Sequential fallback failed for %s: %s", sym, exc2)

            # Polite delay between bulk chunks to avoid rate limiting
            if i + chunk_size < len(ns_symbols):
                time.sleep(rate_delay)

        if not all_dfs:
            return pd.DataFrame()

        combined = pd.concat(all_dfs, axis=1)
        # Deduplicate columns in case of overlap between chunks (e.g. fallback re-fetched same symbol)
        combined = combined.loc[:, ~combined.columns.duplicated()]
        return combined.sort_index()
