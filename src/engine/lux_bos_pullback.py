"""
File: src/engine/lux_bos_pullback.py
Purpose: Valid Break of Structure (BOS) Pullback Retest Engine ported from LuxAlgo Pine Script v6.
Features:
  - Detects structural swings (pivots) across a lookback window.
  - Multi-stage setup tracking:
      * Stage 1 (Initial Breakout): Candle closes beyond swing high/low by at least min_extension.
      * Extreme Extension: New high/low marked and must hold untouched for >= min_untouched_bars.
      * Stage 2 (Valid Retest): Price pulls back and touches the exact previous structure line.
      * Confirmation: Price turns from the retest level and breaks beyond the new extreme (continuation BOS).
  - Dramatically filters out fakeouts and structural traps.
  - Vectorized and state-machine optimized with Polars & NumPy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd
import polars as pl


@dataclass
class ValidBOSSetup:
    direction: int  # +1 Bullish, -1 Bearish
    stage: int      # 1: Initial break & extending, 2: Retest confirmed, 3: Completed BOS continuation
    reference_price: float
    target_price: float
    start_bar: int
    extreme_bar: int
    retest_bar: int | None = None
    completed_bar: int | None = None


@dataclass
class ValidBOSResult:
    df: pl.DataFrame
    setups: list[ValidBOSSetup] = field(default_factory=list)
    latest_bull_bos: bool = False
    latest_bear_bos: bool = False
    latest_retest_level: float | None = None

    def to_pandas(self) -> pd.DataFrame:
        return self.df.to_pandas()


def calculate_valid_bos_pullback(
    data: pl.DataFrame | pd.DataFrame,
    left_bars: int = 3,
    right_bars: int = 3,
    swing_lookback: int = 48,
    min_untouched_bars: int = 5,
    max_wait_bars: int = 120,
) -> ValidBOSResult:
    """
    Compute Valid BOS Pullback setups and continuation confirmations.

    Parameters:
        data: DataFrame containing 'high', 'low', 'close'
        left_bars: Bars required to left of pivot
        right_bars: Bars required to right of pivot
        swing_lookback: Historical window to anchor previous structural pivots
        min_untouched_bars: Minimum bars after break where price does not touch broken level
        max_wait_bars: Timeout after which incomplete setup is discarded

    Returns:
        ValidBOSResult containing annotated Polars DataFrame and list of setups.
    """
    if isinstance(data, pd.DataFrame):
        p_df = pl.from_pandas(data)
    else:
        p_df = data

    cols = {c.lower(): c for c in p_df.columns}
    high_col = cols.get("high", "high")
    low_col = cols.get("low", "low")
    close_col = cols.get("close", "close")

    highs = p_df[high_col].to_numpy().astype(np.float64)
    lows = p_df[low_col].to_numpy().astype(np.float64)
    closes = p_df[close_col].to_numpy().astype(np.float64)
    n = len(closes)

    if n < swing_lookback + right_bars:
        empty_df = p_df.with_columns([
            pl.lit(False).alias("valid_bos_bull"),
            pl.lit(False).alias("valid_bos_bear"),
            pl.lit(False).alias("valid_pullback_touch"),
            pl.lit(np.nan).alias("bos_reference_level"),
            pl.lit(np.nan).alias("bos_target_level"),
        ])
        return ValidBOSResult(df=empty_df)

    # 1. Pivot Highs & Lows
    piv_h = np.zeros(n, dtype=bool)
    piv_l = np.zeros(n, dtype=bool)
    for i in range(left_bars, n - right_bars):
        h_val = highs[i]
        l_val = lows[i]
        if np.all(h_val >= highs[i - left_bars:i]) and np.all(h_val > highs[i + 1:i + right_bars + 1]):
            piv_h[i] = True
        if np.all(l_val <= lows[i - left_bars:i]) and np.all(l_val < lows[i + 1:i + right_bars + 1]):
            piv_l[i] = True

    # 2. Setup Tracking State Machine
    active_setups: list[dict] = []
    completed_setups: list[ValidBOSSetup] = []

    bull_bos_arr = np.zeros(n, dtype=bool)
    bear_bos_arr = np.zeros(n, dtype=bool)
    retest_touch_arr = np.zeros(n, dtype=bool)
    ref_level_arr = np.full(n, np.nan, dtype=np.float64)
    target_level_arr = np.full(n, np.nan, dtype=np.float64)

    high_pivots: list[tuple[int, float]] = []  # (bar_index, price)
    low_pivots: list[tuple[int, float]] = []

    for i in range(n):
        # Register confirmed pivots from right_bars ago
        if i >= right_bars:
            p_idx = i - right_bars
            if piv_h[p_idx]:
                high_pivots.append((p_idx, highs[p_idx]))
            if piv_l[p_idx]:
                low_pivots.append((p_idx, lows[p_idx]))

        # Trim pivots outside swing_lookback
        high_pivots = [p for p in high_pivots if i - p[0] <= swing_lookback]
        low_pivots = [p for p in low_pivots if i - p[0] <= swing_lookback]

        c_close = closes[i]
        c_high = highs[i]
        c_low = lows[i]

        # Check for new initial breakouts of confirmed pivots
        # Bullish break
        for p_bar, p_lvl in high_pivots:
            if c_close > p_lvl:
                # Check if setup already exists for this level
                if not any(s["ref_price"] == p_lvl and s["direction"] == 1 for s in active_setups):
                    active_setups.append({
                        "direction": 1,
                        "stage": 1,
                        "start_bar": i,
                        "ref_price": p_lvl,
                        "target_price": c_high,
                        "extreme_bar": i,
                        "extreme_confirmed": False,
                        "clean_bars": 0,
                    })

        # Bearish break
        for p_bar, p_lvl in low_pivots:
            if c_close < p_lvl:
                if not any(s["ref_price"] == p_lvl and s["direction"] == -1 for s in active_setups):
                    active_setups.append({
                        "direction": -1,
                        "stage": 1,
                        "start_bar": i,
                        "ref_price": p_lvl,
                        "target_price": c_low,
                        "extreme_bar": i,
                        "extreme_confirmed": False,
                        "clean_bars": 0,
                    })

        # Update active setups
        surviving_setups = []
        for s in active_setups:
            age = i - s["start_bar"]
            if age > max_wait_bars:
                continue

            ref_p = s["ref_price"]

            if s["direction"] == 1:  # Bullish
                # Invalidation: close substantially below reference
                if c_close < ref_p * 0.995:
                    continue

                if s["stage"] == 1:
                    if c_high > s["target_price"]:
                        s["target_price"] = c_high
                        s["extreme_bar"] = i
                        s["extreme_confirmed"] = False

                    if i - s["extreme_bar"] >= right_bars:
                        s["extreme_confirmed"] = True

                    # Retest touch: low touches reference level
                    touched = (c_low <= ref_p) and (c_high >= ref_p)
                    if touched and s["extreme_confirmed"] and s["clean_bars"] >= min_untouched_bars:
                        s["stage"] = 2
                        s["retest_bar"] = i
                        retest_touch_arr[i] = True
                        ref_level_arr[i] = ref_p
                        target_level_arr[i] = s["target_price"]

                    s["clean_bars"] = 0 if touched else s["clean_bars"] + 1

                elif s["stage"] == 2:
                    # Stage 2: Retested -> Waiting for breakout above new target
                    if c_close > s["target_price"]:
                        # Confirmed continuation BOS
                        bull_bos_arr[i] = True
                        s["stage"] = 3
                        s["completed_bar"] = i
                        completed_setups.append(ValidBOSSetup(
                            direction=1,
                            stage=3,
                            reference_price=ref_p,
                            target_price=s["target_price"],
                            start_bar=s["start_bar"],
                            extreme_bar=s["extreme_bar"],
                            retest_bar=s.get("retest_bar"),
                            completed_bar=i,
                        ))
                        continue  # Finished

            else:  # Bearish
                if c_close > ref_p * 1.005:
                    continue

                if s["stage"] == 1:
                    if c_low < s["target_price"]:
                        s["target_price"] = c_low
                        s["extreme_bar"] = i
                        s["extreme_confirmed"] = False

                    if i - s["extreme_bar"] >= right_bars:
                        s["extreme_confirmed"] = True

                    touched = (c_high >= ref_p) and (c_low <= ref_p)
                    if touched and s["extreme_confirmed"] and s["clean_bars"] >= min_untouched_bars:
                        s["stage"] = 2
                        s["retest_bar"] = i
                        retest_touch_arr[i] = True
                        ref_level_arr[i] = ref_p
                        target_level_arr[i] = s["target_price"]

                    s["clean_bars"] = 0 if touched else s["clean_bars"] + 1

                elif s["stage"] == 2:
                    if c_close < s["target_price"]:
                        bear_bos_arr[i] = True
                        s["stage"] = 3
                        s["completed_bar"] = i
                        completed_setups.append(ValidBOSSetup(
                            direction=-1,
                            stage=3,
                            reference_price=ref_p,
                            target_price=s["target_price"],
                            start_bar=s["start_bar"],
                            extreme_bar=s["extreme_bar"],
                            retest_bar=s.get("retest_bar"),
                            completed_bar=i,
                        ))
                        continue

            surviving_setups.append(s)

        active_setups = surviving_setups[-30:]

    out_df = p_df.with_columns([
        pl.Series("valid_bos_bull", bull_bos_arr),
        pl.Series("valid_bos_bear", bear_bos_arr),
        pl.Series("valid_pullback_touch", retest_touch_arr),
        pl.Series("bos_reference_level", ref_level_arr),
        pl.Series("bos_target_level", target_level_arr),
    ])

    latest_bull = bool(bull_bos_arr[-1])
    latest_bear = bool(bear_bos_arr[-1])
    latest_retest = float(ref_level_arr[-1]) if not np.isnan(ref_level_arr[-1]) else None

    return ValidBOSResult(
        df=out_df,
        setups=completed_setups,
        latest_bull_bos=latest_bull,
        latest_bear_bos=latest_bear,
        latest_retest_level=latest_retest,
    )
