"""
File: src/nse_bhavcopy/screener.py
Purpose: Replicate Google Finance stock trend, Cumulative Average Rule (CAR),
         AND Bottom Out Hunting swing trading analytics.

Dependencies:
External:
- pandas>=2.2.3: Used for loading dataframes and time-series calculations
- numpy>=2.4.6: Numerical and NaN utilities
- requests>=2.32.3: HTTP requests for NSE data
Internal:
- nse_data_fetcher: Reliable multi-source data fetcher (NSE API + yfinance fallback)

Key Components:
Classes:
- StockScreener: Performs stock calculations (DMA, Trend, CAR, Bottom Out) and
  saves results.

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- [ ] [LOW] Add configurable window lengths for DMAs via config (2h)
- [ ] [MEDIUM] Implement sqlite storage backend for processed outputs (3h)
- [ ] [HIGH] Add local disk cache for yfinance data to avoid re-downloads (4h)

Related Files:
- lerarning.py: Pipeline orchestrator executing the screener.
- nse_data_fetcher.py: Multi-source data fetcher (NSE API + yfinance fallback)
- tests/test_screener.py: Unit tests covering calculations with 100% mocked data.
"""

import logging
import os
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

# Use our reliable data fetcher instead of direct yfinance
from src.nse_bhavcopy.nse_data_fetcher import NSEDataFetcher

# Configure logger standard in compliance with Rule #011
LOGGER: logging.Logger = logging.getLogger(__name__)


