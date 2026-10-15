"""
File: src/engine/smc_decision.py
Purpose: Translates raw SMC structures into actionable Trading Calls with strict risk limits.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
from src.engine.smc import SMCResult, BULLISH, BEARISH

@dataclass
class TradingCall:
    symbol: str
    timestamp: str
    direction: str          # "BUY" or "SELL"
    setup_type: str         # "OB_DEMAND_TAP", "FVG_FILL", etc.
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward: float
    status: str = "PENDING"
    notes: str = ""

def generate_smc_call(symbol: str, smc_res: SMCResult, current_df: pd.DataFrame) -> TradingCall | None:
    if len(current_df) < 30:
        return None

    last_bar = current_df.iloc[-1]
    cmp = float(last_bar["close"])
    current_high = float(last_bar["high"])
    current_low = float(last_bar["low"])
    n_bars = len(current_df)

    # ATR calculation fallback
    if "smc_atr" in smc_res.df.columns:
        atr = float(smc_res.df["smc_atr"][-1])
    else:
        atr = current_high - current_low
    atr = max(atr, cmp * 0.005)  # Floor at 0.5% to avoid divide-by-zero

    swing_trend = smc_res.current_swing_trend
    eq_level = smc_res.equilibrium_level
    active_obs = smc_res.active_order_blocks
    active_fvgs = smc_res.active_fair_value_gaps
    recent_bar_cutoff = max(0, n_bars - 35)

    # -------------------------------------------------------------
    # 1. BULLISH SCENARIOS (Trend Bullish + Price in/near Discount)
    # -------------------------------------------------------------
    if swing_trend == BULLISH and (pd.isna(eq_level) or cmp <= eq_level * 1.02):
        # A. Bullish Order Block Test
        for ob in reversed(active_obs):
            if ob.bias == BULLISH and ob.bar_index >= recent_bar_cutoff:
                # Proximity check: Price is within 1% of OB High or inside OB
                if ob.bar_low <= cmp <= ob.bar_high * 1.015:
                    sl = round(ob.bar_low - (0.15 * atr), 2)
                    risk = cmp - sl
                    max_allowed_risk = cmp * 0.06  # Max 6% SL

                    if 0 < risk <= max_allowed_risk:
                        # Target opposing liquidity: Swing High or 2.5R minimum
                        tp1 = round(smc_res.premium_zone[1] if not pd.isna(smc_res.premium_zone[1]) else cmp + (2.5 * risk), 2)
                        tp1 = max(tp1, round(cmp + (2.0 * risk), 2))
                        tp2 = round(tp1 + (1.5 * risk), 2)
                        rr = round((tp1 - cmp) / risk, 2)

                        if rr >= 1.8:
                            return TradingCall(
                                symbol=symbol,
                                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                direction="BUY",
                                setup_type="OB_DEMAND_TAP",
                                entry_price=round(cmp, 2),
                                stop_loss=sl,
                                target_1=tp1,
                                target_2=tp2,
                                risk_reward=rr,
                                notes=f"Bullish OB ({ob.bar_low:.1f}-{ob.bar_high:.1f}) | Risk: {risk:.2f}"
                            )

        # B. Bullish FVG Fill
        for fvg in reversed(active_fvgs):
            if fvg.bias == BULLISH and fvg.bar_index >= recent_bar_cutoff:
                # Proximity check: Gap is within 1.5x ATR of CMP
                gap_distance = abs(cmp - fvg.top)
                if gap_distance <= (1.5 * atr) and fvg.bottom <= cmp <= fvg.top * 1.01:
                    sl = round(fvg.bottom - (0.15 * atr), 2)
                    risk = cmp - sl
                    max_allowed_risk = cmp * 0.06

                    if 0 < risk <= max_allowed_risk:
                        tp1 = round(smc_res.premium_zone[1] if not pd.isna(smc_res.premium_zone[1]) else cmp + (2.5 * risk), 2)
                        tp1 = max(tp1, round(cmp + (2.0 * risk), 2))
                        tp2 = round(tp1 + (1.5 * risk), 2)
                        rr = round((tp1 - cmp) / risk, 2)

                        if rr >= 1.8:
                            return TradingCall(
                                symbol=symbol,
                                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                direction="BUY",
                                setup_type="FVG_FILL",
                                entry_price=round(cmp, 2),
                                stop_loss=sl,
                                target_1=tp1,
                                target_2=tp2,
                                risk_reward=rr,
                                notes=f"Bullish FVG ({fvg.bottom:.1f}-{fvg.top:.1f}) | Risk: {risk:.2f}"
                            )

    # -------------------------------------------------------------
    # 2. BEARISH SCENARIOS (Trend Bearish + Price in/near Premium)
    # -------------------------------------------------------------
    elif swing_trend == BEARISH and (pd.isna(eq_level) or cmp >= eq_level * 0.98):
        # A. Bearish Order Block Test
        for ob in reversed(active_obs):
            if ob.bias == BEARISH and ob.bar_index >= recent_bar_cutoff:
                if ob.bar_low * 0.985 <= cmp <= ob.bar_high:
                    sl = round(ob.bar_high + (0.15 * atr), 2)
                    risk = sl - cmp
                    max_allowed_risk = cmp * 0.06

                    if 0 < risk <= max_allowed_risk:
                        tp1 = round(smc_res.discount_zone[0] if not pd.isna(smc_res.discount_zone[0]) else cmp - (2.5 * risk), 2)
                        tp1 = min(tp1, round(cmp - (2.0 * risk), 2))
                        tp2 = round(tp1 - (1.5 * risk), 2)
                        rr = round((cmp - tp1) / risk, 2)

                        if rr >= 1.8:
                            return TradingCall(
                                symbol=symbol,
                                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                direction="SELL",
                                setup_type="OB_SUPPLY_TAP",
                                entry_price=round(cmp, 2),
                                stop_loss=sl,
                                target_1=tp1,
                                target_2=tp2,
                                risk_reward=rr,
                                notes=f"Bearish OB ({ob.bar_low:.1f}-{ob.bar_high:.1f}) | Risk: {risk:.2f}"
                            )

    return None
