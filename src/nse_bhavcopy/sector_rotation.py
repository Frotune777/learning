"""
File: src/nse_bhavcopy/sector_rotation.py
Purpose: Calculates JdK RS-Ratio and Momentum to identify sector rotation trends.
Last Modified: 2026-05-27
"""

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf


def fetch_data(
    symbols: list[str], period_days: int
) -> tuple[dict[str, pd.Series], list[str]]:
    """
    Fetch historical data from yfinance.

    Parameters:
        symbols (list[str]): List of sector/stock symbols.
        period_days (int): Number of days of historical data needed.

    Returns:
        Tuple[dict[str, pd.Series], list[str]]:
            Dict mapping symbols to their closing prices, and failed symbols list.
    """
    data: dict[str, pd.Series] = {}
    failed_symbols: list[str] = []

    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days + 10)

    for symbol in symbols:
        try:
            hist = yf.download(symbol, start=start_date, end=end_date, progress=False)
            if hist.empty or len(hist) < 20:
                failed_symbols.append(symbol)
                continue

            # Extract flat Close series
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)

            data[symbol] = hist["Close"]
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
    Calculate JdK RS-Ratio.

    Parameters:
        relative_strength (pd.Series): Relative strength vs benchmark.
        long_period (int): Rolling mean window.

    Returns:
        pd.Series | None: Normalized RS-Ratio.
    """
    if len(relative_strength) < long_period:
        return None

    rs_normalized = (
        relative_strength / relative_strength.rolling(long_period).mean()
    ) * 100
    return rs_normalized


def calculate_jdk_rs_momentum(
    rs_ratio: pd.Series | None, period: int = 10
) -> pd.Series | None:
    """
    Calculate JdK RS-Momentum.

    Parameters:
        rs_ratio (pd.Series | None): RS-Ratio data.
        period (int): Momentum lookback period.

    Returns:
        pd.Series | None: RS-Momentum data.
    """
    if rs_ratio is None or len(rs_ratio) < period:
        return None

    momentum = ((rs_ratio / rs_ratio.shift(period)) - 1) * 100
    return momentum


def get_quadrant_info(rs_ratio: float, rs_momentum: float) -> str:
    """
    Determine quadrant based on RS-Ratio and Momentum.

    Parameters:
        rs_ratio (float): JdK RS-Ratio value.
        rs_momentum (float): JdK RS-Momentum value.

    Returns:
        str: Quadrant designation (Leading, Weakening, Lagging, Improving).
    """
    if rs_ratio > 100 and rs_momentum > 0:
        return "Leading"
    elif rs_ratio > 100 and rs_momentum < 0:
        return "Weakening"
    elif rs_ratio < 100 and rs_momentum < 0:
        return "Lagging"
    else:
        return "Improving"


def run_sector_rotation_cli(benchmark: str = "^NSEI", period: int = 90) -> pd.DataFrame:
    """
    Runs the sector rotation analysis and formats it into a DataFrame.

    Parameters:
        benchmark (str): The benchmark index symbol (default Nifty 50).
        period (int): Lookback period for fetching data in days.

    Returns:
        pd.DataFrame: A table of sectors and their JdK Rotation quadrants.
    """
    sectors = [
        "^CNXAUTO",
        "^CNXPHARMA",
        "^CNXMETAL",
        "^CNXIT",
        "^CNXENERGY",
        "^CNXREALTY",
        "^CNXPSUBANK",
        "^CNXMEDIA",
        "^CNXINFRA",
        "^CNXPSE",
        "RELIANCE.NS",
        "INFY.NS",
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