class StockScreener:
    """
    Class responsible for replicating Google Finance sheet analysis locally,
    INCLUDING the Bottom Out Hunting swing trading method.

    Design Pattern: Strategy - Implements technical screening calculations.

    New Features (2026-05-27):
    - Bottom Out Hunting: Identifies stocks that tested 20-day low and bounced
    - GTT Trigger Price: 20-day high for swing entry
    - Swing Status: "Start GTT" or "Do not start GTT"
    - Advanced Filter: Requires meaningful bounce above 20-day low
    - Uses NSEDataFetcher for reliable data (NSE API + yfinance fallback)
    - Historical data caching to reduce API calls
    - Fixed single-ticker yfinance MultiIndex handling
    - Fixed MultiIndex ticker presence check
    - DMA minimum history guards

    Attributes:
        processed_dir (str): Directory containing cleaned and processed stock CSVs.
        cache_dir (str): Directory for caching historical data.
        bottom_out_tolerance (float): Tolerance % for Today Low ≈ 20D Low.
        bounce_buffer (float): Minimum % bounce required for Advanced filter.
        data_fetcher (NSEDataFetcher): Reliable multi-source data fetcher.

    Public Methods:
        - screen_stocks(top_250_path: str, date_obj: datetime) -> str: Screens symbols.

    Private Methods:
        - _get_ns_ticker(symbol: str) -> str: Normalizes symbol format.
        - _fetch_history(tickers: list[str]) -> pd.DataFrame: Fetch price data.
        - _calculate_car_rating(df_ticker: pd.DataFrame) -> str: Compute CAR rating.
        - _calculate_bottom_out(df_ticker: pd.DataFrame) -> dict: Compute swing setup.
    """

    def __init__(
        self,
        processed_dir: str = "data/processed",
        cache_dir: str = "data/cache",
        bottom_out_tolerance: float = 0.5,
        bounce_buffer: float = 1.0,
    ) -> None:
        """
        Initialize the StockScreener with processed output directories.

        Parameters:
            processed_dir (str): Target directory for saving results.
            cache_dir (str): Target directory for caching data.
            bottom_out_tolerance (float): Max % difference allowed between
                Today Low and 20D Low to consider "tested" (default 0.5%).
            bounce_buffer (float): Min % CMP must be above 20D Low for
                Advanced filter (default 1.0%).

        Returns:
            None: Void constructor return.

        Raises:
            OSError: If directory creation fails.
        """
        self.processed_dir: str = processed_dir
        self.cache_dir: str = cache_dir
        self.bottom_out_tolerance: float = bottom_out_tolerance
        self.bounce_buffer: float = bounce_buffer

        os.makedirs(self.processed_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

        # Initialize the reliable data fetcher
        self.data_fetcher = NSEDataFetcher(
            cache_dir=self.cache_dir,
            cache_days=7,
        )

        LOGGER.info(
            "StockScreener initialized in: %s (cache: %s)",
            self.processed_dir,
            self.cache_dir,
        )

    def _get_ns_ticker(self, symbol: str) -> str:
        """
        Normalize standard stock symbols to Yahoo Finance NSE ticker format.
        """
        clean_symbol: str = str(symbol).strip().upper()
        if not clean_symbol.endswith(".NS"):
            return f"{clean_symbol}.NS"
        return clean_symbol

    def _fetch_history(self, tickers: list[str]) -> pd.DataFrame:
        """
        Download historical daily data for list of tickers.

        Uses NSEDataFetcher which implements:
        1. NSE Official API (primary)
        2. yfinance fallback
        3. Local cache

        Returns MultiIndex DataFrame compatible with existing code.
        """
        LOGGER.info("Fetching historical prices for %d symbols...", len(tickers))

        # Use NSEDataFetcher for reliable data
        # Pass symbols WITHOUT .NS suffix for NSE API preference
        clean_symbols = [t.replace(".NS", "") for t in tickers]

        results = self.data_fetcher.fetch_history(
            symbols=clean_symbols,
            period="1y",
            prefer_nse=True,
        )

        # Convert to MultiIndex DataFrame format
        dfs: list[pd.DataFrame] = []
        for symbol, df in results.items():
            if df.empty:
                LOGGER.warning("No data fetched for %s", symbol)
                continue

            # Ensure standard column names
            df.columns = [c.title() if isinstance(c, str) else c for c in df.columns]

            # Create MultiIndex columns: (symbol, field)
            ns_symbol = self._get_ns_ticker(symbol)
            df.columns = pd.MultiIndex.from_product([[ns_symbol], df.columns])
            dfs.append(df)

        if not dfs:
            LOGGER.error("No historical data fetched for any symbol.")
            raise ValueError("All data sources returned empty.")

        combined = pd.concat(dfs, axis=1)
        LOGGER.info("Combined data shape: %s", combined.shape)
        return combined

    def _calculate_car_rating(self, df_ticker: pd.DataFrame) -> str:
        """
        Compute Advanced Cumulative Average Rule (CAR) rating for a stock.
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

        # Step 5: Expanding Mean
        cum_avg: pd.Series = prices.expanding().mean()

        # Step 6: Get last 10 elements of cumulative average
        last_10: list[float] = cum_avg.tail(10).tolist()

        # Step 7: Check if averages are strictly increasing
        check: int = sum(1 for i in range(1, 10) if last_10[i] > last_10[i - 1])

        # Step 8: Return rating
        if check == 9:
            return "Buy/Average Out"
        return "Avoid/Hold"

    def _calculate_bottom_out(self, df_ticker: pd.DataFrame) -> dict[str, Any]:
        """
        Compute Bottom Out Hunting swing trading metrics.

        Logic:
            Step 1: Verify dataframe has required columns (High, Low, Close).
            Step 2: Calculate 20-day High, 20-day Low, and Today Low.
            Step 3: Check if Today Low is within tolerance of 20-day Low.
            Step 4: Check if CMP bounced above Today Low.
            Step 5: (Advanced) Check if bounce is meaningful (> bounce_buffer%).
            Step 6: Return GTT trigger price and status.

        Parameters:
            df_ticker (pd.DataFrame): Daily OHLCV data for ticker.
                Must have 'High', 'Low', 'Close' columns.

        Returns:
            dict[str, Any]: Dictionary containing:
                - '20D_HIGH': float
                - '20D_LOW': float
                - 'TODAY_LOW': float
                - 'GTT_TRIGGER': float (20-day high)
                - 'BOTTOM_OUT_STATUS': str
                - 'SWING_ADVICE': str
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

        # Step 2: Calculate 20-day metrics
        last_20 = clean_df.tail(20)
        high_20d: float = float(last_20["High"].max())
        low_20d: float = float(last_20["Low"].min())
        today_low: float = float(clean_df["Low"].iloc[-1])
        cmp: float = float(clean_df["Close"].iloc[-1])

        result["20D_HIGH"] = high_20d
        result["20D_LOW"] = low_20d
        result["TODAY_LOW"] = today_low
        result["GTT_TRIGGER"] = high_20d

        # Step 3: Floor Test — Today Low ≈ 20D Low?
        if low_20d <= 0:
            result["BOTTOM_OUT_STATUS"] = "Invalid Low"
            return result

        low_diff_pct: float = abs(today_low - low_20d) / low_20d * 100.0
        floor_tested: bool = low_diff_pct <= self.bottom_out_tolerance

        # Step 4: Bounce Test — CMP > Today Low?
        bounced: bool = cmp > today_low

        # Step 5: Advanced Bounce — meaningful recovery?
        bounce_pct: float = ((cmp - low_20d) / low_20d * 100.0) if low_20d > 0 else 0.0
        meaningful_bounce: bool = bounce_pct >= self.bounce_buffer

        # Decision Logic
        if not floor_tested:
            result["BOTTOM_OUT_STATUS"] = "Do not start GTT"
            result["SWING_ADVICE"] = "Wait for best time"
        elif not bounced:
            result["BOTTOM_OUT_STATUS"] = "Do not start GTT"
            result["SWING_ADVICE"] = "No bounce — avoid"
        elif not meaningful_bounce:
            # Basic version allows weak bounces; Advanced blocks them
            result["BOTTOM_OUT_STATUS"] = "Start GTT (Basic)"
            result["SWING_ADVICE"] = (
                f"Place GTT at {high_20d:.2f} | Weak bounce ({bounce_pct:.2f}%)"
            )
        else:
            # All conditions met
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

        Enhanced to include:
        - Bottom Out Hunting swing trading signals
        - 20-day High/Low/Todays Low metrics
        - GTT Trigger prices
        - Combined filter: Trend + CAR + Bottom Out

        Parameters:
            top_250_path (str): Path to top 250 processed CSV. | Must exist.
            date_obj (datetime): Current Date of pipeline execution. | Valid past date.

        Returns:
            str: Path to the generated filtered final list CSV.

        Raises:
            FileNotFoundError: If input top_250_path is missing.
            KeyError: If columns are missing from source CSV.
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

        # Step 2: Batch download historical data using NSEDataFetcher
        try:
            df_history: pd.DataFrame = self._fetch_history(ns_tickers)
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

            # CRITICAL FIX: Use get_level_values instead of levels[0]
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
                    }
                )
                continue

            # CMP is the last close price
            cmp: float = float(df_ticker["Close"].iloc[-1])
            # Previous close is close of second to last day
            prev_close: float = float(df_ticker["Close"].iloc[-2])

            # CRITICAL FIX: DMA calculations with minimum history guards
            close_series = df_ticker["Close"].dropna()
            available_days: int = len(close_series)

            dma_50: float = np.nan
            dma_100: float = np.nan
            dma_200: float = np.nan

            if available_days >= 50:
                dma_50 = float(close_series.tail(50).mean())
            if available_days >= 100:
                dma_100 = float(close_series.tail(100).mean())
            if available_days >= 200:
                dma_200 = float(close_series.tail(200).mean())

            # Percentage difference from 200 DMA
            diff_200_dma: float = np.nan
            if dma_200 and dma_200 > 0:
                diff_200_dma = ((cmp - dma_200) * 100.0) / dma_200

            # Trend Status with history guards
            trend_status: str = "Unconfirmed"
            if available_days >= 200 and all(
                v is not np.nan for v in [dma_50, dma_100, dma_200]
            ):
                if cmp > dma_50 and cmp > dma_100 and cmp > dma_200:
                    if 0.01 <= diff_200_dma <= 10.0:
                        trend_status = "In Bull Run"
                elif cmp < dma_50 and cmp < dma_100 and cmp < dma_200:
                    if -10.0 <= diff_200_dma <= -0.01:
                        trend_status = "In Bear Run"
            else:
                trend_status = "Insufficient History"

            # CAR Rating calculations
            car_rating: str = self._calculate_car_rating(df_ticker)

            # BOTTOM OUT HUNTING calculations
            bottom_out: dict[str, Any] = self._calculate_bottom_out(df_ticker)

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
                }
            )

        # Step 5: Save complete analyzed dataset
        df_analyzed: pd.DataFrame = pd.DataFrame(analyzed_records)
        date_str: str = date_obj.strftime("%Y%m%d")
        analyzed_filename: str = f"top_250_analyzed_{date_str}.csv"
        analyzed_filepath: str = os.path.join(self.processed_dir, analyzed_filename)
        df_analyzed.to_csv(analyzed_filepath, index=False)
        LOGGER.info("Complete analyzed dataset saved at: %s", analyzed_filepath)

        # Step 6: Create multiple filtered outputs

        # Filter A: Original — Trend = 'In Bull Run' AND CAR = 'Buy/Average Out'
        df_bull_car: pd.DataFrame = df_analyzed[
            (df_analyzed["TREND_STATUS"] == "In Bull Run")
            & (df_analyzed["CAR_RATING"] == "Buy/Average Out")
        ].copy()

        # Filter B: Bottom Out Hunting — Start GTT signals
        df_bottom_out: pd.DataFrame = df_analyzed[
            df_analyzed["BOTTOM_OUT_STATUS"].isin(["Start GTT", "Start GTT (Basic)"])
        ].copy()

        # Filter C: COMBINED — Bull Run + Buy CAR + Start GTT (The Holy Grail)
        df_combined: pd.DataFrame = df_analyzed[
            (df_analyzed["TREND_STATUS"] == "In Bull Run")
            & (df_analyzed["CAR_RATING"] == "Buy/Average Out")
            & (df_analyzed["BOTTOM_OUT_STATUS"] == "Start GTT")
        ].copy()

        # Save Filter A: Original Final List
        final_a_df: pd.DataFrame = df_bull_car[
            [
                "SYMBOL",
                "TURNOVER",
                "PREVIOUS_CLOSE",
                "CMP",
                "DIFF_200_DMA",
                "CAR_RATING",
            ]
        ].copy()
        final_a_df = final_a_df.rename(
            columns={
                "SYMBOL": "NSE Code",
                "TURNOVER": "Volume",
                "PREVIOUS_CLOSE": "Previous Close",
                "CMP": "CMP",
                "DIFF_200_DMA": "Difference from 200 DMA",
                "CAR_RATING": "CAR",
            }
        )
        final_a_df = final_a_df.sort_values(by="Volume", ascending=False)

        final_a_filename: str = f"final_list_{date_str}.csv"
        final_a_filepath: str = os.path.join(self.processed_dir, final_a_filename)
        final_a_df.to_csv(final_a_filepath, index=False)
        LOGGER.info(
            "Original final list (Bull+CAR) saved: %s (%d records)",
            final_a_filepath,
            len(final_a_df),
        )

        # Save Filter B: Bottom Out Swing List
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
            }
        )
        final_b_df = final_b_df.sort_values(by="Volume", ascending=False)

        final_b_filename: str = f"swing_list_{date_str}.csv"
        final_b_filepath: str = os.path.join(self.processed_dir, final_b_filename)
        final_b_df.to_csv(final_b_filepath, index=False)
        LOGGER.info(
            "Swing trading list (Bottom Out) saved: %s (%d records)",
            final_b_filepath,
            len(final_b_df),
        )

        # Save Filter C: Combined Super-Filter
        final_c_df: pd.DataFrame = df_combined[
            [
                "SYMBOL",
                "TURNOVER",
                "CMP",
                "DIFF_200_DMA",
                "CAR_RATING",
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
            "SUPER combined list (Bull+CAR+BottomOut) saved: %s (%d records)",
            final_c_filepath,
            len(final_c_df),
        )

        return final_c_filepath
