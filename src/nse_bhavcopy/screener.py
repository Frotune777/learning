"""
File: src/nse_bhavcopy/screener.py
Purpose: Replicate stock trend, CAR rating, and Bottom Out swing trading.

Dependencies:
External:
- pandas>=2.2.3: Used for loading dataframes and time-series calculations
- numpy>=2.4.6: Numerical and NaN utilities
Internal:
- src.data.fetcher.prices.yfinance_fetcher: [YFinanceFetcher]

Key Components:
Classes:
- StockScreener: Performs stock calculations (Trend, CAR, Bottom Out).
Functions:
- None

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- [ ] [LOW] Add configurable window lengths for DMAs via config (2h)
- [ ] [MEDIUM] Implement sqlite storage backend for processed outputs (3h)

Related Files:
- lerarning.py: Pipeline orchestrator executing the screener.
- tests/test_screener.py: Unit tests covering calculations with 100% mocked data.
"""

import logging
import os
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from src.data.fetcher.prices.yfinance_fetcher import YFinanceFetcher

# Configure logger standard in compliance with Rule #011
LOGGER: logging.Logger = logging.getLogger(__name__)


class StockScreener:
    """
    Class responsible for replicating stock Trend, CAR, and Bottom Out analytics.

    Design Pattern: Strategy - Implements technical screening calculations.

    Attributes:
        processed_dir (str): Output folder for processed stock CSVs. | "data/processed"
        bottom_out_tolerance (float): Tolerance for today low ≈ 20D low. | 0.5
        bounce_buffer (float): Min bounce pct for advanced filter. | 1.0

    Public Methods:
        - screen_stocks(top_250_path, date_obj): Execute and write outputs.

    Private Methods:
        - _get_ns_ticker(symbol): Suffixes '.NS' helper.
        - _fetch_history(tickers, today_prices, date_obj): Fetch batches.
        - _calculate_car_rating(df_ticker): Determine slope checks.
        - _calculate_bottom_out(df_ticker): Calculate 20D low bounce details.

    Usage Flow:
        1. Instantiate StockScreener with processed folder and tolerance configs.
        2. Call screen_stocks with top 250 Bhavcopy sheet path and target date.
        3. Retrieve multiple saved files final_list, swing_list, super_list CSV.

    State Management:
        - Valid states: Initialized, Running, Completed
        - State transitions: Initialized -> Running -> Completed.

    Thread Safety: Yes - Computations are self-contained and stateless.

    Dependencies:
        External: pandas, numpy, yfinance (via YFinanceFetcher)
        Internal: YFinanceFetcher
    """

    def __init__(
        self,
        processed_dir: str = "data/processed",
        bottom_out_tolerance: float = 0.5,
        bounce_buffer: float = 1.0,
    ) -> None:
        """
        Initialize the StockScreener with processed output directories.

        Logic:
            Step 1: Save output directories and swing parameters.
            Step 2: Create directory trees recursively if they do not exist.

        Parameters:
            processed_dir (str): Target directory for saving results. | Valid path.
            bottom_out_tolerance (float): Tolerance percentage for floor low. | >= 0.0
            bounce_buffer (float): Minimum percentage recovery buffer. | >= 0.0

        Returns:
            None: Void constructor return.

        Raises:
            OSError: If directory creation fails.

        Example:
            >>> screener = StockScreener("data/processed", 0.5, 1.0)

        Performance:
            Time Complexity: O(1) [Directory setup check]
            Space Complexity: O(1) [Minimal fields]

        Edge Cases Handled:
            - processed_dir exists (handled gracefully).
        """
        self.processed_dir: str = processed_dir
        self.bottom_out_tolerance: float = bottom_out_tolerance
        self.bounce_buffer: float = bounce_buffer
        os.makedirs(self.processed_dir, exist_ok=True)
        LOGGER.info(
            "StockScreener initialized in: %s (tol: %.2f%%, buf: %.2f%%)",
            self.processed_dir,
            self.bottom_out_tolerance,
            self.bounce_buffer,
        )

    def _get_ns_ticker(self, symbol: str) -> str:
        """
        Normalize standard stock symbols to Yahoo Finance NSE ticker format.

        Logic:
            Step 1: Clean spaces and convert to uppercase.
            Step 2: Append '.NS' suffix for NSE India symbols.

        Parameters:
            symbol (str): Ticker symbol to format. | Non-empty string.

        Returns:
            str: Normalized ticker symbol string.

        Raises:
            None

        Example:
            >>> screener = StockScreener()
            >>> print(screener._get_ns_ticker("TCS"))
            TCS.NS

        Performance:
            Time Complexity: O(1) [Quick string manipulation]
            Space Complexity: O(1) [Single string]

        Edge Cases Handled:
            - Symbol already contains suffix (handles cleanly).
        """
        clean_symbol: str = str(symbol).strip().upper()
        if not clean_symbol.endswith(".NS"):
            return f"{clean_symbol}.NS"
        return clean_symbol

    def _fetch_history(
        self,
        tickers: list[str],
        today_prices: dict[str, float] | None = None,
        date_obj: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Download historical daily data for list of tickers via YFinanceFetcher.

        Parameters:
            tickers (list[str]): List of NSE stock tickers (with .NS suffix).
            today_prices (dict[str, float] | None): Close prices for incremental.
            date_obj (datetime | None): Target datetime for incremental.

        Returns:
            pd.DataFrame: Multi-index DataFrame with historical prices.

        Raises:
            ValueError: If downloading returns completely empty dataframe.
        """
        LOGGER.info("Retrieving historical prices for %d symbols...", len(tickers))

        # We load from data/historical/1d/ which matches HistoricalSync
        cache_dir: str = os.path.join(self.processed_dir, "1d")
        os.makedirs(cache_dir, exist_ok=True)

        fetcher = YFinanceFetcher()

        cached_dfs: list[pd.DataFrame] = []
        tickers_to_download: list[str] = []

        for ticker in tickers:
            symbol = ticker.replace(".NS", "").upper()
            cache_path = os.path.join(cache_dir, f"{symbol}.parquet")
            if os.path.exists(cache_path):
                try:
                    cached_df: pd.DataFrame = pd.read_parquet(cache_path)
                    if not cached_df.empty:
                        # Perform incremental Daily CRUD if we have today's price
                        if today_prices and date_obj and ticker in today_prices:
                            # Normalize index to tz-naive
                            if cached_df.index.tz is not None:
                                cached_df.index = cached_df.index.tz_convert(None)
                            else:
                                cached_df.index = pd.to_datetime(cached_df.index)

                            target_date = (
                                pd.Timestamp(date_obj).normalize().tz_localize(None)
                            )
                            if target_date not in cached_df.index:
                                price = today_prices[ticker]
                                new_row = pd.DataFrame(
                                    {
                                        "Open": [price],
                                        "High": [price],
                                        "Low": [price],
                                        "Close": [price],
                                        "Volume": [0.0],
                                    },
                                    index=[target_date],
                                )
                                cached_df = pd.concat([cached_df, new_row])
                                cached_df = cached_df.sort_index()
                                cached_df = cached_df[
                                    ~cached_df.index.duplicated(keep="last")
                                ]

                                # Enrich with TA indicators before saving
                                from src.nse_bhavcopy.ta_indicators import (
                                    add_ta_indicators,
                                )

                                cached_df = add_ta_indicators(cached_df)
                                cached_df.to_parquet(cache_path)

                        # Reconstruct MultiIndex structure expected downstream
                        req_cols = ["Open", "High", "Low", "Close", "Volume"]
                        existing_cols = [c for c in req_cols if c in cached_df.columns]

                        df_slice = cached_df[existing_cols].copy()
                        df_slice.columns = pd.MultiIndex.from_product(
                            [[ticker], existing_cols]
                        )
                        cached_dfs.append(df_slice)
                        continue
                except Exception as ex:
                    LOGGER.warning(
                        "Failed to read/update cache for %s: %s",
                        ticker,
                        ex,
                    )

            tickers_to_download.append(ticker)

        LOGGER.info(
            "Cache Status: %d loaded from cache, %d scheduled for download.",
            len(cached_dfs),
            len(tickers_to_download),
        )

        if tickers_to_download:
            # Batch download missing tickers via YFinanceFetcher
            df_batch: pd.DataFrame = fetcher.fetch_batch(
                tickers_to_download,
                timeframe="1d",
                period="1y",
                chunk_size=15,
                rate_delay=3.0,
            )

            if not df_batch.empty:
                # Save each ticker's slice to individual cache files
                for ticker in tickers_to_download:
                    if ticker in df_batch.columns.get_level_values(0):
                        df_single: pd.DataFrame = df_batch[ticker].copy()
                        try:
                            symbol = ticker.replace(".NS", "").upper()
                            cache_path = os.path.join(cache_dir, f"{symbol}.parquet")

                            # Enrich with TA indicators before saving
                            from src.nse_bhavcopy.ta_indicators import (
                                add_ta_indicators,
                            )

                            df_single = add_ta_indicators(df_single)
                            df_single.to_parquet(cache_path)
                        except Exception as ex:
                            LOGGER.warning(
                                "Failed to save cache for %s: %s", ticker, ex
                            )

                # Reconstruct MultiIndex structure with only OHLCV columns
                req_cols = ["Open", "High", "Low", "Close", "Volume"]
                present_tickers = list(df_batch.columns.get_level_values(0).unique())
                sliced_dfs = []
                for t in present_tickers:
                    df_t = df_batch[t].copy()
                    existing_cols = [c for c in req_cols if c in df_t.columns]
                    df_t = df_t[existing_cols]
                    df_t.columns = pd.MultiIndex.from_product([[t], existing_cols])
                    sliced_dfs.append(df_t)

                if sliced_dfs:
                    df_batch_sliced = pd.concat(sliced_dfs, axis=1)
                    cached_dfs.append(df_batch_sliced)

        all_dfs: list[pd.DataFrame] = cached_dfs
        if not all_dfs:
            LOGGER.error("No historical data fetched or loaded from cache.")
            raise ValueError("YFinance returned empty history.")

        df: pd.DataFrame = pd.concat(all_dfs, axis=1)
        # Deduplicate columns in case a ticker was both cached and fetched
        df = df.loc[:, ~df.columns.duplicated()]
        return df

    def _calculate_car_rating(self, df_ticker: pd.DataFrame) -> str:
        """
        Compute Advanced Cumulative Average Rule (CAR) rating for a stock.

        Logic:
            Step 1: Check if dataframe has required rows/columns and non-NaN values.
            Step 2: Find the 52-week High price and its earliest index date.
            Step 3: Slice daily Close prices starting from the high date.
            Step 4: If sliced trading history is less than 10 days,
                    return Short History.
            Step 5: Generate Expanding Mean (running cumulative average) of slices.
            Step 6: Retrieve last 10 cumulative average values.
            Step 7: Check if averages are strictly increasing over the 10 days.
            Step 8: Return Buy/Average Out if increasing, else Avoid/Hold.

        Parameters:
            df_ticker (pd.DataFrame): Daily OHLCV data for ticker. | Must have columns.

        Returns:
            str: CAR Rating output string.

        Raises:
            None

        Example:
            >>> screener = StockScreener()
            >>> # rating = screener._calculate_car_rating(df_ticker)

        Performance:
            Time Complexity: O(W) [Linear operations over slice history size W]
            Space Complexity: O(W) [Expanding mean series size W]

        Edge Cases Handled:
            - Empty data or missing high/close columns (returns Avoid/Hold).
            - Short trading history (returns Short History).
            - All close values equal or decreasing (returns Avoid/Hold).
        """
        if df_ticker.empty or "High" not in df_ticker or "Close" not in df_ticker:
            return "Avoid/Hold"

        clean_df = df_ticker.dropna(subset=["High", "Close"])
        if len(clean_df) < 10:
            return "Short History"

        # Step 2: 52-week High and High Date
        high_idx: Any = clean_df["High"].idxmax()

        # Step 3: Slice close prices from high date to today
        prices: pd.Series = clean_df.loc[high_idx:, "Close"]
        count_rows: int = len(prices)

        # Step 4: Minimum 10 trading days requirement
        if count_rows < 10:
            return "Short History"

        # Step 5: Expanding Mean representing expanding running cumulative average
        cum_avg: pd.Series = prices.expanding().mean()

        # Step 6: Get last 10 elements of cumulative average
        last_10: list[float] = cum_avg.tail(10).tolist()

        # Step 7: Check if averages are strictly increasing (9 daily consecutive gains)
        check: int = sum(1 for i in range(1, 10) if last_10[i] > last_10[i - 1])

        # Step 8: Return rating based on rules
        if check == 9:
            return "Buy/Average Out"
        return "Avoid/Hold"

    def _calculate_bottom_out(self, df_ticker: pd.DataFrame) -> dict[str, Any]:
        """
        Compute Bottom Out Hunting swing trading metrics for a stock.

        This identifies stocks that tested their 20-day low and bounced.

        Logic:
            Step 1: Initialize results dictionary with default values.
            Step 2: Check if DataFrame is empty or missing High/Low/Close columns.
            Step 3: Drop NaNs and check if history has at least 20 trading days.
            Step 4: Calculate 20-day High, 20-day Low, Today's Low, and CMP.
            Step 5: Check if Today's Low is within bottom_out_tolerance of 20D Low.
            Step 6: Check if Close is greater than Today's Low (bounced).
            Step 7: Check if the bounce exceeds the bounce_buffer percentage.
            Step 8: Construct swing advice and signals based on these triggers.

        Parameters:
            df_ticker (pd.DataFrame): Daily OHLCV data. | Must have columns.

        Returns:
            dict[str, Any]: Calculated metrics and signal results.
            {
                '20D_HIGH': float,
                '20D_LOW': float,
                'TODAY_LOW': float,
                'GTT_TRIGGER': float,
                'BOTTOM_OUT_STATUS': str,
                'SWING_ADVICE': str
            }

        Raises:
            None

        Example:
            >>> import pandas as pd
            >>> df = pd.DataFrame({
            ...     "High": [120.0]*20, "Low": [100.0]*20, "Close": [105.0]*20
            ... })
            >>> screener = StockScreener()
            >>> res = screener._calculate_bottom_out(df)
            >>> print(res["BOTTOM_OUT_STATUS"])
            Start GTT

        Performance:
            Time Complexity: O(1) [Calculated on the last 20 daily records]
            Space Complexity: O(1) [Static local dictionary allocation]

        Edge Cases Handled:
            - Insufficient history length (< 20 days) returns Short History.
            - Invalid/negative prices and zero/negative low returns Invalid Low.
            - Weak bounce returns Start GTT (Basic) recommendation.

        TODO:
            - None

        Notes:
            The GTT trigger is set at the 20-day high to represent breakout entry.
        """
        result: dict[str, Any] = {
            "20D_HIGH": np.nan,
            "20D_LOW": np.nan,
            "TODAY_LOW": np.nan,
            "GTT_TRIGGER": np.nan,
            "BOTTOM_OUT_STATUS": "No Data",
            "SWING_ADVICE": "Wait",
        }

        if df_ticker.empty or not all(
            col in df_ticker.columns for col in ["High", "Low", "Close"]
        ):
            result["BOTTOM_OUT_STATUS"] = "No Data"
            return result

        clean_df = df_ticker.dropna(subset=["High", "Low", "Close"])
        if len(clean_df) < 20:
            result["BOTTOM_OUT_STATUS"] = "Short History"
            return result

        # Step 4: Calculate 20-day metrics
        last_20 = clean_df.tail(20)
        high_20d: float = float(last_20["High"].max())
        low_20d: float = float(last_20["Low"].min())
        today_low: float = float(clean_df["Low"].iloc[-1])
        cmp: float = float(clean_df["Close"].iloc[-1])

        result["20D_HIGH"] = high_20d
        result["20D_LOW"] = low_20d
        result["TODAY_LOW"] = today_low
        result["GTT_TRIGGER"] = high_20d

        # Step 5: Floor Test
        if low_20d <= 0:
            result["BOTTOM_OUT_STATUS"] = "Invalid Low"
            return result

        low_diff_pct: float = abs(today_low - low_20d) / low_20d * 100.0
        floor_tested: bool = low_diff_pct <= self.bottom_out_tolerance

        # Step 6: Bounce Test
        bounced: bool = cmp > today_low

        # Step 7: Advanced Bounce
        bounce_pct: float = ((cmp - low_20d) / low_20d * 100.0) if low_20d > 0 else 0.0
        meaningful_bounce: bool = bounce_pct >= self.bounce_buffer

        # Step 8: Decision Logic
        if not floor_tested:
            result["BOTTOM_OUT_STATUS"] = "Do not start GTT"
            result["SWING_ADVICE"] = "Wait for best time"
        elif not bounced:
            result["BOTTOM_OUT_STATUS"] = "Do not start GTT"
            result["SWING_ADVICE"] = "No bounce — avoid"
        elif not meaningful_bounce:
            result["BOTTOM_OUT_STATUS"] = "Start GTT (Basic)"
            result["SWING_ADVICE"] = (
                f"Place GTT at {high_20d:.2f} | Weak bounce ({bounce_pct:.2f}%)"
            )
        else:
            result["BOTTOM_OUT_STATUS"] = "Start GTT"
            result["SWING_ADVICE"] = (
                f"Place GTT Buy at {high_20d:.2f} | "
                f"Stop below {today_low:.2f} | "
                f"Bounce: {bounce_pct:.2f}%"
            )

        return result

    def screen_stocks(self, top_250_path: str, date_obj: datetime) -> str:
        """
        Execute stock screener computations and output final CSV lists.

        Logic:
            Step 1: Load top 250 CSV file and extract symbols list.
            Step 2: Generate formatted NSE tickers and batch download history.
            Step 3: Loop through all symbols to extract indicators (DMA, CAR).
            Step 4: Determine Bull/Bear trend status and difference values.
            Step 5: Assemble fully analyzed pandas DataFrame.
            Step 6: Write complete analyzed results to processed directory.
            Step 7: Filter Trend Status='In Bull Run' and CAR='Buy/Average Out'.
            Step 8: Sort final list by turnover descending and write output.

        Parameters:
            top_250_path (str): Path to top 250 processed CSV. | Must exist.
            date_obj (datetime): Current Date of pipeline execution. | Valid past date.

        Returns:
            str: Path to the generated filtered final list CSV.

        Raises:
            FileNotFoundError: If input top_250_path is missing.
            KeyError: If columns are missing from source CSV.

        Example:
            >>> screener = StockScreener()
            >>> # path = screener.screen_stocks(
            >>> #     "data/processed/top_250_20260526.csv", date
            >>> # )

        Performance:
            Time Complexity: O(N * W) [Processing W history for N=250 symbols]
            Space Complexity: O(N) [Temporary tables storage]

        Edge Cases Handled:
            - Missing symbols or data failures (records marked TICKER NOT FOUND).
            - Empty final lists (returns CSV with empty headers).
        """
        if not os.path.exists(top_250_path):
            LOGGER.error("Top 250 source file not found: %s", top_250_path)
            raise FileNotFoundError(f"Source file not found: {top_250_path}")

        # Step 1: Load symbols
        df_top: pd.DataFrame = pd.read_csv(top_250_path)
        if "SYMBOL" not in df_top.columns or "TURNOVER" not in df_top.columns:
            raise KeyError("Source CSV must contain SYMBOL and TURNOVER columns.")

        symbols: list[str] = df_top["SYMBOL"].astype(str).tolist()
        ns_tickers: list[str] = [self._get_ns_ticker(s) for s in symbols]

        # Extract today's prices from top 250 Bhavcopy for incremental caching
        today_prices: dict[str, float] = {}
        for _, row in df_top.iterrows():
            sym = str(row["SYMBOL"])
            ns_tick = self._get_ns_ticker(sym)
            if "CLOSE" in row:
                today_prices[ns_tick] = float(row["CLOSE"])

        # Step 2: Batch download historical data
        try:
            df_history: pd.DataFrame = self._fetch_history(
                ns_tickers, today_prices=today_prices, date_obj=date_obj
            )
        except Exception as e:
            LOGGER.critical("Failed to fetch historical data: %s", str(e))
            raise

        analyzed_records: list[dict[str, Any]] = []

        # Step 3: Loop through all symbols
        for symbol in symbols:
            ns_ticker: str = self._get_ns_ticker(symbol)
            turnover: float = float(
                df_top.loc[df_top["SYMBOL"] == symbol, "TURNOVER"].values[0]
            )

            # Match symbol from level 0 of multi-index columns
            has_ticker: bool = False
            if isinstance(df_history.columns, pd.MultiIndex):
                has_ticker = ns_ticker in df_history.columns.get_level_values(0)

            if not has_ticker:
                LOGGER.warning("Ticker %s not found in downloaded data", ns_ticker)
                analyzed_records.append(
                    {
                        "SYMBOL": symbol,
                        "TURNOVER": turnover,
                        "PREVIOUS_CLOSE": np.nan,
                        "CMP": np.nan,
                        "DMA_50": np.nan,
                        "DMA_100": np.nan,
                        "DMA_200": np.nan,
                        "DIFF_200_DMA": np.nan,
                        "TREND_STATUS": "TICKER NOT FOUND",
                        "CAR_RATING": "TICKER NOT FOUND",
                        "20D_HIGH": np.nan,
                        "20D_LOW": np.nan,
                        "TODAY_LOW": np.nan,
                        "GTT_TRIGGER": np.nan,
                        "BOTTOM_OUT_STATUS": "TICKER NOT FOUND",
                        "SWING_ADVICE": "No data available",
                        "RSI_14": np.nan,
                        "TECH_SCORE": np.nan,
                        "TECH_RATING": "TICKER NOT FOUND",
                    }
                )
                continue

            # Extract daily data frame for single ticker
            df_ticker: pd.DataFrame = pd.DataFrame()
            try:
                df_ticker = df_history[ns_ticker].copy()
                if "Close" in df_ticker.columns:
                    df_ticker = df_ticker.dropna(subset=["Close"])
            except KeyError:
                pass

            if df_ticker.empty or len(df_ticker) < 2:
                analyzed_records.append(
                    {
                        "SYMBOL": symbol,
                        "TURNOVER": turnover,
                        "PREVIOUS_CLOSE": np.nan,
                        "CMP": np.nan,
                        "DMA_50": np.nan,
                        "DMA_100": np.nan,
                        "DMA_200": np.nan,
                        "DIFF_200_DMA": np.nan,
                        "TREND_STATUS": "TICKER NOT FOUND",
                        "CAR_RATING": "TICKER NOT FOUND",
                        "20D_HIGH": np.nan,
                        "20D_LOW": np.nan,
                        "TODAY_LOW": np.nan,
                        "GTT_TRIGGER": np.nan,
                        "BOTTOM_OUT_STATUS": "TICKER NOT FOUND",
                        "SWING_ADVICE": "No data available",
                        "RSI_14": np.nan,
                        "TECH_SCORE": np.nan,
                        "TECH_RATING": "TICKER NOT FOUND",
                    }
                )
                continue

            # CMP is the last close price
            cmp: float = float(df_ticker["Close"].iloc[-1])
            # Previous close is close of second to last day
            prev_close: float = float(df_ticker["Close"].iloc[-2])

            # DMA calculations over trading days with minimum history guards
            close_series: pd.Series = df_ticker["Close"].dropna()
            available_days: int = len(close_series)

            dma_50: float = (
                float(close_series.tail(50).mean()) if available_days >= 50 else np.nan
            )
            dma_100: float = (
                float(close_series.tail(100).mean())
                if available_days >= 100
                else np.nan
            )
            dma_200: float = (
                float(close_series.tail(200).mean())
                if available_days >= 200
                else np.nan
            )

            # Percentage difference from 200 DMA
            diff_200_dma: float = 0.0
            if not pd.isna(dma_200) and dma_200 > 0:
                diff_200_dma = ((cmp - dma_200) * 100.0) / dma_200
            else:
                diff_200_dma = np.nan

            # Trend Status matching with Insufficient History check
            trend_status: str = "Unconfirmed"
            if any(pd.isna(v) for v in [dma_50, dma_100, dma_200]):
                trend_status = "Insufficient History"
            else:
                if cmp > dma_50 and cmp > dma_100 and cmp > dma_200:
                    if 0.01 <= diff_200_dma <= 10.0:
                        trend_status = "In Bull Run"
                elif cmp < dma_50 and cmp < dma_100 and cmp < dma_200:
                    if -10.0 <= diff_200_dma <= -0.01:
                        trend_status = "In Bear Run"

            # CAR Rating calculations
            car_rating: str = self._calculate_car_rating(df_ticker)

            # Bottom Out calculations
            bottom_out: dict[str, Any] = self._calculate_bottom_out(df_ticker)

            # Calculate TA-Lib indicators and score on the fly
            from src.nse_bhavcopy.ta_indicators import (
                add_ta_indicators,
                calculate_technical_score,
            )

            df_ticker = add_ta_indicators(df_ticker)
            latest_row = df_ticker.iloc[-1]
            ta_info = calculate_technical_score(latest_row)
            rsi_val = latest_row.get("RSI_14", np.nan)
            tech_score = ta_info["score"]
            tech_rating = ta_info["rating"]

            analyzed_records.append(
                {
                    "SYMBOL": symbol,
                    "TURNOVER": turnover,
                    "PREVIOUS_CLOSE": prev_close,
                    "CMP": cmp,
                    "DMA_50": dma_50,
                    "DMA_100": dma_100,
                    "DMA_200": dma_200,
                    "DIFF_200_DMA": diff_200_dma,
                    "TREND_STATUS": trend_status,
                    "CAR_RATING": car_rating,
                    "20D_HIGH": bottom_out["20D_HIGH"],
                    "20D_LOW": bottom_out["20D_LOW"],
                    "TODAY_LOW": bottom_out["TODAY_LOW"],
                    "GTT_TRIGGER": bottom_out["GTT_TRIGGER"],
                    "BOTTOM_OUT_STATUS": bottom_out["BOTTOM_OUT_STATUS"],
                    "SWING_ADVICE": bottom_out["SWING_ADVICE"],
                    "RSI_14": rsi_val,
                    "TECH_SCORE": tech_score,
                    "TECH_RATING": tech_rating,
                }
            )

        # Step 5: Save complete analyzed dataset
        df_analyzed: pd.DataFrame = pd.DataFrame(analyzed_records)
        date_str: str = date_obj.strftime("%Y%m%d")
        analyzed_filename: str = f"top_250_analyzed_{date_str}.csv"
        analyzed_filepath: str = os.path.join(self.processed_dir, analyzed_filename)
        df_analyzed.to_csv(analyzed_filepath, index=False)
        LOGGER.info("Complete analyzed dataset saved at: %s", analyzed_filepath)

        # Filter A: Original Bull Run + CAR Buy rating
        df_filtered_a: pd.DataFrame = df_analyzed[
            (df_analyzed["TREND_STATUS"] == "In Bull Run")
            & (df_analyzed["CAR_RATING"] == "Buy/Average Out")
        ].copy()

        df_filtered_a = df_filtered_a.sort_values(by="TURNOVER", ascending=False)

        final_list_df: pd.DataFrame = df_filtered_a[
            [
                "SYMBOL",
                "TURNOVER",
                "PREVIOUS_CLOSE",
                "CMP",
                "DIFF_200_DMA",
                "CAR_RATING",
                "RSI_14",
                "TECH_SCORE",
                "TECH_RATING",
            ]
        ].copy()

        final_list_df = final_list_df.rename(
            columns={
                "SYMBOL": "NSE Code",
                "TURNOVER": "Volume",
                "PREVIOUS_CLOSE": "Previous Close",
                "CMP": "CMP",
                "DIFF_200_DMA": "Difference from 200 DMA",
                "CAR_RATING": "CAR",
                "RSI_14": "RSI",
                "TECH_SCORE": "Tech Score",
                "TECH_RATING": "Tech Rating",
            }
        )

        final_filename: str = f"final_list_{date_str}.csv"
        final_filepath: str = os.path.join(self.processed_dir, final_filename)
        final_list_df.to_csv(final_filepath, index=False)

        LOGGER.info(
            "Final target list (Filter A) saved at: %s (%d records)",
            final_filepath,
            len(final_list_df),
        )

        # Filter B: Bottom Out Hunting — Start GTT signals
        df_bottom_out: pd.DataFrame = df_analyzed[
            df_analyzed["BOTTOM_OUT_STATUS"].isin(["Start GTT", "Start GTT (Basic)"])
        ].copy()

        final_b_df: pd.DataFrame = df_bottom_out[
            [
                "SYMBOL",
                "TURNOVER",
                "CMP",
                "20D_HIGH",
                "20D_LOW",
                "TODAY_LOW",
                "GTT_TRIGGER",
                "BOTTOM_OUT_STATUS",
                "SWING_ADVICE",
                "RSI_14",
                "TECH_SCORE",
            ]
        ].copy()

        final_b_df = final_b_df.rename(
            columns={
                "SYMBOL": "NSE Code",
                "TURNOVER": "Volume",
                "CMP": "CMP",
                "20D_HIGH": "20 Day High",
                "20D_LOW": "20 Day Low",
                "TODAY_LOW": "Today Low",
                "GTT_TRIGGER": "GTT Trigger Price",
                "BOTTOM_OUT_STATUS": "Swing Signal",
                "SWING_ADVICE": "Action",
                "RSI_14": "RSI",
                "TECH_SCORE": "Tech Score",
            }
        )
        final_b_df = final_b_df.sort_values(by="Volume", ascending=False)

        final_b_filename: str = f"swing_list_{date_str}.csv"
        final_b_filepath: str = os.path.join(self.processed_dir, final_b_filename)
        final_b_df.to_csv(final_b_filepath, index=False)

        LOGGER.info(
            "Swing trading list (Filter B) saved at: %s (%d records)",
            final_b_filepath,
            len(final_b_df),
        )

        # Filter C: COMBINED — Bull Run + Buy CAR + Start GTT (The Holy Grail)
        df_combined: pd.DataFrame = df_analyzed[
            (df_analyzed["TREND_STATUS"] == "In Bull Run")
            & (df_analyzed["CAR_RATING"] == "Buy/Average Out")
            & (df_analyzed["BOTTOM_OUT_STATUS"] == "Start GTT")
        ].copy()

        final_c_df: pd.DataFrame = df_combined[
            [
                "SYMBOL",
                "TURNOVER",
                "CMP",
                "DIFF_200_DMA",
                "CAR_RATING",
                "RSI_14",
                "TECH_SCORE",
                "20D_HIGH",
                "20D_LOW",
                "TODAY_LOW",
                "GTT_TRIGGER",
                "SWING_ADVICE",
            ]
        ].copy()

        final_c_df = final_c_df.rename(
            columns={
                "SYMBOL": "NSE Code",
                "TURNOVER": "Volume",
                "CMP": "CMP",
                "DIFF_200_DMA": "Diff 200 DMA",
                "CAR_RATING": "CAR",
                "RSI_14": "RSI",
                "TECH_SCORE": "Tech Score",
                "20D_HIGH": "20 Day High",
                "20D_LOW": "20 Day Low",
                "TODAY_LOW": "Today Low",
                "GTT_TRIGGER": "GTT Trigger",
                "SWING_ADVICE": "Action",
            }
        )
        final_c_df = final_c_df.sort_values(by="Volume", ascending=False)

        final_c_filename: str = f"super_list_{date_str}.csv"
        final_c_filepath: str = os.path.join(self.processed_dir, final_c_filename)
        final_c_df.to_csv(final_c_filepath, index=False)

        LOGGER.info(
            "SUPER combined list (Filter C) saved at: %s (%d records)",
            final_c_filepath,
            len(final_c_df),
        )

        return final_c_filepath
