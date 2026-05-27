"""
File: src/nse_bhavcopy/mtf_confirmation.py
Purpose: Cross-references weekly parquet data to add MTF_CONFIRMED flag to screener
    output.
Last Modified: 2026-05-27
"""

import logging
import os

import numpy as np
import pandas as pd
import talib

LOGGER: logging.Logger = logging.getLogger(__name__)

_WEEKLY_SMA_FAST: int = 50
_WEEKLY_SMA_SLOW: int = 200
_DAILY_BULL_STATUS: str = "In Bull Run"


def _load_weekly_smas(
    symbol: str,
    weekly_dir: str,
) -> tuple[float | None, float | None]:
    """
    Load the latest weekly SMA50 and SMA200 for a given symbol from its parquet file.

    Uses pre-computed SMA_50 / SMA_200 columns if present (written by
    historical_sync → add_ta_indicators); falls back to computing via TA-Lib
    from the raw Close column when those columns are absent.

    Parameters:
        symbol (str): NSE stock symbol without .NS suffix (e.g. "SUZLON").
        weekly_dir (str): Filesystem path to the directory containing 1W
            parquet files named {SYMBOL}.parquet.

    Returns:
        Tuple[float | None, float | None]: (sma50, sma200) for the latest
            available weekly bar, or (None, None) when data is insufficient.

    Raises:
        None (all failures are logged at DEBUG level and return None pair).

    Complexity:
        Time: O(W) where W = number of weekly bars in the parquet file
        Space: O(W) [Parquet read into memory]

    Example:
        >>> sma50, sma200 = _load_weekly_smas("SUZLON", "data/historical/1W")
        >>> print(sma50, sma200)
        49.12 47.88
    """
    path = os.path.join(weekly_dir, f"{symbol.upper()}.parquet")
    if not os.path.exists(path):
        LOGGER.debug("MTF: No weekly parquet for %s at %s", symbol, path)
        return None, None

    try:
        df_w: pd.DataFrame = pd.read_parquet(path)
    except Exception as exc:
        LOGGER.debug("MTF: Failed reading weekly parquet for %s: %s", symbol, exc)
        return None, None

    if df_w.empty or "Close" not in df_w.columns:
        return None, None

    # Use pre-computed columns when available (fastest path)
    if "SMA_50" in df_w.columns and "SMA_200" in df_w.columns:
        sma50_series = df_w["SMA_50"].dropna()
        sma200_series = df_w["SMA_200"].dropna()
        if sma50_series.empty or sma200_series.empty:
            return None, None
        return float(sma50_series.iloc[-1]), float(sma200_series.iloc[-1])

    # Fallback: compute on the fly from Close
    close = df_w["Close"].astype("float64").dropna()
    if len(close) < _WEEKLY_SMA_SLOW:
        LOGGER.debug(
            "MTF: %s has %d weekly bars — need %d for SMA%d",
            symbol,
            len(close),
            _WEEKLY_SMA_SLOW,
            _WEEKLY_SMA_SLOW,
        )
        return None, None

    raw_sma50 = talib.SMA(close.values, timeperiod=_WEEKLY_SMA_FAST)
    raw_sma200 = talib.SMA(close.values, timeperiod=_WEEKLY_SMA_SLOW)
    last50 = raw_sma50[-1]
    last200 = raw_sma200[-1]

    if np.isnan(last50) or np.isnan(last200):
        return None, None

    return float(last50), float(last200)


def build_mtf_map(
    symbols: list[str],
    weekly_dir: str,
) -> dict[str, bool]:
    """
    Build a symbol → weekly_golden_cross mapping for a list of NSE symbols.

    A symbol maps to True when its weekly SMA50 > SMA200 (weekly golden cross).
    This is independent of the daily trend status; the two conditions are
    combined in add_mtf_confirmation().

    Parameters:
        symbols (list[str]): List of NSE stock symbols (e.g. ["SUZLON", "LT"]).
        weekly_dir (str): Path to directory containing 1W parquet files.

    Returns:
        dict[str, bool]: {symbol_upper: True/False} mapping for every input symbol.

    Raises:
        None

    Complexity:
        Time: O(N x W) where N = len(symbols), W = weekly bars per symbol
        Space: O(N) [Dict output]

    Example:
        >>> mtf = build_mtf_map(["SUZLON", "LT"], "data/historical/1W")
        >>> print(mtf)
        {'SUZLON': True, 'LT': False}
    """
    result: dict[str, bool] = {}
    confirmed = 0

    for sym in symbols:
        sma50, sma200 = _load_weekly_smas(sym, weekly_dir)
        weekly_golden_cross = (
            sma50 is not None and sma200 is not None and sma50 > sma200
        )
        result[sym.upper()] = weekly_golden_cross
        if weekly_golden_cross:
            confirmed += 1

    LOGGER.info(
        "MTF map: %d/%d symbols have weekly SMA%d > SMA%d",
        confirmed,
        len(symbols),
        _WEEKLY_SMA_FAST,
        _WEEKLY_SMA_SLOW,
    )
    return result


