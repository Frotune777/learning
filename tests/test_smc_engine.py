"""
File: tests/test_smc_engine.py
Purpose: Regression tests for SMC Order Block mitigation and FVG call generation.
"""

from __future__ import annotations

import pandas as pd
import polars as pl

from src.engine.smc import (
    BEARISH,
    BULLISH,
    FairValueGap,
    SMCResult,
    calculate_smc,
)
from src.engine.smc_decision import generate_smc_call


def test_bullish_ob_survives_tap_until_floor_break() -> None:
    """A Bullish OB must remain active when price taps into it.
    It should only be mitigated when the floor is broken.
    """
    highs = [90.0, 95.0, 100.0, 95.0, 90.0, 105.0, 98.0, 75.0]
    lows = [85.0, 90.0, 95.0, 80.0, 85.0, 92.0, 82.0, 70.0]
    opens = [86.0, 91.0, 96.0, 85.0, 86.0, 93.0, 95.0, 74.0]
    closes = [89.0, 94.0, 98.0, 82.0, 88.0, 104.0, 94.0, 71.0]

    df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})

    # Bar 6: low is 82 (inside OB [80, 95] without breaking floor 80)
    res_tap = calculate_smc(df.iloc[:7], swing_length=3, internal_length=2)
    bull_obs = [ob for ob in res_tap.active_order_blocks if ob.bias == BULLISH]
    assert len(bull_obs) == 1
    assert bull_obs[0].bar_low == 80.0
    assert bull_obs[0].bar_high == 95.0
    assert not bull_obs[0].mitigated

    # Bar 7: low is 70 < 80 (breaks floor) -> mitigated and pruned from active
    res_break = calculate_smc(df, swing_length=3, internal_length=2)
    active_after_break = [ob for ob in res_break.active_order_blocks if ob.bias == BULLISH]
    assert len(active_after_break) == 0


def test_bearish_ob_survives_tap_until_ceiling_break() -> None:
    """A Bearish OB must remain active when price taps into it.
    It should only be mitigated when the ceiling is broken.
    """
    highs = [105.0, 100.0, 95.0, 120.0, 110.0, 85.0, 115.0, 125.0]
    lows = [100.0, 95.0, 90.0, 105.0, 105.0, 80.0, 95.0, 100.0]
    opens = [102.0, 98.0, 93.0, 108.0, 107.0, 84.0, 98.0, 102.0]
    closes = [101.0, 96.0, 91.0, 112.0, 106.0, 81.0, 102.0, 124.0]

    df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})

    # Bar 6: high is 115 (taps into OB [105, 120] without breaking ceiling 120)
    res_tap = calculate_smc(df.iloc[:7], swing_length=3, internal_length=2)
    bear_obs = [ob for ob in res_tap.active_order_blocks if ob.bias == BEARISH]
    assert len(bear_obs) == 1
    assert bear_obs[0].bar_low == 105.0
    assert bear_obs[0].bar_high == 120.0
    assert not bear_obs[0].mitigated

    # Bar 7: high is 125 > 120 (breaks ceiling) -> mitigated and pruned
    res_break = calculate_smc(df, swing_length=3, internal_length=2)
    active_after_break = [ob for ob in res_break.active_order_blocks if ob.bias == BEARISH]
    assert len(active_after_break) == 0


def test_close_vs_wick_mitigation() -> None:
    """Ensure close_mitigation flag controls whether wick or close breaches the zone."""
    highs = [90.0, 95.0, 100.0, 95.0, 90.0, 105.0, 98.0]
    lows = [85.0, 90.0, 95.0, 80.0, 85.0, 92.0, 78.0]  # Wick low 78 < 80, Close 82 >= 80
    opens = [86.0, 91.0, 96.0, 85.0, 86.0, 93.0, 95.0]
    closes = [89.0, 94.0, 98.0, 82.0, 88.0, 104.0, 82.0]

    df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})

    # Wick mitigation (default): low 78 < 80 breaks floor -> 0 active
    res_wick = calculate_smc(df, swing_length=3, internal_length=2, close_mitigation=False)
    assert len([ob for ob in res_wick.active_order_blocks if ob.bias == BULLISH]) == 0

    # Close mitigation: close 82 >= 80 does not break floor -> 1 active
    res_close = calculate_smc(df, swing_length=3, internal_length=2, close_mitigation=True)
    assert len([ob for ob in res_close.active_order_blocks if ob.bias == BULLISH]) == 1


def test_bearish_fvg_fill_generates_sell_call() -> None:
    """Ensure a bearish FVG fill generates a SELL trading decision."""
    n = 40
    df = pd.DataFrame({
        "open": [100.0] * n,
        "high": [102.0] * n,
        "low": [98.0] * n,
        "close": [100.0] * n,
    })

    fvg = FairValueGap(top=101.5, bottom=99.5, bias=BEARISH, bar_index=35)
    smc_res = SMCResult(
        df=pl.from_pandas(df).with_columns(pl.Series("smc_atr", [2.0] * n)),
        active_fair_value_gaps=[fvg],
        current_swing_trend=BEARISH,
        discount_zone=(90.0, 92.0),
        equilibrium_level=95.0,
    )

    call = generate_smc_call("TEST_BEAR", smc_res, df)
    assert call is not None
    assert call.direction == "SELL"
    assert call.setup_type == "FVG_FILL"
    assert call.entry_price == 100.0
    assert call.stop_loss > call.entry_price  # Stop loss must be above entry for short
    assert call.target_1 < call.entry_price  # Target must be below entry for short
    assert call.risk_reward >= 1.8


def test_bullish_fvg_fill_still_generates_buy_call() -> None:
    """Ensure bullish FVG fill remains functional on the working path."""
    n = 40
    df = pd.DataFrame({
        "open": [100.0] * n,
        "high": [102.0] * n,
        "low": [98.0] * n,
        "close": [100.0] * n,
    })

    fvg = FairValueGap(top=101.5, bottom=99.5, bias=BULLISH, bar_index=35)
    smc_res = SMCResult(
        df=pl.from_pandas(df).with_columns(pl.Series("smc_atr", [2.0] * n)),
        active_fair_value_gaps=[fvg],
        current_swing_trend=BULLISH,
        premium_zone=(108.0, 110.0),
        equilibrium_level=105.0,
    )

    call = generate_smc_call("TEST_BULL", smc_res, df)
    assert call is not None
    assert call.direction == "BUY"
    assert call.setup_type == "FVG_FILL"
    assert call.entry_price == 100.0
    assert call.stop_loss < call.entry_price  # Stop loss below entry for long
    assert call.target_1 > call.entry_price  # Target above entry for long
    assert call.risk_reward >= 1.8
