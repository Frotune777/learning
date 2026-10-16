"""
File: tests/test_scanner.py
Purpose: Unit and regression tests for UltraOptimizedMultiTimeframeScanner risk management and signal emission.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest
import talib

from src.engine.scanner import UltraOptimizedMultiTimeframeScanner


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate synthetic 30-bar daily OHLCV series."""
    np.random.seed(42)
    n = 30
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    base = 100.0 + np.cumsum(np.random.randn(n) * 1.5)
    highs = base + np.random.uniform(1.0, 3.0, n)
    lows = base - np.random.uniform(1.0, 3.0, n)
    closes = base + np.random.uniform(-1.0, 1.0, n)
    opens = base + np.random.uniform(-1.0, 1.0, n)
    volume = np.random.randint(10000, 50000, n)

    df = pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volume,
        },
        index=dates,
    )
    return df


def test_atr_matches_talib_atr(sample_ohlcv: pd.DataFrame) -> None:
    """Verify scanner's Wilder ATR matches talib.ATR on synthetic OHLCV."""
    scanner = UltraOptimizedMultiTimeframeScanner()
    res = scanner._calculate_risk_management(sample_ohlcv, {}, signal="BUY")

    expected_atr = talib.ATR(
        sample_ohlcv["High"].values.astype(float),
        sample_ohlcv["Low"].values.astype(float),
        sample_ohlcv["Close"].values.astype(float),
        timeperiod=14,
    )[-1]

    cmp = float(sample_ohlcv["Close"].iloc[-1])
    computed_atr = (cmp - res["stop_loss"]) / 2.0
    assert math.isclose(computed_atr, expected_atr, rel_tol=1e-5)


def test_short_signal_gets_sl_above_tp_below(sample_ohlcv: pd.DataFrame) -> None:
    """SELL signal must produce stop loss above current price and take profit below current price."""
    scanner = UltraOptimizedMultiTimeframeScanner()
    res = scanner._calculate_risk_management(sample_ohlcv, {}, signal="SELL")

    cmp = res["current_price"]
    assert res["stop_loss"] > cmp, f"SL {res['stop_loss']} must be > CMP {cmp} for SHORT"
    assert res["take_profit"] < cmp, f"TP {res['take_profit']} must be < CMP {cmp} for SHORT"
    assert res["risk_reward_ratio"] > 0


def test_long_signal_gets_sl_below_tp_above(sample_ohlcv: pd.DataFrame) -> None:
    """BUY signal must produce stop loss below current price and take profit above current price."""
    scanner = UltraOptimizedMultiTimeframeScanner()
    res = scanner._calculate_risk_management(sample_ohlcv, {}, signal="BUY")

    cmp = res["current_price"]
    assert res["stop_loss"] < cmp, f"SL {res['stop_loss']} must be < CMP {cmp} for LONG"
    assert res["take_profit"] > cmp, f"TP {res['take_profit']} must be > CMP {cmp} for LONG"
    assert res["risk_reward_ratio"] > 0


def test_neutral_signal_does_not_emit_sl_tp(sample_ohlcv: pd.DataFrame) -> None:
    """NEUTRAL signal must yield NaN for stop loss and take profit."""
    scanner = UltraOptimizedMultiTimeframeScanner()
    res = scanner._calculate_risk_management(sample_ohlcv, {}, signal="NEUTRAL")

    assert math.isnan(res["stop_loss"])
    assert math.isnan(res["take_profit"])
    assert math.isnan(res["risk_percent"])
    assert math.isnan(res["reward_percent"])
    assert math.isnan(res["risk_reward_ratio"])


def test_emit_to_bus_neutral_is_not_short() -> None:
    """NEUTRAL result must emit signal_direction as None instead of misclassifying as SHORT."""
    scanner = UltraOptimizedMultiTimeframeScanner()
    emitted_data = []
    scanner.emit_signal = lambda data: emitted_data.append(data)

    mock_result = {
        "symbol": "TCS",
        "signal": "NEUTRAL",
        "score": 5,
        "confidence": 50,
        "risk_management": {},
    }

    scanner._emit_to_bus(mock_result, ["1d"])
    assert len(emitted_data) == 1
    assert emitted_data[0]["signal_direction"] is None
    assert emitted_data[0]["signal_direction"] != "SHORT"
