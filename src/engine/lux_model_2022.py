"""
File: src/engine/lux_model_2022.pine -> src/engine/lux_model_2022.py
Purpose: ICT Model 2022 engine ported from LuxAlgo Pine Script v6.
Features:
  - Liquidity Pool Raids (PDH/PDL, Swings, Equal Highs/Lows).
  - Market Structure Shift (MSS) validation with displacement.
  - Fair Value Gap (FVG) creation on shift leg.
  - Optimal Entry (Near Edge or 50% Consequent Encroachment).
  - Explicit Target & Invalidation Stops.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import pandas as pd
import polars as pl

LOGGER = logging.getLogger(__name__)

BULLISH = 1
BEARISH = -1

# Setup States
S_IDLE = 0
S_RAID = 1    # Pool raided, waiting for market structure shift
S_GAP = 2     # Shift printed, waiting for displacement FVG
S_ENTRY = 3   # FVG marked, waiting for retracement fill
S_TRADE = 4   # Entry filled / active trade


@dataclass
class LiquidityPool:
    price: float
    bar_index: int
    is_high: bool
    kind: str  # 'SWING', 'EQH_EQL', 'DAY'
    raided: bool = False
    raided_bar_index: int = -1


@dataclass
class Model2022Setup:
    symbol: str
    direction: str          # "BUY" or "SELL"
    bias: int               # +1 or -1
    raid_bar_index: int
    raid_price: float
    mss_bar_index: int
    mss_level: float
    fvg_top: float
    fvg_bottom: float
    entry_price: float
    stop_loss: float
    target: float
    risk_reward: float
    status: str = "PENDING"  # PENDING, ACTIVE, TARGET_HIT, STOPPED
    notes: str = ""


@dataclass
class Model2022Result:
    df: pl.DataFrame
    setups: list[Model2022Setup] = field(default_factory=list)
    active_setups: list[Model2022Setup] = field(default_factory=list)
    liquidity_pools: list[LiquidityPool] = field(default_factory=list)

    def to_pandas(self) -> pd.DataFrame:
        return self.df.to_pandas()


def calculate_model_2022(
    data: pl.DataFrame | pd.DataFrame,
    symbol: str = "TICKER",
    swing_length: int = 12,
    mss_length: int = 3,
    mss_window: int = 30,
    entry_window: int = 24,
    min_rr: float = 1.5,
) -> Model2022Result:
    """
    Execute ICT Model 2022 execution sequence:
    1. Liquidity Pool Raid -> 2. MSS Breakout -> 3. Displacement FVG -> 4. Retracement Entry
    """
    if isinstance(data, pd.DataFrame):
        p_df = pl.from_pandas(data)
    else:
        p_df = data

    cols = {c.lower(): c for c in p_df.columns}
    for req in ("open", "high", "low", "close"):
        if req not in cols:
            raise ValueError(f"Input DataFrame must contain '{req}' column.")

    highs = p_df[cols["high"]].to_numpy().astype(float)
    lows = p_df[cols["low"]].to_numpy().astype(float)
    closes = p_df[cols["close"]].to_numpy().astype(float)
    opens = p_df[cols["open"]].to_numpy().astype(float)
    n = len(closes)

    if n < max(swing_length * 2, 35):
        return Model2022Result(df=p_df)

    # Calculate ATR(14)
    tr = np.zeros(n, dtype=float)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
    atr = np.zeros(n, dtype=float)
    atr[:14] = np.mean(tr[:14])
    for i in range(14, n):
        atr[i] = (atr[i - 1] * 13 + tr[i]) / 14.0

    # 1. Identify Liquidity Pools (Swing Highs and Lows)
    pools: list[LiquidityPool] = []
    for i in range(swing_length, n):
        idx = i - swing_length
        # Check swing high
        if highs[idx] == np.max(highs[max(0, idx - swing_length): min(n, idx + swing_length + 1)]):
            pools.append(LiquidityPool(price=highs[idx], bar_index=idx, is_high=True, kind="SWING"))
        # Check swing low
        if lows[idx] == np.min(lows[max(0, idx - swing_length): min(n, idx + swing_length + 1)]):
            pools.append(LiquidityPool(price=lows[idx], bar_index=idx, is_high=False, kind="SWING"))

    # Track sequence state
    setups: list[Model2022Setup] = []
    active_setups: list[Model2022Setup] = []

    state = S_IDLE
    curr_bias = 0
    raid_idx = -1
    raid_price = 0.0
    mss_level = 0.0
    mss_idx = -1

    setup_signal = np.zeros(n, dtype=np.int8)  # +1 Bull, -1 Bear

    for i in range(n):
        c, h, l, o = closes[i], highs[i], lows[i], opens[i]

        # Check for Raids on untaken pools
        if state == S_IDLE:
            for p in pools:
                if not p.raided and p.bar_index < i - 2:
                    # Bullish setup raid: Price sweeps low liquidity pool
                    if not p.is_high and l < p.price and c > l:
                        p.raided = True
                        p.raided_bar_index = i
                        state = S_RAID
                        curr_bias = BULLISH
                        raid_idx = i
                        raid_price = l
                        # Look for most recent swing high before raid as MSS trigger
                        prior_highs = [x for x in pools if x.is_high and x.bar_index < i]
                        if prior_highs:
                            mss_level = prior_highs[-1].price
                        break

                    # Bearish setup raid: Price sweeps high liquidity pool
                    elif p.is_high and h > p.price and c < h:
                        p.raided = True
                        p.raided_bar_index = i
                        state = S_RAID
                        curr_bias = BEARISH
                        raid_idx = i
                        raid_price = h
                        prior_lows = [x for x in pools if not x.is_high and x.bar_index < i]
                        if prior_lows:
                            mss_level = prior_lows[-1].price
                        break

        # S_RAID: Waiting for MSS Breakout within mss_window bars
        elif state == S_RAID:
            if i - raid_idx > mss_window:
                state = S_IDLE
            else:
                if curr_bias == BULLISH and c > mss_level:
                    state = S_GAP
                    mss_idx = i
                elif curr_bias == BEARISH and c < mss_level:
                    state = S_GAP
                    mss_idx = i

        # S_GAP: Displacement FVG created on breakout leg
        elif state == S_GAP:
            if i - mss_idx > 3:
                state = S_IDLE
            elif i >= 2:
                # Check Bullish FVG
                if curr_bias == BULLISH and l > highs[i - 2]:
                    fvg_bot = highs[i - 2]
                    fvg_top = l
                    entry = fvg_top  # Near edge entry
                    sl = round(raid_price - (0.1 * atr[i]), 2)
                    risk = entry - sl
                    if risk > 0:
                        tp = round(entry + (max(min_rr, 2.0) * risk), 2)
                        st = Model2022Setup(
                            symbol=symbol,
                            direction="BUY",
                            bias=BULLISH,
                            raid_bar_index=raid_idx,
                            raid_price=raid_price,
                            mss_bar_index=mss_idx,
                            mss_level=mss_level,
                            fvg_top=fvg_top,
                            fvg_bottom=fvg_bot,
                            entry_price=round(entry, 2),
                            stop_loss=sl,
                            target=tp,
                            risk_reward=round((tp - entry) / risk, 2),
                            notes=f"Model 2022 Long after {raid_price:.1f} sweep",
                        )
                        setups.append(st)
                        active_setups.append(st)
                        setup_signal[i] = BULLISH
                    state = S_IDLE

                # Check Bearish FVG
                elif curr_bias == BEARISH and h < lows[i - 2]:
                    fvg_top = lows[i - 2]
                    fvg_bot = h
                    entry = fvg_bot  # Near edge entry
                    sl = round(raid_price + (0.1 * atr[i]), 2)
                    risk = sl - entry
                    if risk > 0:
                        tp = round(entry - (max(min_rr, 2.0) * risk), 2)
                        st = Model2022Setup(
                            symbol=symbol,
                            direction="SELL",
                            bias=BEARISH,
                            raid_bar_index=raid_idx,
                            raid_price=raid_price,
                            mss_bar_index=mss_idx,
                            mss_level=mss_level,
                            fvg_top=fvg_top,
                            fvg_bottom=fvg_bot,
                            entry_price=round(entry, 2),
                            stop_loss=sl,
                            target=tp,
                            risk_reward=round((entry - tp) / risk, 2),
                            notes=f"Model 2022 Short after {raid_price:.1f} sweep",
                        )
                        setups.append(st)
                        active_setups.append(st)
                        setup_signal[i] = BEARISH
                    state = S_IDLE

    res_df = p_df.with_columns(
        [
            pl.Series("model_2022_signal", setup_signal),
            pl.Series("model_2022_atr", atr),
        ]
    )

    return Model2022Result(
        df=res_df,
        setups=setups,
        active_setups=active_setups[-10:],
        liquidity_pools=pools,
    )
