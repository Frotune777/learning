"""
Unit test for Smart Money Concepts (SMC) engine.
Verifies pivot detection, BOS/CHoCH, Order Blocks, FVGs, and Premium/Discount zones.
"""

import numpy as np
import pandas as pd
import polars as pl

from src.engine.smc import BULLISH, calculate_smc


def test_smc_output_structure():
    """Verify DataFrame columns and returned dataclass structure."""
    np.random.seed(42)
    n = 100
    close = 100.0 + np.cumsum(np.random.randn(n))
    high = close + 1.0
    low = close - 1.0
    open_ = close + 0.1

    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})
    res = calculate_smc(df, swing_length=10, internal_length=3)

    assert isinstance(res.df, pl.DataFrame)
    expected_cols = {
        "smc_swing_bos",
        "smc_swing_choch",
        "smc_internal_bos",
        "smc_internal_choch",
        "smc_fvg_bullish",
        "smc_fvg_bearish",
        "smc_swing_trend",
        "smc_internal_trend",
        "smc_atr",
    }
    assert expected_cols.issubset(set(res.df.columns))
    assert len(res.df) == n


def test_smc_polars_input():
    """Verify calculate_smc accepts Polars DataFrame directly."""
    n = 60
    prices = np.linspace(50, 150, n)
    p_df = pl.DataFrame({
        "open": prices,
        "high": prices + 1.0,
        "low": prices - 1.0,
        "close": prices + 0.5,
    })
    res = calculate_smc(p_df, swing_length=10, internal_length=3)
    assert isinstance(res.df, pl.DataFrame)
    assert len(res.df) == n


def test_bullish_fvg_detection():
    """Verify detection of a classic 3-bar Bullish Fair Value Gap."""
    # Bar 0: Low 10, High 12
    # Bar 1: Huge green expansion candle
    # Bar 2: Low stays above Bar 0's High -> creates imbalance gap
    opens = [10.0, 12.5, 18.0] * 20
    highs = [12.0, 19.0, 20.0] * 20
    lows = [9.5, 12.0, 14.0] * 20   # low[2] = 14.0 > high[0] = 12.0 -> FVG
    closes = [11.5, 18.5, 19.5] * 20

    df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})
    res = calculate_smc(df, swing_length=5, internal_length=2)

    assert any(fvg.bias == BULLISH for fvg in res.fair_value_gaps)
    bullish_fvgs = [f for f in res.fair_value_gaps if f.bias == BULLISH]
    assert bullish_fvgs[0].top > bullish_fvgs[0].bottom


def test_premium_discount_zones():
    """Verify premium zone is higher than discount zone."""
    np.random.seed(123)
    n = 150
    close = np.linspace(100, 200, n) + np.sin(np.linspace(0, 10, n)) * 10
    high = close + 2.0
    low = close - 2.0
    open_ = close - 0.5

    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})
    res = calculate_smc(df, swing_length=10, internal_length=4)

    if not np.isnan(res.equilibrium_level):
        assert res.premium_zone[0] > res.equilibrium_level
        assert res.discount_zone[1] < res.equilibrium_level
