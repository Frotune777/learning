"""
File: tests/test_ta_indicators.py
Purpose: Unit tests for technical indicators calculation and scoring.
Last Modified: 2026-05-27
"""

import numpy as np
import pandas as pd

from src.nse_bhavcopy.ta_indicators import (
    _calculate_vectorized_divergences,
    add_ta_indicators,
    calculate_technical_score,
)


def test_add_ta_indicators_empty() -> None:
    """
    Test add_ta_indicators with an empty DataFrame.

    Parameters:
        None

    Returns:
        None

    Complexity:
        Time: O(1)
        Space: O(1)
    """
    df = pd.DataFrame()
    res = add_ta_indicators(df)
    assert res.empty


def test_add_ta_indicators_success() -> None:
    """
    Test add_ta_indicators with a valid mock historical DataFrame.

    Parameters:
        None

    Returns:
        None

    Complexity:
        Time: O(N)
        Space: O(N)
    """
    # Create 250 days of mock prices to satisfy all moving averages up to 200 days
    dates = pd.date_range(start="2023-01-01", periods=250)
    data = {
        "Open": np.linspace(100.0, 200.0, 250),
        "High": np.linspace(105.0, 205.0, 250),
        "Low": np.linspace(95.0, 195.0, 250),
        "Close": np.linspace(100.0, 200.0, 250),
        "Volume": [10000.0] * 250,
    }
    df = pd.DataFrame(data, index=dates)

    res = add_ta_indicators(df)

    # Check columns
    expected_cols = [
        "RSI_14",
        "MACD",
        "MACD_SIGNAL",
        "MACD_HIST",
        "BB_UPPER",
        "BB_MIDDLE",
        "BB_LOWER",
        "EMA_20",
        "EMA_50",
        "EMA_100",
        "EMA_200",
        "SMA_50",
        "SMA_100",
        "SMA_200",
        "ATR_14",
        "ADX_14",
        "CCI_14",
    ]
    for col in expected_cols:
        assert col in res.columns

    # Verify that the last elements are not NaN
    assert not pd.isna(res["EMA_20"].iloc[-1])
    assert not pd.isna(res["SMA_50"].iloc[-1])
    assert not pd.isna(res["SMA_200"].iloc[-1])
    assert not pd.isna(res["RSI_14"].iloc[-1])


def test_calculate_technical_score_strong_buy() -> None:
    """
    Test calculate_technical_score under highly bullish conditions.

    Parameters:
        None

    Returns:
        None

    Complexity:
        Time: O(1)
        Space: O(1)
    """
    row = pd.Series(
        {
            "Close": 150.0,
            "EMA_20": 140.0,
            "SMA_50": 130.0,
            "SMA_200": 100.0,
            "RSI_14": 60.0,
            "MACD": 5.0,
            "MACD_SIGNAL": 2.0,
            "BB_UPPER": 160.0,
            "BB_MIDDLE": 145.0,
            "BB_LOWER": 130.0,
            "ADX_14": 30.0,
        }
    )
    result = calculate_technical_score(row)
    assert result["score"] >= 80
    assert result["rating"] == "STRONG BUY"


def test_calculate_technical_score_neutral() -> None:
    """
    Test calculate_technical_score under mixed/neutral conditions.

    Parameters:
        None

    Returns:
        None

    Complexity:
        Time: O(1)
        Space: O(1)
    """
    row = pd.Series(
        {
            "Close": 100.0,
            "EMA_20": 105.0,
            "SMA_50": 100.0,
            "SMA_200": 98.0,
            "RSI_14": 45.0,
            "MACD": -1.0,
            "MACD_SIGNAL": -0.5,
            "BB_UPPER": 110.0,
            "BB_MIDDLE": 100.0,
            "BB_LOWER": 90.0,
            "ADX_14": 15.0,
        }
    )
    result = calculate_technical_score(row)
    assert 40 <= result["score"] < 60
    assert result["rating"] == "NEUTRAL"


def test_score_returns_insufficient_data_on_all_nan() -> None:
    """When key indicators are all NaN, calculate_technical_score must return INSUFFICIENT DATA."""
    row = pd.Series(
        {
            "Close": 100.0,
            "EMA_20": np.nan,
            "SMA_50": np.nan,
            "SMA_200": np.nan,
            "RSI_14": np.nan,
            "ADX_14": np.nan,
        }
    )
    result = calculate_technical_score(row)
    assert result["score"] == 0
    assert result["rating"] == "INSUFFICIENT DATA"


def test_score_proceeds_when_at_least_half_indicators_present() -> None:
    """
    When at least half of the key indicators are present (non-NaN),
    calculate_technical_score proceeds.
    """
    # 3 present out of 5 key indicators (RSI_14, EMA_20, SMA_50)
    row = pd.Series(
        {
            "Close": 150.0,
            "EMA_20": 140.0,
            "SMA_50": 130.0,
            "SMA_200": np.nan,
            "RSI_14": 60.0,
            "ADX_14": np.nan,
        }
    )
    result = calculate_technical_score(row)
    assert result["rating"] != "INSUFFICIENT DATA"
    assert result["score"] > 0


