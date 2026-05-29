"""
File: tests/test_nifty_ki_dukan.py
Purpose: Unit tests for nifty_ki_dukan module using synthetic analyzed CSVs.
Last Modified: 2026-05-29
"""

import os

import pandas as pd
import pytest

from src.nse_bhavcopy.nifty_ki_dukan import run_nifty_ki_dukan


def _make_dummy_analyzed_csv(tmp_path: str, rows: list[dict]) -> str:  # type: ignore[type-arg]
    """Write dummy CSV data for testing."""
    df = pd.DataFrame(rows)
    path = os.path.join(str(tmp_path), "top_250_analyzed_20260529.csv")
    df.to_csv(path, index=False)
    return path


def test_run_nifty_ki_dukan_missing_file(tmp_path: str) -> None:
    """run_nifty_ki_dukan raises FileNotFoundError for missing path."""
    with pytest.raises(FileNotFoundError):
        run_nifty_ki_dukan(str(tmp_path / "missing.csv"))


def test_run_nifty_ki_dukan_filters_correctly(tmp_path: str) -> None:
    """Filters stocks by Trend Status and CAR rating for both variants."""
    rows = [
        # Variant A Bull Run matches
        {
            "SYMBOL": "VAR_A_OK",
            "TREND_STATUS": "In Bull Run",
            "TREND_STATUS_SL": "Unconfirmed",
            "CAR_RATING": "Buy/Average Out",
            "CMP": 150.0,
            "TURNOVER": 1000.0,
        },
        # Variant B Bull Run matches (should automatically match A as well)
        {
            "SYMBOL": "VAR_B_OK",
            "TREND_STATUS": "In Bull Run",
            "TREND_STATUS_SL": "In Bull Run (SL)",
            "CAR_RATING": "Buy/Average Out",
            "CMP": 50.0,
            "TURNOVER": 2000.0,
        },
        # Avoided due to CAR
        {
            "SYMBOL": "AVOID_CAR",
            "TREND_STATUS": "In Bull Run",
            "TREND_STATUS_SL": "In Bull Run (SL)",
            "CAR_RATING": "Avoid/Hold",
            "CMP": 300.0,
            "TURNOVER": 3000.0,
        },
        # Not in Bull Run
        {
            "SYMBOL": "BEARISH",
            "TREND_STATUS": "In Bear Run",
            "TREND_STATUS_SL": "In Bear Run (SL)",
            "CAR_RATING": "Buy/Average Out",
            "CMP": 10.0,
            "TURNOVER": 500.0,
        },
    ]

    path = _make_dummy_analyzed_csv(tmp_path, rows)
    df_a, df_b = run_nifty_ki_dukan(path, output_dir=str(tmp_path), date_str="20260529")

    # Variant A (No SL) should have both VAR_A_OK and VAR_B_OK
    symbols_a = df_a["NSE Code"].tolist()
    assert "VAR_A_OK" in symbols_a
    assert "VAR_B_OK" in symbols_a
    assert "AVOID_CAR" not in symbols_a
    assert "BEARISH" not in symbols_a

    # Variant B (SL) should only have VAR_B_OK
    symbols_b = df_b["NSE Code"].tolist()
    assert "VAR_B_OK" in symbols_b
    assert "VAR_A_OK" not in symbols_b
    assert "AVOID_CAR" not in symbols_b


def test_run_nifty_ki_dukan_sorts_cmp_ascending(tmp_path: str) -> None:
    """Outputs must be sorted by CMP ascending (cheapest stocks first)."""
    rows = [
        {
            "SYMBOL": "EXPENSIVE",
            "TREND_STATUS": "In Bull Run",
            "CAR_RATING": "Buy/Average Out",
            "CMP": 1000.0,
        },
        {
            "SYMBOL": "CHEAP",
            "TREND_STATUS": "In Bull Run",
            "CAR_RATING": "Buy/Average Out",
            "CMP": 50.0,
        },
        {
            "SYMBOL": "MID",
            "TREND_STATUS": "In Bull Run",
            "CAR_RATING": "Buy/Average Out",
            "CMP": 250.0,
        },
    ]

    path = _make_dummy_analyzed_csv(tmp_path, rows)
    df_a, _ = run_nifty_ki_dukan(path, output_dir=str(tmp_path), date_str="20260529")

    assert df_a.iloc[0]["NSE Code"] == "CHEAP"
    assert df_a.iloc[1]["NSE Code"] == "MID"
    assert df_a.iloc[2]["NSE Code"] == "EXPENSIVE"
