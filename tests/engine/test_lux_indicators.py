"""
Unit tests for the portfolio of high-performance LuxAlgo indicators:
1. Nadaraya-Watson Envelope (Kernel Regression)
2. ICT Model 2022 Setup Engine
3. Structure Volume Profile (POC / VAH / VAL)
4. Liquidity Sweeps & Inverted FVGs (iFVGs)
5. Stan Weinstein 4-Stage Analysis Engine
6. Volume Spread Analysis (No-Demand / No-Supply)
7. Savitzky-Golay Digital Filter
8. Valid BOS Pullback Retest Engine
"""

import numpy as np
import pandas as pd
import polars as pl
import pytest

from src.engine.lux_bos_pullback import calculate_valid_bos_pullback
from src.engine.lux_ifvg_sweeps import calculate_sweeps_ifvgs
from src.engine.lux_model_2022 import calculate_model_2022
from src.engine.lux_nwe import calculate_nwe
from src.engine.lux_savgol import calculate_savgol
from src.engine.lux_volume_profile import calculate_volume_profile
from src.engine.lux_vsa import calculate_vsa_bars
from src.engine.lux_weinstein import calculate_weinstein_stage


@pytest.fixture
def sample_ohlcv():
    np.random.seed(42)
    n = 200
    close = 100.0 + np.cumsum(np.random.randn(n) * 1.2)
    return pd.DataFrame({
        "open": close + np.random.uniform(-0.4, 0.4, n),
        "high": close + np.random.uniform(0.5, 2.0, n),
        "low": close - np.random.uniform(0.5, 2.0, n),
        "close": close,
        "volume": np.random.uniform(10_000, 500_000, n),
    })


def test_nwe_calculation(sample_ohlcv):
    res = calculate_nwe(sample_ohlcv, bandwidth=8.0, multiplier=2.5)
    assert isinstance(res.df, pl.DataFrame)
    assert "nwe" in res.df.columns
    assert "nwe_upper" in res.df.columns
    assert "nwe_lower" in res.df.columns
    assert not np.isnan(res.latest_nwe)
    assert res.latest_upper > res.latest_nwe > res.latest_lower


def test_model_2022_structure(sample_ohlcv):
    res = calculate_model_2022(sample_ohlcv, symbol="RELIANCE", swing_length=5)
    assert isinstance(res.df, pl.DataFrame)
    assert "model_2022_signal" in res.df.columns
    assert len(res.liquidity_pools) > 0


def test_volume_profile_poc_vah_val(sample_ohlcv):
    res = calculate_volume_profile(sample_ohlcv, lookback=80, rows=25, va_percent=70.0)
    assert res.total_volume > 0
    assert res.vah_price >= res.poc_price >= res.val_price
    assert len(res.bins) == 25
    assert sum(b.is_poc for b in res.bins) == 1


def test_sweeps_and_ifvgs(sample_ohlcv):
    res = calculate_sweeps_ifvgs(sample_ohlcv, swing_len=4, vol_filter_mult=0.1)
    assert isinstance(res.df, pl.DataFrame)
    assert "sweep_high" in res.df.columns
    assert "sweep_low" in res.df.columns
    assert "ifvg_bullish" in res.df.columns
    assert "ifvg_bearish" in res.df.columns
    # Verify outputs are properly shaped boolean series
    assert res.df["sweep_high"].dtype == pl.Boolean
    assert res.df["ifvg_bullish"].dtype == pl.Boolean


def test_weinstein_stage_analysis(sample_ohlcv):
    # With 200 bars and ma_weeks=10 (50 bars), we have ample data
    res = calculate_weinstein_stage(sample_ohlcv, ma_weeks=10, slope_weeks=2, is_daily=True)
    assert isinstance(res.df, pl.DataFrame)
    assert "weinstein_stage" in res.df.columns
    assert "weinstein_stage_name" in res.df.columns
    assert "stage2_breakout" in res.df.columns
    assert res.current_stage in (0, 1, 2, 3, 4)
    assert res.volume_ratio >= 0.0


def test_vsa_bars(sample_ohlcv):
    res = calculate_vsa_bars(sample_ohlcv, spread_len=15, context_len=30)
    assert isinstance(res.df, pl.DataFrame)
    assert "vsa_no_demand" in res.df.columns
    assert "vsa_no_supply" in res.df.columns
    assert "vsa_spread_ratio" in res.df.columns
    assert res.relative_spread > 0.0
    assert res.relative_volume > 0.0


def test_savgol_filter(sample_ohlcv):
    res = calculate_savgol(sample_ohlcv, half_width=10, poly_order=2)
    assert isinstance(res.df, pl.DataFrame)
    assert "sg_filter" in res.df.columns
    assert "sg_slope" in res.df.columns
    assert "sg_signal" in res.df.columns
    assert not np.isnan(res.latest_sg)
    assert res.latest_turn_signal in (-1, 0, 1)


def test_valid_bos_pullback(sample_ohlcv):
    res = calculate_valid_bos_pullback(sample_ohlcv, left_bars=2, right_bars=2, swing_lookback=30)
    assert isinstance(res.df, pl.DataFrame)
    assert "valid_bos_bull" in res.df.columns
    assert "valid_bos_bear" in res.df.columns
    assert "valid_pullback_touch" in res.df.columns
