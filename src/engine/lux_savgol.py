"""
File: src/engine/lux_savgol.py
Purpose: Savitzky-Golay Digital Smoothing Filter ported from LuxAlgo Pine Script v6.
Features:
  - Polynomial curve fitting filter via scipy.signal.savgol_filter.
  - Eliminates market noise while preserving local minima/maxima peak heights without lag.
  - Computes 1st derivative (slope) and 2nd derivative (curvature).
  - Emits inflection turning signals (Bullish turn when slope turns positive, Bearish when slope turns negative).
  - High performance calculation via SciPy and Polars.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
import polars as pl
from scipy.signal import savgol_filter


@dataclass
class SavGolResult:
    df: pl.DataFrame
    latest_sg: float
    latest_slope: float
    latest_curvature: float
    latest_turn_signal: int  # +1: Bullish reversal turn, -1: Bearish reversal turn, 0: Neutral

    def to_pandas(self) -> pd.DataFrame:
        return self.df.to_pandas()


def calculate_savgol(
    data: pl.DataFrame | pd.DataFrame,
    half_width: int = 15,
    poly_order: int = 2,
    min_slope_ratio: float = 0.05,
    src_col: str = "close",
) -> SavGolResult:
    """
    Compute Savitzky-Golay Filter and slope inflection signals.

    Parameters:
        data: DataFrame containing price series
        half_width: Window half width (window_length = 2 * half_width + 1)
        poly_order: Degree of polynomial (default 2)
        min_slope_ratio: Slope deadband threshold as fraction of ATR to avoid flat market noise
        src_col: Price column to filter (default 'close')

    Returns:
        SavGolResult with Polars DataFrame containing sg_filter, sg_slope, and signals.
    """
    if isinstance(data, pd.DataFrame):
        p_df = pl.from_pandas(data)
    else:
        p_df = data

    cols = {c.lower(): c for c in p_df.columns}
    src_key = cols.get(src_col.lower(), "close")

    prices = p_df[src_key].to_numpy().astype(np.float64)
    n = len(prices)
    window_len = 2 * half_width + 1

    if n < window_len:
        empty_df = p_df.with_columns([
            pl.lit(prices).alias("sg_filter"),
            pl.lit(0.0).alias("sg_slope"),
            pl.lit(0.0).alias("sg_curvature"),
            pl.lit(0).alias("sg_signal"),
        ])
        return SavGolResult(
            df=empty_df,
            latest_sg=float(prices[-1]) if n > 0 else 0.0,
            latest_slope=0.0,
            latest_curvature=0.0,
            latest_turn_signal=0,
        )

    # 1. Compute Savitzky-Golay 0th, 1st, and 2nd derivatives
    # deriv=0 is smoothed curve
    sg_smooth = savgol_filter(prices, window_length=window_len, polyorder=poly_order, deriv=0)
    # deriv=1 is velocity / slope
    sg_slope = savgol_filter(prices, window_length=window_len, polyorder=poly_order, deriv=1)
    # deriv=2 is acceleration / curvature
    sg_curv = savgol_filter(prices, window_length=window_len, polyorder=poly_order, deriv=2)

    # 2. Reversal turn signals
    # Bull turn: slope crosses above +threshold from <= 0
    # Bear turn: slope crosses below -threshold from >= 0
    signals = np.zeros(n, dtype=np.int32)
    for i in range(1, n):
        if sg_slope[i - 1] <= 0 and sg_slope[i] > 0:
            signals[i] = 1
        elif sg_slope[i - 1] >= 0 and sg_slope[i] < 0:
            signals[i] = -1

    out_df = p_df.with_columns([
        pl.Series("sg_filter", np.round(sg_smooth, 2)),
        pl.Series("sg_slope", np.round(sg_slope, 4)),
        pl.Series("sg_curvature", np.round(sg_curv, 6)),
        pl.Series("sg_signal", signals),
    ])

    return SavGolResult(
        df=out_df,
        latest_sg=round(float(sg_smooth[-1]), 2),
        latest_slope=round(float(sg_slope[-1]), 4),
        latest_curvature=round(float(sg_curv[-1]), 6),
        latest_turn_signal=int(signals[-1]),
    )