# ---------------------------------------------------------------------------
# Divergence Acceptance Tests (9 tests)
# ---------------------------------------------------------------------------


def test_divergence_empty_dataframe() -> None:
    """1. Empty DataFrame returns empty DataFrame."""
    df = pd.DataFrame()
    res = _calculate_vectorized_divergences(df)
    assert res.empty


def test_divergence_short_series() -> None:
    """2. Short series (len < lookback) has columns initialized to 'None'."""
    dates = pd.date_range("2026-01-01", periods=10)
    df = pd.DataFrame({"Close": [100.0] * 10}, index=dates)
    res = _calculate_vectorized_divergences(df, lookback=20)
    assert "RSI_Divergence" in res.columns
    assert "MACD_Divergence" in res.columns
    assert (res["RSI_Divergence"] == "None").all()
    assert (res["MACD_Divergence"] == "None").all()


def test_divergence_no_divergence() -> None:
    """3. Monotonic series without divergence produces 'None' throughout."""
    dates = pd.date_range("2026-01-01", periods=30)
    # Both price and indicators rise together
    df = pd.DataFrame(
        {
            "Close": np.linspace(100.0, 130.0, 30),
            "RSI_14": np.linspace(40.0, 70.0, 30),
            "MACD_HIST": np.linspace(0.1, 3.0, 30),
        },
        index=dates,
    )
    res = _calculate_vectorized_divergences(df, lookback=20)
    assert (res["RSI_Divergence"] == "None").all()
    assert (res["MACD_Divergence"] == "None").all()


def test_divergence_bullish_rsi() -> None:
    """4. Bullish RSI divergence: price makes new low while RSI holds higher low."""
    dates = pd.date_range("2026-01-01", periods=25)
    close = [100.0] * 25
    rsi = [50.0] * 25
    # Historical low at index 5: price=95, rsi=30
    close[5] = 95.0
    rsi[5] = 30.0
    # Current bar at index 24: price=90 (lower low), rsi=35 (higher low)
    close[24] = 90.0
    rsi[24] = 35.0

    df = pd.DataFrame({"Close": close, "RSI_14": rsi}, index=dates)
    res = _calculate_vectorized_divergences(df, lookback=20)
    assert res["RSI_Divergence"].iloc[24] == "Bullish"


def test_divergence_bearish_rsi() -> None:
    """5. Bearish RSI divergence: price makes new high while RSI makes lower high."""
    dates = pd.date_range("2026-01-01", periods=25)
    close = [100.0] * 25
    rsi = [50.0] * 25
    # Historical high at index 5: price=140, rsi=75
    close[5] = 140.0
    rsi[5] = 75.0
    # Current bar at index 24: price=150 (higher high), rsi=65 (lower high)
    close[24] = 150.0
    rsi[24] = 65.0

    df = pd.DataFrame({"Close": close, "RSI_14": rsi}, index=dates)
    res = _calculate_vectorized_divergences(df, lookback=20)
    assert res["RSI_Divergence"].iloc[24] == "Bearish"


def test_divergence_bullish_macd() -> None:
    """6. Bullish MACD divergence: price makes new low while MACD_HIST holds higher low."""
    dates = pd.date_range("2026-01-01", periods=25)
    close = [100.0] * 25
    macd_hist = [0.0] * 25
    # Historical low at index 5: price=95, macd_hist=-2.0
    close[5] = 95.0
    macd_hist[5] = -2.0
    # Current bar at index 24: price=90 (lower low), macd_hist=-0.5 (higher low)
    close[24] = 90.0
    macd_hist[24] = -0.5

    df = pd.DataFrame({"Close": close, "MACD_HIST": macd_hist}, index=dates)
    res = _calculate_vectorized_divergences(df, lookback=20)
    assert res["MACD_Divergence"].iloc[24] == "Bullish"


def test_divergence_bearish_macd() -> None:
    """7. Bearish MACD divergence: price makes new high while MACD_HIST makes lower high."""
    dates = pd.date_range("2026-01-01", periods=25)
    close = [100.0] * 25
    macd_hist = [0.0] * 25
    # Historical high at index 5: price=140, macd_hist=3.0
    close[5] = 140.0
    macd_hist[5] = 3.0
    # Current bar at index 24: price=150 (higher high), macd_hist=1.0 (lower high)
    close[24] = 150.0
    macd_hist[24] = 1.0

    df = pd.DataFrame({"Close": close, "MACD_HIST": macd_hist}, index=dates)
    res = _calculate_vectorized_divergences(df, lookback=20)
    assert res["MACD_Divergence"].iloc[24] == "Bearish"


