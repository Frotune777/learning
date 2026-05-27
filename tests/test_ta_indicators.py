"""
File: tests/test_ta_indicators.py
Purpose: Unit tests for technical indicators calculation and scoring.
Last Modified: 2026-05-27
"""

import numpy as np
import pandas as pd

from src.nse_bhavcopy.ta_indicators import (
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
