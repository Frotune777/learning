"""
File: tests/test_capsule_engine.py
Purpose: Verification tests for Capsule Academy 5-Star, Train 920/130, and SMC setups.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engine.capsule_engine import (
    CapsuleAnalysisResult,
    add_capsule_indicators,
    analyze_capsule_strategy,
)


def _make_dummy_ohlcv(n_bars: int = 350) -> pd.DataFrame:
    """Generate deterministic trending OHLCV dataframe with uppercase column names."""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=n_bars, freq="D")
    base = 100.0 + np.linspace(0, 150, n_bars) + np.random.randn(n_bars) * 1.5
    df = pd.DataFrame(
        {
            "Open": base - 0.5,
            "High": base + 2.0,
            "Low": base - 2.0,
            "Close": base + 0.5,
            "Volume": np.random.randint(100_000, 1_000_000, size=n_bars),
        },
        index=dates,
    )
    return df


def test_capsule_engine_indicators() -> None:
    """Validate technical indicators computation (EMA 7/9/20/200, CCI, MACD, RSI, Turnover)."""
    df = _make_dummy_ohlcv(250)
    enriched = add_capsule_indicators(df)

    assert "EMA7" in enriched.columns
    assert "EMA9" in enriched.columns
    assert "EMA20" in enriched.columns
    assert "EMA200" in enriched.columns
    assert "CCI_30_5" in enriched.columns
    assert "MACD_Hist" in enriched.columns
    assert "RSI14" in enriched.columns
    assert "Turnover_Surge_Pct" in enriched.columns
    assert not enriched["EMA9"].isna().all()


def test_capsule_strategy_analysis() -> None:
    """Validate full multi-timeframe 5-Star analysis and result object."""
    df = _make_dummy_ohlcv(350)
    result = analyze_capsule_strategy("RELIANCE", df)

    assert result is not None
    assert isinstance(result, CapsuleAnalysisResult)
    assert result.symbol == "RELIANCE"
    assert result.close > 0
    assert 0 <= result.total_stars <= 5
    assert isinstance(result.train_920130_boarding, bool)
    assert isinstance(result.smc_spring, bool)
    assert isinstance(result.smc_ifc_candle, bool)
    assert result.recommended_action in ("STRONG BUY", "BUY", "BUY / BOARD", "WATCH")


def test_capsule_screener_output_and_table_rendering(tmp_path: pytest.TempPathFactory) -> None:
    """End-to-end regression test: ensure screener returns non-empty columns and table renders cleanly."""
    from src.cli.menus import _render_capsule_table
    from src.scanners.capsule_screener import run_capsule_screener

    # Create dummy parquet files in tmp_path
    df = _make_dummy_ohlcv(350)
    for sym in ["SYM_A", "SYM_B", "SYM_C"]:
        df.to_parquet(tmp_path / f"{sym}.parquet")

    results_df = run_capsule_screener(str(tmp_path), min_stars=0)
    assert not results_df.empty
    assert "Symbol" in results_df.columns
    assert "Close" in results_df.columns
    assert "Stars" in results_df.columns
    assert "SYMBOL" in results_df.columns
    assert "CMP" in results_df.columns

    # Verify that symbols and close values are not null/empty
    first_row = results_df.iloc[0]
    assert first_row["Symbol"] in ["SYM_A", "SYM_B", "SYM_C"]
    assert first_row["Close"] > 0
    assert first_row["CMP"] > 0

    # Ensure table rendering runs without raising any exception across all modes
    _render_capsule_table(results_df, title="TEST 5STAR", mode="5star")
    _render_capsule_table(results_df, title="TEST TRAIN", mode="train")
    _render_capsule_table(results_df, title="TEST TURNOVER", mode="turnover")
    _render_capsule_table(results_df, title="TEST SMC", mode="smc")


def _make_dummy_hourly_ohlcv(n_bars: int = 100) -> pd.DataFrame:
    """Generate deterministic hourly OHLCV dataframe."""
    np.random.seed(42)
    dates = pd.date_range("2026-01-01 09:15", periods=n_bars, freq="h")
    base = 100.0 + np.linspace(0, 50, n_bars)
    volumes = np.full(n_bars, 100_000)
    volumes[-1] = 250_000  # 150% volume surge on final bar

    return pd.DataFrame(
        {
            "Open": base - 0.2,
            "High": base + 1.0,
            "Low": base - 1.0,
            "Close": base + 0.3,
            "Volume": volumes,
        },
        index=dates,
    )


def test_resample_to_3h() -> None:
    """Verify 1H OHLCV resamples cleanly to 3H bars."""
    from src.engine.capsule_engine import resample_to_3h

    df_1h = _make_dummy_hourly_ohlcv(30)
    df_3h = resample_to_3h(df_1h)

    assert not df_3h.empty
    assert len(df_3h) < len(df_1h)
    assert set(["Open", "High", "Low", "Close", "Volume"]).issubset(df_3h.columns)
    # Check that empty or None returns empty DataFrame
    assert resample_to_3h(None).empty
    assert resample_to_3h(pd.DataFrame()).empty


def test_capsule_strategy_with_1h_intraday() -> None:
    """Verify Capsule analysis activates true 1H Intraday mode when 1H data is provided."""
    df_daily = _make_dummy_ohlcv(350)
    df_hourly = _make_dummy_hourly_ohlcv(120)

    result = analyze_capsule_strategy("INFY", df_daily, df_hourly=df_hourly)

    assert result is not None
    assert result.tf_mode == "1H"
    assert result.hourly_ema9_gt_ema20 is True
    assert result.hourly_turnover_surge is True
    assert result.star_turnover_surge is True
    assert isinstance(result.seeds_3h_overlap, bool)


def test_capsule_strategy_1d_fallback() -> None:
    """Verify Capsule analysis falls back explicitly to 1D_FALLBACK when 1H data is absent."""
    df_daily = _make_dummy_ohlcv(350)

    result = analyze_capsule_strategy("INFY", df_daily, df_hourly=None)

    assert result is not None
    assert result.tf_mode == "1D_FALLBACK"
    assert result.hourly_ema9_gt_ema20 is False
    assert result.hourly_crossover is False


