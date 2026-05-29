"""
File: tests/test_rsi_scanner.py
Purpose: Unit tests for rsi_scanner module using mocked screener CSVs.
Last Modified: 2026-05-29
"""

import os
from unittest.mock import patch

import pandas as pd
import pytest

from src.nse_bhavcopy.rsi_scanner import (
    MIN_PRICE_DROP_PCT,
    RSI_ENTRY_THRESHOLD,
    _rsi_to_step_hint,
    check_averaging_eligible,
    get_todays_buy,
    scan_rsi_signals,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────


def _make_analyzed_csv(tmp_path: str, rows: list[dict]) -> str:  # type: ignore[type-arg]
    """Write a minimal analyzed CSV and return its path."""
    df = pd.DataFrame(rows)
    path = os.path.join(str(tmp_path), "analyzed.csv")
    df.to_csv(path, index=False)
    return path


# ─── _rsi_to_step_hint ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "rsi,expected",
    [
        (3.0, "Step 7 (Average < 5)"),
        (8.0, "Step 6 (Average < 10)"),
        (13.0, "Step 5 (Average < 15)"),
        (18.0, "Step 4 (Average < 20)"),
        (22.0, "Step 3 (Average < 25)"),
        (28.0, "Step 2 (Average < 30)"),
        (33.0, "Step 1 (Entry < 35)"),
    ],
)
def test_rsi_to_step_hint(rsi: float, expected: str) -> None:
    """_rsi_to_step_hint maps RSI ranges to correct step labels."""
    assert _rsi_to_step_hint(rsi) == expected


def test_rsi_to_step_hint_nan() -> None:
    """_rsi_to_step_hint returns 'Unknown' for NaN input."""
    assert _rsi_to_step_hint(float("nan")) == "Unknown"


# ─── scan_rsi_signals ─────────────────────────────────────────────────────────


def test_scan_rsi_signals_raises_on_missing_csv(tmp_path: str) -> None:
    """scan_rsi_signals raises FileNotFoundError for missing CSV."""
    with pytest.raises(FileNotFoundError):
        scan_rsi_signals(str(tmp_path / "missing.csv"))


def test_scan_rsi_signals_returns_empty_on_no_rsi_column(
    tmp_path: str,
) -> None:
    """scan_rsi_signals returns empty DataFrame if RSI_14 column absent."""
    path = _make_analyzed_csv(str(tmp_path), [{"SYMBOL": "TCS", "CMP": 3500.0}])
    universe = ["TCS"]
    with patch("src.nse_bhavcopy.rsi_scanner.get_rsi_universe", return_value=universe):
        result = scan_rsi_signals(
            path, cache_dir=str(tmp_path), output_dir=str(tmp_path)
        )
    assert result.empty


def test_scan_rsi_signals_filters_universe(tmp_path: str) -> None:
    """scan_rsi_signals only returns symbols in the RSI universe."""
    rows = [
        {"SYMBOL": "TCS", "RSI_14": 30.0, "CMP": 3500.0, "PREVIOUS_CLOSE": 3490.0},
        {"SYMBOL": "OUTSIDE", "RSI_14": 20.0, "CMP": 100.0, "PREVIOUS_CLOSE": 98.0},
    ]
    path = _make_analyzed_csv(str(tmp_path), rows)
    with (
        patch(
            "src.nse_bhavcopy.rsi_scanner.get_rsi_universe",
            return_value=["TCS"],
        ),
        patch(
            "src.nse_bhavcopy.rsi_scanner.get_nifty50",
            return_value=["TCS"],
        ),
    ):
        result = scan_rsi_signals(
            path, cache_dir=str(tmp_path), output_dir=str(tmp_path)
        )

    assert "OUTSIDE" not in result["NSE Code"].tolist()
    assert "TCS" in result["NSE Code"].tolist()


def test_scan_rsi_signals_sorts_by_rsi_ascending(tmp_path: str) -> None:
    """scan_rsi_signals returns rows sorted by RSI ascending."""
    rows = [
        {"SYMBOL": "A", "RSI_14": 34.0, "CMP": 100.0, "PREVIOUS_CLOSE": 99.0},
        {"SYMBOL": "B", "RSI_14": 25.0, "CMP": 200.0, "PREVIOUS_CLOSE": 195.0},
        {"SYMBOL": "C", "RSI_14": 10.0, "CMP": 50.0, "PREVIOUS_CLOSE": 49.0},
    ]
    path = _make_analyzed_csv(str(tmp_path), rows)
    with (
        patch(
            "src.nse_bhavcopy.rsi_scanner.get_rsi_universe",
            return_value=["A", "B", "C"],
        ),
        patch("src.nse_bhavcopy.rsi_scanner.get_nifty50", return_value=[]),
    ):
        result = scan_rsi_signals(
            path, cache_dir=str(tmp_path), output_dir=str(tmp_path)
        )

    assert result.iloc[0]["NSE Code"] == "C"
    assert result.iloc[-1]["NSE Code"] == "A"


