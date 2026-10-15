"""
File: src/engine/lux_weinstein.py
Purpose: Stan Weinstein 4-Stage Analysis Engine ported from LuxAlgo Pine Script v6.
Features:
  - 30-week (or configurable daily equivalent) Moving Average calculation.
  - Multi-week Slope Calculation & Flat Band detection to classify:
      * Stage 1: Basing (Accumulation, flat MA after decline)
      * Stage 2: Advancing (Markup, rising MA, breakout on volume)
      * Stage 3: Topping (Distribution, flattening MA after rally)
      * Stage 4: Declining (Markdown, falling MA, breakdown)
  - Relative Volume Breakout confirmation (>2.0x volume filter).
  - High performance, vectorized with Polars & NumPy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import polars as pl

STAGE_NAMES = {
    0: "Undetermined",
    1: "Stage 1 (Basing / Accumulation)",
    2: "Stage 2 (Advancing / Markup)",
    3: "Stage 3 (Topping / Distribution)",
    4: "Stage 4 (Declining / Markdown)",
}


@dataclass
class WeinsteinResult:
    df: pl.DataFrame
    current_stage: int
    stage_name: str
    ma_value: float
    ma_slope_pct: float
    volume_ratio: float
    is_breakout: bool
    is_breakdown: bool

    def to_pandas(self) -> pd.DataFrame:
        return self.df.to_pandas()


def calculate_weinstein_stage(
    data: pl.DataFrame | pd.DataFrame,
    ma_weeks: int = 30,
    slope_weeks: int = 4,
    flat_band_pct: float = 1.0,
    vol_lookback_weeks: int = 4,
    vol_mult: float = 2.0,
    is_daily: bool = True,
) -> WeinsteinResult:
    """
    Compute Weinstein 4-Stage Analysis.

    Parameters:
        data: DataFrame containing 'close' and optionally 'volume'
        ma_weeks: Moving average length in weeks (default 30 weeks = 150 daily bars)
        slope_weeks: Slope lookback in weeks (default 4 weeks = 20 daily bars)
        flat_band_pct: Flat band percentage threshold (+/- 1.0% change over slope period)
        vol_lookback_weeks: Average volume lookback in weeks (default 4 weeks = 20 bars)
        vol_mult: Minimum volume multiple for strong breakout confirmation (default 2.0x)
        is_daily: True if chart timeframe is Daily (converts 1 week -> 5 bars), False for Weekly

    Returns:
        WeinsteinResult with annotated stages and breakout flags.
    """
    if isinstance(data, pd.DataFrame):
        p_df = pl.from_pandas(data)
    else:
        p_df = data

    cols = {c.lower(): c for c in p_df.columns}
    close_col = cols.get("close", "close")
    vol_col = cols.get("volume", "volume") if "volume" in cols else None

    closes = p_df[close_col].to_numpy().astype(np.float64)
    vols = p_df[vol_col].to_numpy().astype(np.float64) if vol_col else np.ones_like(closes)
    n = len(closes)

    bars_per_week = 5 if is_daily else 1
    ma_len = max(2, int(ma_weeks * bars_per_week))
    slope_len = max(1, int(slope_weeks * bars_per_week))
    vol_len = max(1, int(vol_lookback_weeks * bars_per_week))

    if n < ma_len + slope_len:
        empty_df = p_df.with_columns([
            pl.lit(0).alias("weinstein_stage"),
            pl.lit(STAGE_NAMES[0]).alias("weinstein_stage_name"),
            pl.lit(np.nan).alias("weinstein_ma"),
            pl.lit(0.0).alias("weinstein_slope_pct"),
            pl.lit(1.0).alias("weinstein_vol_ratio"),
            pl.lit(False).alias("stage2_breakout"),
            pl.lit(False).alias("stage4_breakdown"),
        ])
        return WeinsteinResult(
            df=empty_df,
            current_stage=0,
            stage_name=STAGE_NAMES[0],
            ma_value=float(closes[-1]) if n > 0 else 0.0,
            ma_slope_pct=0.0,
            volume_ratio=1.0,
            is_breakout=False,
            is_breakdown=False,
        )

    # 1. Vectorized 30-week SMA
    # Using cumsum for exact fast rolling mean
    cumsum = np.cumsum(np.insert(closes, 0, 0.0))
    sma = np.full(n, np.nan, dtype=np.float64)
    sma[ma_len - 1:] = (cumsum[ma_len:] - cumsum[:-ma_len]) / ma_len

    # 2. Vectorized Slope Percentage over slope_len bars
    slope_pct = np.zeros(n, dtype=np.float64)
    valid_slope_mask = ~np.isnan(sma) & (np.arange(n) >= ma_len - 1 + slope_len)
    for i in np.where(valid_slope_mask)[0]:
        prev_ma = sma[i - slope_len]
        if prev_ma > 0:
            slope_pct[i] = ((sma[i] / prev_ma) - 1.0) * 100.0

    # slope_state: +1 (rising), 0 (flat), -1 (falling)
    slope_state = np.zeros(n, dtype=np.int32)
    slope_state[slope_pct > flat_band_pct] = 1
    slope_state[slope_pct < -flat_band_pct] = -1

    # 3. Vectorized Volume Ratio
    vol_cumsum = np.cumsum(np.insert(vols, 0, 0.0))
    vol_avg = np.full(n, np.nan, dtype=np.float64)
    vol_avg[vol_len:] = (vol_cumsum[vol_len:-1] - vol_cumsum[:-vol_len - 1]) / vol_len

    vol_ratio = np.ones(n, dtype=np.float64)
    valid_vol = ~np.isnan(vol_avg) & (vol_avg > 0)
    vol_ratio[valid_vol] = vols[valid_vol] / vol_avg[valid_vol]

    # 4. State Machine Evaluation (Fast sequential transition across bars)
    stages = np.zeros(n, dtype=np.int32)
    stage2_breakout = np.zeros(n, dtype=bool)
    stage4_breakdown = np.zeros(n, dtype=bool)

    current_stage = 0
    start_idx = ma_len - 1 + slope_len

    for i in range(start_idx, n):
        c = closes[i]
        m = sma[i]
        s = slope_state[i]

        to_s1 = False
        to_s2 = False
        to_s3 = False
        to_s4 = False

        if current_stage == 0:
            if c > m and s == 1:
                to_s2 = True
            elif c < m and s == -1:
                to_s4 = True
            elif s == 0:
                to_s1 = True
        elif current_stage == 1:
            # Stage 1 -> Stage 2 breakout: price clears MA, MA is not falling, and preferably volume expands
            if c > m and s >= 0:
                to_s2 = True
            elif c < m and s == -1:
                to_s4 = True
        elif current_stage == 2:
            # Stage 2 -> Stage 3 top: price drops below MA while MA flattens or rolls over
            if c < m and s <= 0:
                to_s3 = True
        elif current_stage == 3:
            # Stage 3 -> Stage 4 breakdown: price breaks below MA while MA is not rising
            if c < m and s <= 0:
                to_s4 = True
            elif c > m and s >= 0:
                to_s2 = True
        elif current_stage == 4:
            # Stage 4 -> Stage 1 base: price recovers above MA while MA flattens
            if c > m and s >= 0:
                to_s1 = True

        prev_stage = current_stage
        if to_s1:
            current_stage = 1
        elif to_s2:
            current_stage = 2
        elif to_s3:
            current_stage = 3
        elif to_s4:
            current_stage = 4

        stages[i] = current_stage

        if prev_stage != 2 and current_stage == 2:
            stage2_breakout[i] = True
        elif prev_stage != 4 and current_stage == 4:
            stage4_breakdown[i] = True

    stage_names_col = [STAGE_NAMES.get(s, "Undetermined") for s in stages]

    out_df = p_df.with_columns([
        pl.Series("weinstein_stage", stages),
        pl.Series("weinstein_stage_name", stage_names_col),
        pl.Series("weinstein_ma", np.round(sma, 2)),
        pl.Series("weinstein_slope_pct", np.round(slope_pct, 2)),
        pl.Series("weinstein_vol_ratio", np.round(vol_ratio, 2)),
        pl.Series("stage2_breakout", stage2_breakout),
        pl.Series("stage4_breakdown", stage4_breakdown),
    ])

    last_stage = int(stages[-1])
    return WeinsteinResult(
        df=out_df,
        current_stage=last_stage,
        stage_name=STAGE_NAMES.get(last_stage, "Undetermined"),
        ma_value=round(float(sma[-1]), 2) if not np.isnan(sma[-1]) else 0.0,
        ma_slope_pct=round(float(slope_pct[-1]), 2),
        volume_ratio=round(float(vol_ratio[-1]), 2),
        is_breakout=bool(stage2_breakout[-1]),
        is_breakdown=bool(stage4_breakdown[-1]),
    )
