"""
File: src/engine/lux_nwe.py
Purpose: Nadaraya-Watson Envelope (Kernel Regression) ported from LuxAlgo Pine Script v6.
Features:
  - Non-parametric Kernel Regression estimation using Gaussian weights.
  - Multi-window Mean Absolute Error (MAE) dynamic volatility bands (Upper / Lower).
  - Crossover & Crossunder mean-reversion reversal signal detection.
  - High performance via NumPy and Polars.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import polars as pl


@dataclass
class NWEResult:
    """Output container for Nadaraya-Watson Envelope calculations."""
    df: pl.DataFrame
    bandwidth: float
    multiplier: float
    latest_nwe: float
    latest_upper: float
    latest_lower: float
    latest_signal: int  # +1 (Oversold / Buy), -1 (Overbought / Sell), 0 (Neutral)

    def to_pandas(self) -> pd.DataFrame:
        return self.df.to_pandas()


def calculate_nwe(
    data: pl.DataFrame | pd.DataFrame,
    bandwidth: float = 8.0,
    multiplier: float = 3.0,
    lookback: int = 500,
    src_col: str = "close",
) -> NWEResult:
    """
    Compute Nadaraya-Watson Envelope (NWE) with Gaussian Kernel.

    Parameters:
        data: Polars or Pandas DataFrame containing price series.
        bandwidth: Kernel bandwidth (smoothing parameter, default 8.0).
        multiplier: Multiplier for Mean Absolute Error envelope (default 3.0).
        lookback: Maximum historical window for kernel calculation (default 500).
        src_col: Source price column (default 'close').

    Returns:
        NWEResult containing Polars DataFrame with nwe, nwe_upper, nwe_lower, and signals.
    """
    if isinstance(data, pd.DataFrame):
        p_df = pl.from_pandas(data)
    else:
        p_df = data

    src_lower = src_col.lower()
    matched_col = None
    for c in p_df.columns:
        if c.lower() == src_lower:
            matched_col = c
            break

    if not matched_col:
        raise ValueError(f"Column '{src_col}' not found in input data.")

    src = p_df[matched_col].to_numpy().astype(float)
    n = len(src)

    if n == 0:
        return NWEResult(
            df=p_df,
            bandwidth=bandwidth,
            multiplier=multiplier,
            latest_nwe=float("nan"),
            latest_upper=float("nan"),
            latest_lower=float("nan"),
            latest_signal=0,
        )

    # 1. Pre-calculate Gaussian kernel weights for lookback distance
    # Pine: gauss(x, h) => math.exp(-(math.pow(x, 2) / (h * h * 2)))
    w_len = min(lookback, n)
    indices = np.arange(w_len, dtype=float)
    weights = np.exp(-(indices ** 2) / (2.0 * (bandwidth ** 2)))
    den = np.sum(weights)

    nwe_arr = np.full(n, np.nan, dtype=float)
    upper_arr = np.full(n, np.nan, dtype=float)
    lower_arr = np.full(n, np.nan, dtype=float)
    bullish_rev = np.zeros(n, dtype=bool)
    bearish_rev = np.zeros(n, dtype=bool)

    # 2. Causal / Streaming Endpoint Kernel calculation (Non-repainting mode)
    # At each bar i, weighted sum of previous bars using backward Gaussian kernel
    for i in range(n):
        curr_len = min(i + 1, w_len)
        window_src = src[i - curr_len + 1: i + 1][::-1]  # distance 0 to curr_len-1
        curr_weights = weights[:curr_len]
        curr_den = np.sum(curr_weights)

        nwe_val = np.sum(window_src * curr_weights) / curr_den
        nwe_arr[i] = nwe_val

        # Rolling Mean Absolute Error (MAE)
        mae_window = abs(src[max(0, i - curr_len + 1): i + 1] - nwe_arr[max(0, i - curr_len + 1): i + 1])
        mae = np.mean(mae_window) * multiplier
        upper_arr[i] = nwe_val + mae
        lower_arr[i] = nwe_val - mae

        # Reversal signals: Crossing outside boundary then crossing back, or boundary touches
        if i >= 1:
            if src[i - 1] < lower_arr[i - 1] and src[i] >= lower_arr[i]:
                bullish_rev[i] = True
            elif src[i - 1] > upper_arr[i - 1] and src[i] <= upper_arr[i]:
                bearish_rev[i] = True

    latest_sig = 1 if bullish_rev[-1] else (-1 if bearish_rev[-1] else 0)

    res_df = p_df.with_columns(
        [
            pl.Series("nwe", nwe_arr),
            pl.Series("nwe_upper", upper_arr),
            pl.Series("nwe_lower", lower_arr),
            pl.Series("nwe_buy_reversal", bullish_rev),
            pl.Series("nwe_sell_reversal", bearish_rev),
        ]
    )

    return NWEResult(
        df=res_df,
        bandwidth=bandwidth,
        multiplier=multiplier,
        latest_nwe=float(nwe_arr[-1]),
        latest_upper=float(upper_arr[-1]),
        latest_lower=float(lower_arr[-1]),
        latest_signal=latest_sig,
    )