def test_scan_rsi_signals_computes_amo_price(tmp_path: str) -> None:
    """AMO Price = PREVIOUS_CLOSE - 0.01."""
    rows = [
        {
            "SYMBOL": "SBIN",
            "RSI_14": 28.0,
            "CMP": 400.0,
            "PREVIOUS_CLOSE": 398.00,
        }
    ]
    path = _make_analyzed_csv(str(tmp_path), rows)
    with (
        patch(
            "src.nse_bhavcopy.rsi_scanner.get_rsi_universe",
            return_value=["SBIN"],
        ),
        patch("src.nse_bhavcopy.rsi_scanner.get_nifty50", return_value=[]),
    ):
        result = scan_rsi_signals(
            path, cache_dir=str(tmp_path), output_dir=str(tmp_path)
        )

    assert abs(result.iloc[0]["AMO Price"] - 397.99) < 0.001


def test_scan_rsi_signals_excludes_above_threshold(tmp_path: str) -> None:
    """scan_rsi_signals excludes stocks with RSI >= 35."""
    rows = [{"SYMBOL": "SAFE", "RSI_14": RSI_ENTRY_THRESHOLD, "CMP": 100.0}]
    path = _make_analyzed_csv(str(tmp_path), rows)
    with (
        patch(
            "src.nse_bhavcopy.rsi_scanner.get_rsi_universe",
            return_value=["SAFE"],
        ),
        patch("src.nse_bhavcopy.rsi_scanner.get_nifty50", return_value=[]),
    ):
        result = scan_rsi_signals(
            path, cache_dir=str(tmp_path), output_dir=str(tmp_path)
        )
    assert result.empty


# ─── get_todays_buy ───────────────────────────────────────────────────────────


def test_get_todays_buy_returns_first_row() -> None:
    """get_todays_buy returns the first row of a non-empty DataFrame."""
    df = pd.DataFrame([{"NSE Code": "IRFC", "RSI": 28.0}])
    row = get_todays_buy(df)
    assert row is not None
    assert row["NSE Code"] == "IRFC"


def test_get_todays_buy_returns_none_on_empty() -> None:
    """get_todays_buy returns None for empty DataFrame."""
    assert get_todays_buy(pd.DataFrame()) is None


# ─── check_averaging_eligible ─────────────────────────────────────────────────


def test_averaging_eligible_happy_path() -> None:
    """Returns eligible=True when RSI crosses threshold and price dropped >=3.14%."""
    result = check_averaging_eligible(
        last_buy_price=612.50,
        current_price=580.00,
        current_rsi=28.5,
        last_rsi_step=1,
    )
    assert result["eligible"] is True
    assert result["next_step"] == 2


def test_averaging_ineligible_rsi_not_crossed() -> None:
    """Returns eligible=False when RSI hasn't crossed next threshold."""
    result = check_averaging_eligible(
        last_buy_price=612.50,
        current_price=580.00,
        current_rsi=31.0,  # Still above step-2 threshold of 30
        last_rsi_step=1,
    )
    assert result["eligible"] is False


def test_averaging_ineligible_insufficient_price_drop() -> None:
    """Returns eligible=False when price drop < MIN_PRICE_DROP_PCT."""
    result = check_averaging_eligible(
        last_buy_price=612.50,
        current_price=610.00,  # Only ~0.4% drop
        current_rsi=28.5,
        last_rsi_step=1,
    )
    assert result["eligible"] is False
    assert str(MIN_PRICE_DROP_PCT) in result["reason"]


def test_averaging_max_steps_reached() -> None:
    """Returns eligible=False and next_step=None after step 7."""
    result = check_averaging_eligible(
        last_buy_price=100.0,
        current_price=50.0,
        current_rsi=1.0,
        last_rsi_step=7,
    )
    assert result["eligible"] is False
    assert result["next_step"] is None
