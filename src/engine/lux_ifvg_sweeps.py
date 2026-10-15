"""
File: src/engine/lux_ifvg_sweeps.py
Purpose: Liquidity Sweeps & Inverted Fair Value Gaps (iFVG) ported from LuxAlgo Pine Script v6.
Features:
  - Vectorized detection of Swing Highs / Swing Lows via rolling window pivots.
  - Liquidity Sweeps: Wick-only penetrations of previous swing highs/lows where the body closes back within range.
  - Inverted FVGs (iFVGs): Detects standard 3-candle Fair Value Gaps and flips them to support/resistance breakers
    once price closes through them.
  - High performance calculation via Polars & NumPy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import polars as pl


@dataclass
class SweepEvent:
    bar_index: int
    price: float
    direction: str  # "BEARISH_SWEEP" (swept high with upper wick) or "BULLISH_SWEEP" (swept low with lower wick)
    timestamp: str | None = None


@dataclass
class IFVGZone:
    start_index: int
    inversion_index: int
    top: float
    bottom: float
    direction: str  # "BULLISH_IFVG" (support) or "BEARISH_IFVG" (resistance)
    mitigated: bool = False


@dataclass
class SweepsIFVGResult:
    df: pl.DataFrame
    sweeps: list[SweepEvent] = field(default_factory=list)
    ifvgs: list[IFVGZone] = field(default_factory=list)
    latest_sweep: SweepEvent | None = None
    latest_ifvg: IFVGZone | None = None

    def to_pandas(self) -> pd.DataFrame:
        return self.df.to_pandas()


def calculate_sweeps_ifvgs(
    data: pl.DataFrame | pd.DataFrame,
    swing_len: int = 5,
    vol_filter_mult: float = 0.3,
    atr_period: int = 14,
) -> SweepsIFVGResult:
    """
    Compute Liquidity Sweeps and Inverted Fair Value Gaps (iFVGs).

    Parameters:
        data: DataFrame containing 'open', 'high', 'low', 'close', 'volume'
        swing_len: Pivot swing detection length (left and right bars)
        vol_filter_mult: FVG minimum size as a multiple of ATR
        atr_period: ATR lookback period for filtering micro-gaps

    Returns:
        SweepsIFVGResult with Polars DataFrame enriched with sweep and iFVG signals.
    """
    if isinstance(data, pd.DataFrame):
        p_df = pl.from_pandas(data)
    else:
        p_df = data

    cols = {c.lower(): c for c in p_df.columns}
    high_col = cols.get("high", "high")
    low_col = cols.get("low", "low")
    close_col = cols.get("close", "close")
    open_col = cols.get("open", "open")

    highs = p_df[high_col].to_numpy().astype(np.float64)
    lows = p_df[low_col].to_numpy().astype(np.float64)
    closes = p_df[close_col].to_numpy().astype(np.float64)
    opens = p_df[open_col].to_numpy().astype(np.float64)
    n = len(closes)

    if n < max(swing_len * 2 + 1, atr_period + 1):
        empty_df = p_df.with_columns([
            pl.lit(False).alias("sweep_high"),
            pl.lit(False).alias("sweep_low"),
            pl.lit(False).alias("ifvg_bullish"),
            pl.lit(False).alias("ifvg_bearish"),
            pl.lit(0.0).alias("ifvg_top"),
            pl.lit(0.0).alias("ifvg_bottom"),
        ])
        return SweepsIFVGResult(df=empty_df)

    # 1. Vectorized ATR calculation
    tr1 = highs[1:] - lows[1:]
    tr2 = np.abs(highs[1:] - closes[:-1])
    tr3 = np.abs(lows[1:] - closes[:-1])
    tr = np.empty(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    tr[1:] = np.maximum(tr1, np.maximum(tr2, tr3))

    # Rolling ATR
    atr = np.zeros(n, dtype=np.float64)
    if n >= atr_period:
        atr[atr_period - 1] = np.mean(tr[:atr_period])
        for i in range(atr_period, n):
            atr[i] = (atr[i - 1] * (atr_period - 1) + tr[i]) / atr_period
    else:
        atr[:] = np.mean(tr)

    # 2. Pivot Highs & Pivot Lows
    piv_h = np.zeros(n, dtype=bool)
    piv_l = np.zeros(n, dtype=bool)
    for i in range(swing_len, n - swing_len):
        h_val = highs[i]
        l_val = lows[i]
        if np.all(h_val >= highs[i - swing_len:i]) and np.all(h_val > highs[i + 1:i + swing_len + 1]):
            piv_h[i] = True
        if np.all(l_val <= lows[i - swing_len:i]) and np.all(l_val < lows[i + 1:i + swing_len + 1]):
            piv_l[i] = True

    # 3. Liquidity Sweeps
    # Bearish Sweep: price penetrates above previous swing high (high > pivot_high), but candle closes back below it (close < pivot_high).
    # Bullish Sweep: price penetrates below previous swing low (low < pivot_low), but candle closes back above it (close > pivot_low).
    sweep_high_arr = np.zeros(n, dtype=bool)
    sweep_low_arr = np.zeros(n, dtype=bool)
    sweeps_list: list[SweepEvent] = []

    # Active swing tracking
    active_highs: list[tuple[int, float]] = []  # (bar_index, price)
    active_lows: list[tuple[int, float]] = []

    # 4. FVG & iFVG Tracking
    # Standard FVG:
    # Bullish FVG: low[i] > high[i-2], gap = low[i] - high[i-2]
    # Bearish FVG: high[i] < low[i-2], gap = low[i-2] - high[i]
    active_fvgs: list[dict] = []  # dict(start_idx, top, bottom, is_bull)
    active_ifvgs: list[IFVGZone] = []

    ifvg_bull_arr = np.zeros(n, dtype=bool)
    ifvg_bear_arr = np.zeros(n, dtype=bool)
    ifvg_top_arr = np.zeros(n, dtype=np.float64)
    ifvg_bot_arr = np.zeros(n, dtype=np.float64)

    timestamps = p_df["date"].to_list() if "date" in p_df.columns else (
        p_df["datetime"].to_list() if "datetime" in p_df.columns else None
    )

    for i in range(n):
        # Register confirmed pivots from swing_len bars ago
        if i >= swing_len:
            p_idx = i - swing_len
            if piv_h[p_idx]:
                active_highs.append((p_idx, highs[p_idx]))
            if piv_l[p_idx]:
                active_lows.append((p_idx, lows[p_idx]))

        c_close = closes[i]
        c_high = highs[i]
        c_low = lows[i]

        # Check for sweeps against active swing highs
        retained_highs = []
        for idx, p_price in active_highs:
            if c_high > p_price:
                if c_close < p_price:
                    # Liquidity sweep of high (wick sweep)
                    sweep_high_arr[i] = True
                    t_str = str(timestamps[i]) if timestamps else None
                    sweeps_list.append(SweepEvent(bar_index=i, price=float(p_price), direction="BEARISH_SWEEP", timestamp=t_str))
                # Broken or swept high is consumed
                continue
            retained_highs.append((idx, p_price))
        active_highs = retained_highs[-50:]  # Keep recent

        # Check for sweeps against active swing lows
        retained_lows = []
        for idx, p_price in active_lows:
            if c_low < p_price:
                if c_close > p_price:
                    # Liquidity sweep of low (wick sweep)
                    sweep_low_arr[i] = True
                    t_str = str(timestamps[i]) if timestamps else None
                    sweeps_list.append(SweepEvent(bar_index=i, price=float(p_price), direction="BULLISH_SWEEP", timestamp=t_str))
                # Broken or swept low is consumed
                continue
            retained_lows.append((idx, p_price))
        active_lows = retained_lows[-50:]

        # Detect new standard FVGs at bar i (using i, i-1, i-2)
        if i >= 2:
            gap_threshold = atr[i] * vol_filter_mult
            # Bullish FVG
            if c_low > highs[i - 2]:
                gap_size = c_low - highs[i - 2]
                if gap_size > gap_threshold:
                    active_fvgs.append({
                        "start_idx": i - 2,
                        "top": float(c_low),
                        "bottom": float(highs[i - 2]),
                        "is_bull": True,
                    })
            # Bearish FVG
            elif c_high < lows[i - 2]:
                gap_size = lows[i - 2] - c_high
                if gap_size > gap_threshold:
                    active_fvgs.append({
                        "start_idx": i - 2,
                        "top": float(lows[i - 2]),
                        "bottom": float(c_high),
                        "is_bull": False,
                    })

        # Process active FVGs for Inversion (iFVG)
        remaining_fvgs = []
        for f in active_fvgs:
            if f["is_bull"]:
                # If a bullish FVG is closed below its bottom, it inverts to Bearish iFVG (Resistance)
                if c_close < f["bottom"]:
                    ifvg_bear_arr[i] = True
                    ifvg_top_arr[i] = f["top"]
                    ifvg_bot_arr[i] = f["bottom"]
                    zone = IFVGZone(
                        start_index=f["start_idx"],
                        inversion_index=i,
                        top=f["top"],
                        bottom=f["bottom"],
                        direction="BEARISH_IFVG",
                    )
                    active_ifvgs.append(zone)
                    continue  # Inverted, no longer regular FVG
            else:
                # If a bearish FVG is closed above its top, it inverts to Bullish iFVG (Support)
                if c_close > f["top"]:
                    ifvg_bull_arr[i] = True
                    ifvg_top_arr[i] = f["top"]
                    ifvg_bot_arr[i] = f["bottom"]
                    zone = IFVGZone(
                        start_index=f["start_idx"],
                        inversion_index=i,
                        top=f["top"],
                        bottom=f["bottom"],
                        direction="BULLISH_IFVG",
                    )
                    active_ifvgs.append(zone)
                    continue  # Inverted, no longer regular FVG

            # Discard FVGs older than 300 bars
            if i - f["start_idx"] <= 300:
                remaining_fvgs.append(f)
        active_fvgs = remaining_fvgs[-60:]

        # Mark mitigation of active iFVGs
        for ifvg in active_ifvgs:
            if not ifvg.mitigated:
                if ifvg.direction == "BEARISH_IFVG" and c_close > ifvg.top:
                    ifvg.mitigated = True
                elif ifvg.direction == "BULLISH_IFVG" and c_close < ifvg.bottom:
                    ifvg.mitigated = True

    # Assemble Polars DataFrame
    out_df = p_df.with_columns([
        pl.Series("sweep_high", sweep_high_arr),
        pl.Series("sweep_low", sweep_low_arr),
        pl.Series("ifvg_bullish", ifvg_bull_arr),
        pl.Series("ifvg_bearish", ifvg_bear_arr),
        pl.Series("ifvg_top", np.round(ifvg_top_arr, 2)),
        pl.Series("ifvg_bottom", np.round(ifvg_bot_arr, 2)),
    ])

    latest_swp = sweeps_list[-1] if sweeps_list else None
    latest_iz = active_ifvgs[-1] if active_ifvgs else None

    return SweepsIFVGResult(
        df=out_df,
        sweeps=sweeps_list,
        ifvgs=active_ifvgs,
        latest_sweep=latest_swp,
        latest_ifvg=latest_iz,
    )