def add_mtf_confirmation(
    df: pd.DataFrame,
    weekly_dir: str,
    symbol_col: str = "SYMBOL",
    trend_col: str = "TREND_STATUS",
) -> pd.DataFrame:
    """
    Append MTF_CONFIRMED and MTF_CALLOUT columns to the analyzed screener DataFrame.

    A stock is MTF_CONFIRMED=True only when BOTH conditions hold:
        1. Daily TREND_STATUS == "In Bull Run"  (from screener.py output)
        2. Weekly SMA50 > Weekly SMA200         (golden cross on weekly chart)

    Parameters:
        df (pd.DataFrame): Analyzed screener DataFrame with symbol and trend columns.
        weekly_dir (str): Path to directory containing 1W parquet files named
            {SYMBOL}.parquet (e.g. "data/historical/1W").
        symbol_col (str): Column name holding the NSE ticker symbol. |
            Default: "SYMBOL"
        trend_col (str): Column name holding the daily trend status string. |
            Default: "TREND_STATUS"

    Returns:
        pd.DataFrame: Copy of input with two new columns:
            - MTF_CONFIRMED (bool): True when both daily + weekly align bullish.
            - MTF_CALLOUT (str): One-line human-readable signal description.

    Raises:
        KeyError: If symbol_col is not present in df.columns.

    Complexity:
        Time: O(N x W) where N = stocks, W = weekly bars per parquet
        Space: O(N) [Two new Series + internal dict]

    Example:
        >>> df = pd.read_csv("data/historical/top_250_analyzed_20260527.csv")
        >>> enriched = add_mtf_confirmation(df, "data/historical/1W")
        >>> confirmed = enriched[enriched["MTF_CONFIRMED"]]
        >>> print(confirmed[["SYMBOL", "TREND_STATUS", "MTF_CALLOUT"]].head())
    """
    if symbol_col not in df.columns:
        raise KeyError(
            f"Symbol column '{symbol_col}' not found. "
            f"Available columns: {df.columns.tolist()}"
        )

    symbols: list[str] = df[symbol_col].astype(str).str.strip().str.upper().tolist()
    mtf_map = build_mtf_map(symbols, weekly_dir)

    df = df.copy()

    weekly_ok: pd.Series = (
        df[symbol_col].astype(str).str.upper().map(mtf_map).fillna(False)
    )

    daily_bull: pd.Series
    if trend_col in df.columns:
        daily_bull = df[trend_col].eq(_DAILY_BULL_STATUS)
    else:
        LOGGER.warning(
            "MTF: trend column '%s' not found; daily condition defaults False.",
            trend_col,
        )
        daily_bull = pd.Series(False, index=df.index)

    df["MTF_CONFIRMED"] = weekly_ok & daily_bull

    def _callout(confirmed: bool) -> str:
        """Return a one-line MTF signal description based on confirmation status."""
        if confirmed:
            return (
                "✅ MTF Confirmed: Weekly Golden Cross + Daily Bull Run "
                "— highest conviction setup"
            )
        return "⏸️  MTF: Daily/Weekly alignment incomplete — wait for confirmation"

    df["MTF_CALLOUT"] = df["MTF_CONFIRMED"].map(_callout)

    confirmed_count = int(df["MTF_CONFIRMED"].sum())
    LOGGER.info(
        "MTF confirmation: %d/%d stocks fully confirmed on daily + weekly.",
        confirmed_count,
        len(df),
    )
    return df