def test_divergence_collision_resolves_to_none() -> None:
    """8. Collision between simultaneous bullish and bearish conditions resolves to 'None'."""
    dates = pd.date_range("2026-01-01", periods=25)
    # Flat series: price is identically min and max simultaneously
    close = [100.0] * 25
    rsi = [50.0] * 25
    df = pd.DataFrame({"Close": close, "RSI_14": rsi}, index=dates)
    res = _calculate_vectorized_divergences(df, lookback=20)
    assert (res["RSI_Divergence"] == "None").all()


def test_divergence_historical_point_in_time_preservation() -> None:
    """9. Point-in-time preservation: historical divergences are preserved and not overridden."""
    dates = pd.date_range("2026-01-01", periods=30)
    close = [100.0] * 30
    rsi = [50.0] * 30
    # Setup bullish divergence at index 21
    close[2] = 95.0
    rsi[2] = 30.0
    close[21] = 90.0
    rsi[21] = 35.0

    df = pd.DataFrame({"Close": close, "RSI_14": rsi}, index=dates)
    res = _calculate_vectorized_divergences(df, lookback=20)
    assert res["RSI_Divergence"].iloc[21] == "Bullish"
    # Later bar index 29 has returned to normal and is 'None'
    assert res["RSI_Divergence"].iloc[29] == "None"


def test_divergence_no_mutation() -> None:
    """Input DataFrame is not mutated by _calculate_vectorized_divergences."""
    dates = pd.date_range("2026-01-01", periods=25)
    df = pd.DataFrame(
        {
            "Close": np.linspace(100.0, 150.0, 25),
            "RSI_14": np.linspace(40.0, 60.0, 25),
            "MACD_HIST": np.linspace(-1.0, 1.0, 25),
        },
        index=dates,
    )
    original = df.copy(deep=True)
    out = _calculate_vectorized_divergences(df)
    assert df.equals(original)  # input unchanged
    assert "RSI_Divergence" in out.columns
    assert "MACD_Divergence" in out.columns


def test_divergence_no_lookahead() -> None:
    """Prefixes of running frames are byte-identical to full-frame results (no lookahead)."""
    dates = pd.date_range("2026-01-01", periods=60)
    close = np.linspace(100.0, 120.0, 60)
    rsi = np.linspace(40.0, 60.0, 60)
    macd_hist = np.linspace(-1.0, 1.0, 60)
    # Known bullish divergence near the end at index 53
    close[35] = 95.0
    rsi[35] = 30.0
    macd_hist[35] = -2.0
    close[53] = 90.0
    rsi[53] = 35.0
    macd_hist[53] = -0.5

    df = pd.DataFrame(
        {"Close": close, "RSI_14": rsi, "MACD_HIST": macd_hist}, index=dates
    )
    full = _calculate_vectorized_divergences(df)
    for i in (40, 50, 55):
        prefix = _calculate_vectorized_divergences(df.iloc[:i].copy())
        pd.testing.assert_series_equal(
            prefix["RSI_Divergence"],
            full["RSI_Divergence"].iloc[:i],
            check_names=False,
        )
        pd.testing.assert_series_equal(
            prefix["MACD_Divergence"],
            full["MACD_Divergence"].iloc[:i],
            check_names=False,
        )


def test_divergence_columns_absent() -> None:
    """When both RSI_14 and MACD_HIST are missing, divergence columns are all 'None'."""
    dates = pd.date_range("2026-01-01", periods=25)
    df = pd.DataFrame(
        {
            "Close": np.linspace(100.0, 120.0, 25),
            "RSI_14": np.linspace(40.0, 60.0, 25),
            "MACD_HIST": np.linspace(-1.0, 1.0, 25),
        },
        index=dates,
    )
    out = _calculate_vectorized_divergences(df.drop(columns=["RSI_14", "MACD_HIST"]))
    assert (out["RSI_Divergence"] == "None").all()
    assert (out["MACD_Divergence"] == "None").all()


def test_divergence_dtype_and_value_contract() -> None:
    """Divergence columns satisfy dtype object, non-null, and canonical categorical values."""
    dates = pd.date_range("2026-01-01", periods=30)
    close = [100.0] * 30
    rsi = [50.0] * 30
    macd_hist = [0.0] * 30
    close[5] = 95.0
    rsi[5] = 30.0
    macd_hist[5] = -2.0
    close[24] = 90.0
    rsi[24] = 35.0
    macd_hist[24] = -0.5

    df = pd.DataFrame(
        {"Close": close, "RSI_14": rsi, "MACD_HIST": macd_hist}, index=dates
    )
    out = _calculate_vectorized_divergences(df)
    for col in ("RSI_Divergence", "MACD_Divergence"):
        assert out[col].dtype == object
        assert out[col].notna().all()
        assert set(out[col].unique()) <= {"Bullish", "Bearish", "None"}

