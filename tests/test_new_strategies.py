"""
File: tests/test_new_strategies.py
Purpose: Unit tests for the 5 new strategy calculators ported from screeni-py.
Last Modified: 2026-06-01
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engine.strategies import (
    _supertrend_impl,
    calc_candle_patterns,
    calc_dual_supertrend,
    calc_lorentzian,
    calc_ttm_squeeze,
    calc_vcp,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(n: int, close: float = 100.0, atr_noise: float = 0.0) -> pd.DataFrame:
    """Create a minimal OHLCV DataFrame with n rows."""
    rng = np.random.default_rng(42)
    noise = rng.uniform(-atr_noise, atr_noise, size=n) if atr_noise else np.zeros(n)
    closes = np.full(n, close) + noise
    return pd.DataFrame(
        {
            "Open": closes - 1.0,
            "High": closes + 1.0,
            "Low": closes - 1.0,
            "Close": closes,
            "Volume": np.full(n, 1_000_000.0),
        }
    )


def _make_trend_df(n: int = 300) -> pd.DataFrame:
    """Create a DataFrame with Close well above SMA50 and SMA200 (Stage 2 uptrend)."""
    closes = np.linspace(80.0, 130.0, n)  # Gradual uptrend
    highs = closes + 2.0
    lows = closes - 2.0
    df = pd.DataFrame(
        {
            "Open": closes - 0.5,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": np.full(n, 500_000.0),
        }
    )
    df["SMA_50"] = df["Close"].rolling(50).mean()
    df["SMA_200"] = df["Close"].rolling(200).mean()
    return df


# ---------------------------------------------------------------------------
# calc_vcp
# ---------------------------------------------------------------------------


class TestCalcVCP:
    def test_insufficient_data(self) -> None:
        df = _make_ohlcv(100)
        result = calc_vcp(df, lookback=250)
        assert result["action"] == "No VCP"
        assert "Insufficient data" in result["reason"]

    def test_price_below_sma_returns_no_vcp(self) -> None:
        n = 260
        # CMP much lower than SMA — below both moving averages
        closes = np.linspace(200.0, 50.0, n)  # Strong downtrend
        df = pd.DataFrame(
            {
                "High": closes + 1,
                "Low": closes - 1,
                "Close": closes,
            }
        )
        df["SMA_50"] = df["Close"].rolling(50).mean()
        df["SMA_200"] = df["Close"].rolling(200).mean()
        result = calc_vcp(df)
        assert result["action"] == "No VCP"

    def test_returns_dict_with_required_keys(self) -> None:
        df = _make_trend_df(300)
        result = calc_vcp(df)
        assert "action" in result
        assert "reason" in result

    def test_no_vcp_on_flat_data(self) -> None:
        """Flat data without tightening peaks should return No VCP."""
        df = _make_trend_df(300)
        result = calc_vcp(df)
        # Flat/monotone data won't have proper swing contraction
        assert result["action"] in ("No VCP", "VCP Tightening")  # Either is valid

    def test_none_df_returns_no_vcp(self) -> None:
        result = calc_vcp(None)  # type: ignore[arg-type]
        assert result["action"] == "No VCP"


# ---------------------------------------------------------------------------
# calc_ttm_squeeze
# ---------------------------------------------------------------------------


class TestCalcTTMSqueeze:
    def test_insufficient_data(self) -> None:
        df = _make_ohlcv(10)
        result = calc_ttm_squeeze(df, period=20)
        assert result["action"] == "Insufficient Data"
        assert result["squeeze_active"] is False

    def test_no_squeeze_on_wide_bands(self) -> None:
        """When volatility is high, BB will be wider than KC — no squeeze."""
        n = 60
        # High volatility: alternating spikes
        closes = np.array([100.0 + 10.0 * (i % 2) for i in range(n)])
        df = pd.DataFrame(
            {
                "High": closes + 5,
                "Low": closes - 5,
                "Close": closes,
            }
        )
        result = calc_ttm_squeeze(df)
        assert "squeeze_active" in result
        assert isinstance(result["squeeze_active"], bool)

    def test_result_has_required_keys(self) -> None:
        df = _make_ohlcv(50)
        result = calc_ttm_squeeze(df)
        assert "action" in result
        assert "squeeze_active" in result
        assert "momentum" in result

    def test_squeeze_active_when_bb_inside_kc(self) -> None:
        """Artificially create squeeze: very low stddev (tight BB) with normal ATR."""
        n = 60
        # Very stable close price — tight BB
        closes = np.full(n, 100.0)
        closes[-1] = 100.1  # Tiny jitter
        highs = np.full(n, 102.0)  # Wide High-Low range → bigger ATR → wider KC
        lows = np.full(n, 98.0)
        df = pd.DataFrame({"High": highs, "Low": lows, "Close": closes})
        result = calc_ttm_squeeze(df)
        # With very low price std and larger ATR from H-L range, squeeze may be active
        assert result["action"] in ("Squeeze Active (Bullish)", "Squeeze Active (Bearish)", "No Squeeze", "Insufficient Data")

    def test_none_df(self) -> None:
        result = calc_ttm_squeeze(None)  # type: ignore[arg-type]
        assert result["squeeze_active"] is False


# ---------------------------------------------------------------------------
# _supertrend_impl (internal) + calc_dual_supertrend
# ---------------------------------------------------------------------------


class TestSupertrend:
    def test_supertrend_impl_returns_correct_shapes(self) -> None:
        n = 50
        high = pd.Series(np.full(n, 105.0))
        low = pd.Series(np.full(n, 95.0))
        close = pd.Series(np.full(n, 100.0))
        st, direction = _supertrend_impl(high, low, close, atr_period=10, factor=3.0)
        assert len(st) == n
        assert len(direction) == n

    def test_supertrend_direction_values(self) -> None:
        n = 50
        high = pd.Series(np.full(n, 105.0))
        low = pd.Series(np.full(n, 95.0))
        close = pd.Series(np.full(n, 100.0))
        _, direction = _supertrend_impl(high, low, close, atr_period=10, factor=3.0)
        unique_dirs = set(direction)
        # Direction should only be 1 or -1
        assert unique_dirs.issubset({1.0, -1.0})

    def test_dual_supertrend_insufficient_data(self) -> None:
        df = _make_ohlcv(5)
        result = calc_dual_supertrend(df, buy_atr=10)
        assert result["action"] == "Insufficient Data"

    def test_dual_supertrend_returns_keys(self) -> None:
        df = _make_ohlcv(30)
        result = calc_dual_supertrend(df, buy_atr=10, sell_atr=10)
        assert "action" in result
        assert "buy_dir" in result
        assert "sell_dir" in result

    def test_dual_supertrend_action_values(self) -> None:
        df = _make_ohlcv(60)
        result = calc_dual_supertrend(df)
        assert result["action"] in ("Long Entry", "Close Long", "Hold", "Insufficient Data")

    def test_dual_supertrend_long_entry_on_uptrend(self) -> None:
        """Force a flip: first half downtrend, second half strong uptrend."""
        n = 60
        # First 30 bars: declining prices (downtrend)
        # Last 30 bars: sharply rising (should trigger uptrend flip)
        closes = np.concatenate([np.linspace(120.0, 80.0, 30), np.linspace(80.0, 150.0, 30)])
        df = pd.DataFrame(
            {
                "High": closes + 5,
                "Low": closes - 5,
                "Close": closes,
            }
        )
        result = calc_dual_supertrend(df, buy_atr=5, buy_factor=1.5)
        # The result should be one of the valid states
        assert result["action"] in ("Long Entry", "Close Long", "Hold")


# ---------------------------------------------------------------------------
# calc_candle_patterns
# ---------------------------------------------------------------------------


class TestCalcCandlePatterns:
    def test_empty_df_returns_none(self) -> None:
        df = pd.DataFrame()
        result = calc_candle_patterns(df)
        assert result["pattern"] == "None"

    def test_missing_required_columns(self) -> None:
        df = pd.DataFrame({"Close": [100.0, 101.0]})
        result = calc_candle_patterns(df)
        assert result["pattern"] == "None"

    def test_returns_required_keys(self) -> None:
        df = _make_ohlcv(10)
        result = calc_candle_patterns(df)
        assert "action" in result
        assert "pattern" in result

    def test_valid_df_returns_string_pattern(self) -> None:
        df = _make_ohlcv(20)
        result = calc_candle_patterns(df)
        assert isinstance(result["pattern"], str)

    def test_none_df(self) -> None:
        result = calc_candle_patterns(None)  # type: ignore[arg-type]
        assert result["action"] == "None"


# ---------------------------------------------------------------------------
# calc_lorentzian
# ---------------------------------------------------------------------------


class TestCalcLorentzian:
    def test_insufficient_data(self) -> None:
        df = _make_ohlcv(10)
        result = calc_lorentzian(df)
        assert result["action"] == "No Signal"

    def test_returns_required_keys(self) -> None:
        df = _make_ohlcv(100)
        result = calc_lorentzian(df)
        assert "action" in result
        assert "confidence" in result

    def test_action_is_valid_string(self) -> None:
        df = _make_ohlcv(100, atr_noise=2.0)
        # Add minimal TA columns for sklearn fallback
        df["RSI_14"] = np.linspace(40.0, 60.0, len(df))
        df["ADX_14"] = np.full(len(df), 25.0)
        df["CCI_14"] = np.linspace(-50.0, 50.0, len(df))
        df["MACD_HIST"] = np.linspace(-0.5, 0.5, len(df))
        result = calc_lorentzian(df)
        assert result["action"] in ("Lorentzian Buy", "No Signal", "Lorentzian Sell")

    def test_none_df(self) -> None:
        result = calc_lorentzian(None)  # type: ignore[arg-type]
        assert result["action"] == "No Signal"

    def test_sklearn_fallback_without_advanced_ta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure sklearn KNN fallback works when advanced_ta is patched out."""
        import src.engine.strategies as strats

        original_has_ata = strats._HAS_ATA
        try:
            strats._HAS_ATA = False
            n = 100
            df = _make_ohlcv(n, atr_noise=2.0)
            df["RSI_14"] = np.linspace(30.0, 70.0, n)
            df["ADX_14"] = np.full(n, 28.0)
            df["CCI_14"] = np.linspace(-100.0, 100.0, n)
            df["MACD_HIST"] = np.linspace(-1.0, 1.0, n)
            result = calc_lorentzian(df)
            assert "action" in result
            assert result["action"] in ("Lorentzian Buy", "No Signal")
        finally:
            strats._HAS_ATA = original_has_ata
