"""
File: src/nse_bhavcopy/sector_rotation.py
Purpose: Calculates JdK RS-Ratio and Momentum to identify sector rotation trends.
Last Modified: 2026-05-27
"""

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import os

def fetch_data(
    symbols: list[str], period_days: int, hist_dir: str = "data/historical/1d"
) -> tuple[dict[str, pd.Series], list[str]]:
    """
    Fetch historical data from local offline Parquet files.

    Parameters:
        symbols (list[str]): List of sector/stock symbols.
        period_days (int): Number of days of historical data needed.
        hist_dir (str): Directory containing local parquet files.

    Returns:
        Tuple[dict[str, pd.Series], list[str]]:
            Dict mapping symbols to their closing prices, and failed symbols list.
    """
    data: dict[str, pd.Series] = {}
    failed_symbols: list[str] = []

    # rough calculation: 1 trading day = ~1 row. Add 10 buffer.
    rows_needed = period_days + 10

    for symbol in symbols:
        try:
            clean_sym = symbol.replace("^", "").replace(".NS", "")
            path = os.path.join(hist_dir, f"{clean_sym.upper()}.parquet")
            
            if not os.path.exists(path):
                failed_symbols.append(symbol)
                continue
                
            hist = pd.read_parquet(path)
            
            if hist.empty or len(hist) < 20:
                failed_symbols.append(symbol)
                continue

            # Ensure index is datetime
            if not isinstance(hist.index, pd.DatetimeIndex):
                hist.index = pd.to_datetime(hist.index)
            
            # Map columns to lowercase just in case to find 'close', or uppercase 'Close'
            col_mapping = {col.lower(): col for col in hist.columns}
            if 'close' not in col_mapping:
                failed_symbols.append(symbol)
                continue

            close_col = col_mapping['close']
            
            # Keep only the needed tail
            data[symbol] = hist[close_col].tail(rows_needed).copy()
        except Exception:
            failed_symbols.append(symbol)

    return data, failed_symbols


def calculate_relative_strength(
    price_data: pd.Series, benchmark_data: pd.Series, period: int
) -> tuple[pd.Series | None, pd.Series | None]:
    """
    Calculate relative strength vs benchmark.

    Parameters:
        price_data (pd.Series): Asset closing prices.
        benchmark_data (pd.Series): Benchmark closing prices.
        period (int): Lookback period for momentum calculation.

    Returns:
        Tuple[pd.Series | None, pd.Series | None]: Relative strength and momentum.
    """
    min_length = min(len(price_data), len(benchmark_data))
    if min_length < period:
        return None, None

    aligned_data = pd.DataFrame(
        {"price": price_data, "benchmark": benchmark_data}
    ).dropna()

    if len(aligned_data) < period:
        return None, None

    relative_strength = aligned_data["price"] / aligned_data["benchmark"]
    rs_momentum = relative_strength.pct_change(period).dropna()

    return relative_strength, rs_momentum


def calculate_jdk_rs_ratio(
    relative_strength: pd.Series, long_period: int = 40
) -> pd.Series | None:
    """
    Calculate volatility-standardized JdK RS-Ratio (Z-score normalized).

    Parameters:
        relative_strength (pd.Series): Relative strength vs benchmark.
        long_period (int): Rolling mean window.

    Returns:
        pd.Series | None: Standardized RS-Ratio centered at 100.
    """
    if len(relative_strength) < long_period:
        return None

    mean = relative_strength.rolling(long_period).mean()
    std = relative_strength.rolling(long_period).std()
    rs_normalized = ((relative_strength - mean) / (std + 1e-9)) * 10 + 100
    return rs_normalized


