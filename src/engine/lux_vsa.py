"""
File: src/engine/lux_vsa.py
Purpose: Volume Spread Analysis (VSA) - No-Demand & No-Supply Bars ported from LuxAlgo Pine Script v6.
Features:
  - Spread calculation: (High - Low) relative to 20-period rolling average spread.
  - Narrow spread test: Spread < Narrow Spread Threshold * Average Spread.
  - Low volume test: Volume lower than both previous two bars (Volume[i] < Volume[i-1] and Volume[i-2]).
  - Directional Bar tests:
      * No-Demand (ND): Up candle (Close > Close[1]) on narrow spread + low volume.
      * No-Supply (NS): Down candle (Close < Close[1]) on narrow spread + low volume.
  - Background Context Filter:
      * Context Trend Filter via 50 EMA/SMA (NS qualified in uptrend / ND qualified in downtrend).
  - Next-bar Confirmation: Up close after NS, Down close after ND.
  - Vectorized using Polars & NumPy.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
import polars as pl


@dataclass
class VSAResult:
    df: pl.DataFrame
    latest_no_demand: bool
    latest_no_supply: bool
    latest_nd_confirmed: bool
    latest_ns_confirmed: bool
    relative_spread: float
    relative_volume: float

    def to_pandas(self) -> pd.DataFrame:
        return self.df.to_pandas()


def calculate_vsa_bars(
    data: pl.DataFrame | pd.DataFrame,
    spread_len: int = 20,
    narrow_spread_threshold: float = 1.0,
    context_len: int = 50,
    use_context_filter: bool = True,
) -> VSAResult:
    """
    Compute VSA No-Demand & No-Supply bar classifications.

    Parameters:
        data: DataFrame containing 'high', 'low', 'close', 'volume'
        spread_len: Rolling average spread lookback (default 20)
        narrow_spread_threshold: Fraction of average spread to count as narrow (default 1.0)
        context_len: Moving average lookback for background trend (default 50)
        use_context_filter: If True, only qualifies NS in uptrend and ND in downtrend

    Returns:
        VSAResult with Polars DataFrame enriched with VSA columns.
    """
    if isinstance(data, pd.DataFrame):
        p_df = pl.from_pandas(data)
    else:
        p_df = data

    cols = {c.lower(): c for c in p_df.columns}
    high_col = cols.get("high", "high")
    low_col = cols.get("low", "low")
    close_col = cols.get("close", "close")
    vol_col = cols.get("volume", "volume")

    highs = p_df[high_col].to_numpy().astype(np.float64)
    lows = p_df[low_col].to_numpy().astype(np.float64)
    closes = p_df[close_col].to_numpy().astype(np.float64)
    vols = p_df[vol_col].to_numpy().astype(np.float64) if vol_col in p_df.columns else np.ones_like(closes)
    n = len(closes)

    if n < max(spread_len, context_len) + 2:
        empty_df = p_df.with_columns([
            pl.lit(False).alias("vsa_no_demand"),
            pl.lit(False).alias("vsa_no_supply"),
            pl.lit(False).alias("vsa_nd_confirmed"),
            pl.lit(False).alias("vsa_ns_confirmed"),
            pl.lit(1.0).alias("vsa_spread_ratio"),
            pl.lit(1.0).alias("vsa_vol_ratio"),
        ])
        return VSAResult(
            df=empty_df,
            latest_no_demand=False,
            latest_no_supply=False,
            latest_nd_confirmed=False,
            latest_ns_confirmed=False,
            relative_spread=1.0,
            relative_volume=1.0,
        )

    # 1. Bar spread & rolling average spread
    bar_spread = highs - lows
    spread_cumsum = np.cumsum(np.insert(bar_spread, 0, 0.0))
    avg_spread = np.full(n, np.nan, dtype=np.float64)
    avg_spread[spread_len - 1:] = (spread_cumsum[spread_len:] - spread_cumsum[:-spread_len]) / spread_len

    # 2. Context trend: 50 EMA
    alpha = 2.0 / (context_len + 1.0)
    context_ema = np.empty(n, dtype=np.float64)
    context_ema[0] = closes[0]
    for i in range(1, n):
        context_ema[i] = alpha * closes[i] + (1.0 - alpha) * context_ema[i - 1]

    # 3. Vectorized VSA flags
    # Up close vs Down close
    up_close = np.zeros(n, dtype=bool)
    down_close = np.zeros(n, dtype=bool)
    up_close[1:] = closes[1:] > closes[:-1]
    down_close[1:] = closes[1:] < closes[:-1]

    # Narrow spread: bar_spread < avg_spread * narrow_spread_threshold
    narrow_spread = np.zeros(n, dtype=bool)
    valid_avg_spread = ~np.isnan(avg_spread) & (avg_spread > 0)
    narrow_spread[valid_avg_spread] = bar_spread[valid_avg_spread] < (avg_spread[valid_avg_spread] * narrow_spread_threshold)

    # Low volume: volume < volume[i-1] and volume < volume[i-2]
    low_volume = np.zeros(n, dtype=bool)
    low_volume[2:] = (vols[2:] < vols[1:-1]) & (vols[2:] < vols[:-2])

    # Raw No-Demand & No-Supply
    raw_no_demand = up_close & narrow_spread & low_volume
    raw_no_supply = down_close & narrow_spread & low_volume

    # Context qualification
    bg_strength = closes > context_ema
    bg_weakness = closes < context_ema

    if use_context_filter:
        qualified_nd = raw_no_demand & bg_weakness
        qualified_ns = raw_no_supply & bg_strength
    else:
        qualified_nd = raw_no_demand
        qualified_ns = raw_no_supply

    # Next-bar confirmation:
    # NS confirmed if previous bar was qualified NS and current bar is up_close
    # ND confirmed if previous bar was qualified ND and current bar is down_close
    ns_confirmed = np.zeros(n, dtype=bool)
    nd_confirmed = np.zeros(n, dtype=bool)
    ns_confirmed[1:] = qualified_ns[:-1] & up_close[1:]
    nd_confirmed[1:] = qualified_nd[:-1] & down_close[1:]

    # Ratios for diagnostics
    spread_ratio = np.ones(n, dtype=np.float64)
    spread_ratio[valid_avg_spread] = bar_spread[valid_avg_spread] / avg_spread[valid_avg_spread]

    prior_min_vol = np.minimum(vols[1:-1], vols[:-2])
    vol_ratio = np.ones(n, dtype=np.float64)
    valid_pv = np.zeros(n, dtype=bool)
    valid_pv[2:] = prior_min_vol > 0
    vol_ratio[2:][valid_pv[2:]] = vols[2:][valid_pv[2:]] / prior_min_vol[valid_pv[2:]]

    out_df = p_df.with_columns([
        pl.Series("vsa_no_demand", qualified_nd),
        pl.Series("vsa_no_supply", qualified_ns),
        pl.Series("vsa_nd_confirmed", nd_confirmed),
        pl.Series("vsa_ns_confirmed", ns_confirmed),
        pl.Series("vsa_spread_ratio", np.round(spread_ratio, 2)),
        pl.Series("vsa_vol_ratio", np.round(vol_ratio, 2)),
        pl.Series("vsa_context_ema", np.round(context_ema, 2)),
    ])

    return VSAResult(
        df=out_df,
        latest_no_demand=bool(qualified_nd[-1]),
        latest_no_supply=bool(qualified_ns[-1]),
        latest_nd_confirmed=bool(nd_confirmed[-1]),
        latest_ns_confirmed=bool(ns_confirmed[-1]),
        relative_spread=round(float(spread_ratio[-1]), 2),
        relative_volume=round(float(vol_ratio[-1]), 2),
    )
