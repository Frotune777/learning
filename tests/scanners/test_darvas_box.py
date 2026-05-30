"""
File: tests/test_darvas_box.py
Purpose: Unit tests for darvas_box module using synthetic OHLCV DataFrames.
Last Modified: 2026-05-29
"""

import numpy as np
import pandas as pd
import pytest

from src.core.signal import Signal
from src.scanners.darvas_box import (
    _count_trailing_true,
    detect_darvas_box,
    scan_darvas_breakouts,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_ohlcv(
    n: int = 40,
    base_price: float = 100.0,
    volume: float = 1_000_000.0,
) -> pd.DataFrame:
    """Generate a flat OHLCV DataFrame for consolidation testing."""
    closes = [base_price] * n
    return pd.DataFrame(
        {
            "Open": [base_price * 0.99] * n,
            "High": [base_price * 1.005] * n,
            "Low": [base_price * 0.995] * n,
            "Close": closes,
            "Volume": [volume] * n,
        }
    )


def _make_breakout_ohlcv(
    consolidation: int = 25,
    base: float = 100.0,
    breakout_price: float = 110.0,
    vol_normal: float = 500_000.0,
    vol_spike: float = 1_500_000.0,
) -> pd.DataFrame:
    """Build OHLCV where last row breaks above prior rolling high with volume."""
    df = _make_ohlcv(n=consolidation, base_price=base, volume=vol_normal)
    spike_row = pd.DataFrame(
        [
            {
                "Open": base,
                "High": breakout_price + 1.0,
                "Low": base * 0.99,
                "Close": breakout_price,
                "Volume": vol_spike,
            }
        ]
    )
    return pd.concat([df, spike_row], ignore_index=True)


# ─── _count_trailing_true ─────────────────────────────────────────────────────


def test_count_trailing_true_all_true() -> None:
    """Returns length of series when all values are True."""
    s = pd.Series([True, True, True])
    assert _count_trailing_true(s) == 3


def test_count_trailing_true_partial() -> None:
    """Returns count of trailing True streak."""
    s = pd.Series([True, False, True, True, True])
    assert _count_trailing_true(s) == 3


def test_count_trailing_true_none() -> None:
    """Returns 0 when last value is False."""
    s = pd.Series([True, True, False])
    assert _count_trailing_true(s) == 0


# ─── detect_darvas_box ────────────────────────────────────────────────────────


def test_detect_darvas_box_insufficient_data() -> None:
    """Returns Insufficient Data when DataFrame has too few rows."""
    df = _make_ohlcv(n=5)
    result = detect_darvas_box(df)
    assert result["signal"] == "Insufficient Data"
    assert result["breakout"] is False


def test_detect_darvas_box_missing_columns() -> None:
    """Returns Insufficient Data when required columns are absent."""
    df = pd.DataFrame({"Close": [100.0] * 30})
    result = detect_darvas_box(df)
    assert result["signal"] == "Insufficient Data"


def test_detect_darvas_box_no_pattern_flat() -> None:
    """Returns No Pattern or Consolidating for flat price series."""
    df = _make_ohlcv(n=40, base_price=100.0)
    result = detect_darvas_box(df)
    assert result["breakout"] is False
    assert result["breakdown"] is False


def test_detect_darvas_box_breakout_vol_confirmed() -> None:
    """Detects volume-confirmed breakout when close clearly exceeds the box high."""
    # Build 35 consolidation bars at base=100 so rolling window is stable,
    # then add a single bar that closes 20% above (unambiguous breakout).
    df = _make_breakout_ohlcv(
        consolidation=35,
        base=100.0,
        breakout_price=125.0,  # 25% above consolidation range
        vol_normal=300_000.0,
        vol_spike=3_000_000.0,  # 10x normal — volume clearly confirmed
    )
    result = detect_darvas_box(df)
    assert result["vol_confirmed"] is True
    assert "Breakout" in result["signal"]


def test_detect_darvas_box_returns_floats_or_nan() -> None:
    """box_high and box_low are floats or NaN, never strings."""
    df = _make_ohlcv(n=40)
    result = detect_darvas_box(df)
    assert isinstance(result["box_high"], float) or np.isnan(
        result["box_high"]  # type: ignore[arg-type]
    )
    assert isinstance(result["box_low"], float) or np.isnan(
        result["box_low"]  # type: ignore[arg-type]
    )


def test_detect_darvas_box_box_days_is_int() -> None:
    """box_days is always an integer."""
    df = _make_ohlcv(n=40)
    result = detect_darvas_box(df)
    assert isinstance(result["box_days"], int)


@pytest.mark.parametrize("n", [0, 1, 10, 20])
def test_detect_darvas_box_edge_row_counts(n: int) -> None:
    """detect_darvas_box does not raise on any row count."""
    df = _make_ohlcv(n=n)
    result = detect_darvas_box(df)
    assert "signal" in result


def test_scan_darvas_breakouts_signal_protocol(tmp_path):
    """scan_darvas_breakouts should return a list of Signal objects."""

    # Create mock parquet data
    df_hist = _make_breakout_ohlcv(
        consolidation=35,
        base=100.0,
        breakout_price=125.0,
        vol_normal=300_000.0,
        vol_spike=3_000_000.0,
    )

    daily_dir = tmp_path / "1d"
    daily_dir.mkdir()
    df_hist.to_parquet(daily_dir / "MOCKSTOCK.parquet")

    analyzed_df = pd.DataFrame(
        {"SYMBOL": ["MOCKSTOCK"], "CMP": [125.0], "TECH_SCORE": [9.0]}
    )

    signals = scan_darvas_breakouts(
        analyzed_df=analyzed_df, daily_dir=str(daily_dir), output_dir=str(tmp_path)
    )

    assert isinstance(signals, list)
    assert len(signals) == 1
    sig = signals[0]
    assert isinstance(sig, Signal)
    assert sig.symbol == "MOCKSTOCK"
    assert sig.action == 1  # Breakout
    assert 0.0 <= sig.conviction <= 1.0
    assert sig.meta["cmp"] == 125.0
    assert sig.meta["raw_signal"] == "Breakout (Volume Confirmed)"