def calculate_jdk_rs_momentum(
    rs_ratio: pd.Series | None, period: int = 10
) -> pd.Series | None:
    """
    Calculate volatility-standardized JdK RS-Momentum (Z-score normalized rate of change).

    Parameters:
        rs_ratio (pd.Series | None): RS-Ratio data.
        period (int): Momentum lookback period.

    Returns:
        pd.Series | None: Standardized RS-Momentum centered at 100.
    """
    if rs_ratio is None or len(rs_ratio) < period + 1:
        return None

    roc = rs_ratio.diff(1)
    mean = roc.rolling(period).mean()
    std = roc.rolling(period).std()
    momentum = ((roc - mean) / (std + 1e-9)) * 10 + 100
    return momentum


def get_quadrant_info(rs_ratio: float, rs_momentum: float) -> str:
    """
    Determine quadrant based on standardized RS-Ratio and Momentum.

    Parameters:
        rs_ratio (float): JdK RS-Ratio value.
        rs_momentum (float): JdK RS-Momentum value.

    Returns:
        str: Quadrant designation (Leading, Weakening, Lagging, Improving).
    """
    if rs_ratio > 100 and rs_momentum > 100:
        return "Leading"
    elif rs_ratio > 100 and rs_momentum < 100:
        return "Weakening"
    elif rs_ratio < 100 and rs_momentum < 100:
        return "Lagging"
    else:
        return "Improving"


def run_sector_rotation_cli(benchmark: str = "NIFTYBEES", period: int = 90) -> pd.DataFrame:
    """
    Runs the sector rotation analysis and formats it into a DataFrame.

    Parameters:
        benchmark (str): The benchmark index symbol (default NIFTYBEES).
        period (int): Lookback period for fetching data in days.

    Returns:
        pd.DataFrame: A table of sectors and their JdK Rotation quadrants.
    """
    sectors = [
        "AUTOBEES",
        "PHARMABEES",
        "ITBEES",
        "INFRABEES",
        "PSUBNKBEES",
        "CONSUMBEES",
        "BANKBEES",
        "MID150BEES",
        "RELIANCE",
        "INFY",
    ]

    benchmark_data, _ = fetch_data([benchmark], period)
    if benchmark not in benchmark_data:
        print(f"Error: Could not fetch data for benchmark {benchmark}")
        return pd.DataFrame()

    sector_data, failed_sectors = fetch_data(sectors, period)
    if failed_sectors:
        print(f"Warning: Failed to fetch {failed_sectors}")

    results: dict[str, Any] = {}
    benchmark_prices = benchmark_data[benchmark]

    for symbol, prices in sector_data.items():
        rel_strength, _ = calculate_relative_strength(prices, benchmark_prices, 10)
        if rel_strength is not None:
            rs_ratio = calculate_jdk_rs_ratio(rel_strength)
            rs_momentum = calculate_jdk_rs_momentum(rs_ratio)
            results[symbol] = {
                "rs_ratio": rs_ratio,
                "rs_momentum": rs_momentum,
            }

    summary_data = []
    for symbol, data in results.items():
        if data["rs_ratio"] is not None and data["rs_momentum"] is not None:
            if len(data["rs_ratio"]) > 0 and len(data["rs_momentum"]) > 0:
                current_ratio = data["rs_ratio"].iloc[-1]
                current_momentum = data["rs_momentum"].iloc[-1]
                quadrant = get_quadrant_info(current_ratio, current_momentum)

                summary_data.append(
                    {
                        "Sector": symbol,
                        "RS_Ratio": current_ratio,
                        "RS_Momentum": current_momentum,
                        "Quadrant": quadrant,
                    }
                )

    if not summary_data:
        return pd.DataFrame()

    df_summary = pd.DataFrame(summary_data)
    # Sort logically so Leading is at top, followed by Improving, Weakening, Lagging
    quadrant_order = {"Leading": 1, "Improving": 2, "Weakening": 3, "Lagging": 4}
    df_summary["Sort_Order"] = df_summary["Quadrant"].map(quadrant_order)
    df_summary = df_summary.sort_values(
        by=["Sort_Order", "RS_Ratio"], ascending=[True, False]
    ).drop(columns=["Sort_Order"])

    return df_summary
