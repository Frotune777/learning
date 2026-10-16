"""
File: src/engine/smc.py
Purpose: Smart Money Concepts (SMC) engine aligned with LuxAlgo logic.
Fixes: Correct 2-sided pivot detection, accurate FVG thresholds, proper OB mitigation,
       and dealing-range scoped Premium/Discount calculations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import polars as pl
from scipy.signal import argrelextrema

try:
    import talib as _talib  # type: ignore[import-untyped]
    _HAS_TALIB = True
except ImportError:
    _HAS_TALIB = False

LOGGER = logging.getLogger(__name__)

BULLISH = 1
BEARISH = -1


@dataclass
class Pivot:
    current_level: float = float("nan")
    last_level: float = float("nan")
    crossed: bool = False
    bar_index: int = -1


@dataclass
class OrderBlock:
    bar_high: float
    bar_low: float
    bar_index: int
    bias: int  # +1 Bullish (Demand), -1 Bearish (Supply)
    is_internal: bool = False
    mitigated: bool = False
    mitigated_bar_index: int = -1


@dataclass
class FairValueGap:
    top: float
    bottom: float
    bias: int
    bar_index: int
    mitigated: bool = False
    mitigated_bar_index: int = -1


@dataclass
class StructureBreakout:
    tag: str  # 'BOS' or 'CHoCH'
    bias: int
    price_level: float
    bar_index: int
    pivot_bar_index: int
    is_internal: bool


@dataclass
class SMCResult:
    df: pl.DataFrame
    order_blocks: list[OrderBlock] = field(default_factory=list)
    active_order_blocks: list[OrderBlock] = field(default_factory=list)
    fair_value_gaps: list[FairValueGap] = field(default_factory=list)
    active_fair_value_gaps: list[FairValueGap] = field(default_factory=list)
    structure_breaks: list[StructureBreakout] = field(default_factory=list)
    premium_zone: tuple[float, float] = (float("nan"), float("nan"))
    equilibrium_level: float = float("nan")
    discount_zone: tuple[float, float] = (float("nan"), float("nan"))
    current_swing_trend: int = 0
    current_internal_trend: int = 0

    def to_pandas(self) -> pd.DataFrame:
        return self.df.to_pandas()


def _compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(high)
    if n == 0:
        return np.array([], dtype=float)

    if _HAS_TALIB and n >= period:
        atr = _talib.ATR(high, low, close, timeperiod=period)
        valid_mask = ~np.isnan(atr)
        if np.any(valid_mask):
            atr[~valid_mask] = atr[valid_mask][0]
            return atr

    tr = np.zeros(n, dtype=float)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))

    atr = np.zeros(n, dtype=float)
    w = min(period, n)
    atr[:w] = np.mean(tr[:w])
    for i in range(w, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def calculate_smc(
    data: pl.DataFrame | pd.DataFrame,
    swing_length: int = 20,
    internal_length: int = 5,
    max_order_blocks: int = 10,
    close_mitigation: bool = False,
) -> SMCResult:
    # 1. Normalize columns
    if isinstance(data, pd.DataFrame):
        p_df = pl.from_pandas(data)
    else:
        p_df = data

    cols = {col.lower(): col for col in p_df.columns}
    for req in ("open", "high", "low", "close"):
        if req not in cols:
            raise ValueError(f"Input DataFrame must contain '{req}' column.")

    opens = p_df[cols["open"]].to_numpy().astype(float)
    highs = p_df[cols["high"]].to_numpy().astype(float)
    lows = p_df[cols["low"]].to_numpy().astype(float)
    closes = p_df[cols["close"]].to_numpy().astype(float)
    n_bars = len(closes)

    if n_bars < max(swing_length * 2, 5):
        return SMCResult(df=p_df)

    atr = _compute_atr(highs, lows, closes, period=14)

    # 2. Pre-calculate true 2-sided local extrema
    swing_high_indices = set(argrelextrema(highs, np.greater, order=swing_length)[0])
    swing_low_indices = set(argrelextrema(lows, np.less, order=swing_length)[0])
    internal_high_indices = set(argrelextrema(highs, np.greater, order=internal_length)[0])
    internal_low_indices = set(argrelextrema(lows, np.less, order=internal_length)[0])

    # Output signal buffers
    swing_bos = np.zeros(n_bars, dtype=np.int8)
    swing_choch = np.zeros(n_bars, dtype=np.int8)
    internal_bos = np.zeros(n_bars, dtype=np.int8)
    internal_choch = np.zeros(n_bars, dtype=np.int8)
    bullish_fvg = np.zeros(n_bars, dtype=bool)
    bearish_fvg = np.zeros(n_bars, dtype=bool)
    swing_trend_arr = np.zeros(n_bars, dtype=np.int8)
    internal_trend_arr = np.zeros(n_bars, dtype=np.int8)

    swing_high = Pivot()
    swing_low = Pivot()
    internal_high = Pivot()
    internal_low = Pivot()

    swing_trend_bias = 0
    internal_trend_bias = 0

    all_order_blocks: list[OrderBlock] = []
    active_order_blocks: list[OrderBlock] = []
    all_fvgs: list[FairValueGap] = []
    active_fvgs: list[FairValueGap] = []
    structure_breaks: list[StructureBreakout] = []

    cum_body = 0.0

    # 3. Main chronological loop
    for i in range(n_bars):
        c, h, l = closes[i], highs[i], lows[i]

        # Confirm Swing Pivots (available at i - swing_length)
        if i >= swing_length:
            p_idx = i - swing_length
            if p_idx in swing_high_indices:
                swing_high.last_level = swing_high.current_level
                swing_high.current_level = highs[p_idx]
                swing_high.crossed = False
                swing_high.bar_index = p_idx
            if p_idx in swing_low_indices:
                swing_low.last_level = swing_low.current_level
                swing_low.current_level = lows[p_idx]
                swing_low.crossed = False
                swing_low.bar_index = p_idx

        # Confirm Internal Pivots (available at i - internal_length)
        if i >= internal_length:
            p_idx = i - internal_length
            if p_idx in internal_high_indices:
                internal_high.last_level = internal_high.current_level
                internal_high.current_level = highs[p_idx]
                internal_high.crossed = False
                internal_high.bar_index = p_idx
            if p_idx in internal_low_indices:
                internal_low.last_level = internal_low.current_level
                internal_low.current_level = lows[p_idx]
                internal_low.crossed = False
                internal_low.bar_index = p_idx

        # Internal Structure Breaks
        if not np.isnan(internal_high.current_level) and not internal_high.crossed and c > internal_high.current_level:
            tag = "CHoCH" if internal_trend_bias == BEARISH else "BOS"
            internal_high.crossed = True
            internal_trend_bias = BULLISH
            if tag == "CHoCH":
                internal_choch[i] = BULLISH
            else:
                internal_bos[i] = BULLISH
            structure_breaks.append(StructureBreakout(tag, BULLISH, internal_high.current_level, i, internal_high.bar_index, True))

            # Store Bullish Internal OB
            p_start = max(0, internal_high.bar_index)
            min_k = p_start + int(np.argmin(lows[p_start:i + 1]))
            ob = OrderBlock(highs[min_k], lows[min_k], min_k, BULLISH, True)
            all_order_blocks.append(ob)
            active_order_blocks.append(ob)

        elif not np.isnan(internal_low.current_level) and not internal_low.crossed and c < internal_low.current_level:
            tag = "CHoCH" if internal_trend_bias == BULLISH else "BOS"
            internal_low.crossed = True
            internal_trend_bias = BEARISH
            if tag == "CHoCH":
                internal_choch[i] = BEARISH
            else:
                internal_bos[i] = BEARISH
            structure_breaks.append(StructureBreakout(tag, BEARISH, internal_low.current_level, i, internal_low.bar_index, True))

            # Store Bearish Internal OB
            p_start = max(0, internal_low.bar_index)
            max_k = p_start + int(np.argmax(highs[p_start:i + 1]))
            ob = OrderBlock(highs[max_k], lows[max_k], max_k, BEARISH, True)
            all_order_blocks.append(ob)
            active_order_blocks.append(ob)

        # Swing Structure Breaks
        if not np.isnan(swing_high.current_level) and not swing_high.crossed and c > swing_high.current_level:
            tag = "CHoCH" if swing_trend_bias == BEARISH else "BOS"
            swing_high.crossed = True
            swing_trend_bias = BULLISH
            if tag == "CHoCH":
                swing_choch[i] = BULLISH
            else:
                swing_bos[i] = BULLISH
            structure_breaks.append(StructureBreakout(tag, BULLISH, swing_high.current_level, i, swing_high.bar_index, False))

            p_start = max(0, swing_high.bar_index)
            min_k = p_start + int(np.argmin(lows[p_start:i + 1]))
            ob = OrderBlock(highs[min_k], lows[min_k], min_k, BULLISH, False)
            all_order_blocks.append(ob)
            active_order_blocks.append(ob)

        elif not np.isnan(swing_low.current_level) and not swing_low.crossed and c < swing_low.current_level:
            tag = "CHoCH" if swing_trend_bias == BULLISH else "BOS"
            swing_low.crossed = True
            swing_trend_bias = BEARISH
            if tag == "CHoCH":
                swing_choch[i] = BEARISH
            else:
                swing_bos[i] = BEARISH
            structure_breaks.append(StructureBreakout(tag, BEARISH, swing_low.current_level, i, swing_low.bar_index, False))

            p_start = max(0, swing_low.bar_index)
            max_k = p_start + int(np.argmax(highs[p_start:i + 1]))
            ob = OrderBlock(highs[max_k], lows[max_k], max_k, BEARISH, False)
            all_order_blocks.append(ob)
            active_order_blocks.append(ob)

        # Order Block Mitigation Check
        surviving_obs = []
        for ob in active_order_blocks:
            # Bullish OB (Demand): Mitigated when price violates the floor (bar_low)
            if ob.bias == BULLISH:
                breached = (c < ob.bar_low) if close_mitigation else (l < ob.bar_low)
                if breached:
                    ob.mitigated = True
                    ob.mitigated_bar_index = i
                else:
                    surviving_obs.append(ob)
            # Bearish OB (Supply): Mitigated when price violates the ceiling (bar_high)
            else:
                breached = (c > ob.bar_high) if close_mitigation else (h > ob.bar_high)
                if breached:
                    ob.mitigated = True
                    ob.mitigated_bar_index = i
                else:
                    surviving_obs.append(ob)
        active_order_blocks = surviving_obs[-max_order_blocks:]

        # Fair Value Gaps (FVG)
        surviving_fvgs = []
        for fvg in active_fvgs:
            if fvg.bias == BULLISH and l <= fvg.bottom:
                fvg.mitigated = True
                fvg.mitigated_bar_index = i
            elif fvg.bias == BEARISH and h >= fvg.top:
                fvg.mitigated = True
                fvg.mitigated_bar_index = i
            else:
                surviving_fvgs.append(fvg)
        active_fvgs = surviving_fvgs

        if i >= 2:
            prev_close, prev_open = closes[i - 1], opens[i - 1]
            body = abs(prev_close - prev_open)
            cum_body += body
            avg_body = cum_body / i

            # Bullish FVG
            if l > highs[i - 2] and prev_close > highs[i - 2] and body > avg_body:
                bullish_fvg[i] = True
                new_fvg = FairValueGap(top=l, bottom=highs[i - 2], bias=BULLISH, bar_index=i)
                all_fvgs.append(new_fvg)
                active_fvgs.append(new_fvg)
            # Bearish FVG
            elif h < lows[i - 2] and prev_close < lows[i - 2] and body > avg_body:
                bearish_fvg[i] = True
                new_fvg = FairValueGap(top=lows[i - 2], bottom=h, bias=BEARISH, bar_index=i)
                all_fvgs.append(new_fvg)
                active_fvgs.append(new_fvg)

        swing_trend_arr[i] = swing_trend_bias
        internal_trend_arr[i] = internal_trend_bias

    # 4. Premium / Discount on the Active Swing Range
    s_top = swing_high.current_level
    s_bot = swing_low.current_level
    if not np.isnan(s_top) and not np.isnan(s_bot) and s_top > s_bot:
        prem_zone = (0.95 * s_top + 0.05 * s_bot, s_top)
        eq_lvl = 0.5 * (s_top + s_bot)
        disc_zone = (s_bot, 0.95 * s_bot + 0.05 * s_top)
    else:
        prem_zone = (float("nan"), float("nan"))
        eq_lvl = float("nan")
        disc_zone = (float("nan"), float("nan"))

    # 5. Output DataFrame
    result_df = p_df.with_columns(
        [
            pl.Series("smc_swing_bos", swing_bos),
            pl.Series("smc_swing_choch", swing_choch),
            pl.Series("smc_internal_bos", internal_bos),
            pl.Series("smc_internal_choch", internal_choch),
            pl.Series("smc_fvg_bullish", bullish_fvg),
            pl.Series("smc_fvg_bearish", bearish_fvg),
            pl.Series("smc_swing_trend", swing_trend_arr),
            pl.Series("smc_internal_trend", internal_trend_arr),
            pl.Series("smc_atr", atr),
        ]
    )

    return SMCResult(
        df=result_df,
        order_blocks=all_order_blocks,
        active_order_blocks=active_order_blocks,
        fair_value_gaps=all_fvgs,
        active_fair_value_gaps=active_fvgs,
        structure_breaks=structure_breaks,
        premium_zone=prem_zone,
        equilibrium_level=eq_lvl,
        discount_zone=disc_zone,
        current_swing_trend=swing_trend_bias,
        current_internal_trend=internal_trend_bias,
    )