"""Unit tests for delivery backfill loader."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.platform.loaders.delivery_backfill import (
    download_sec_bhavdata_range,
    parse_sec_bhavdata,
)


@pytest.fixture
def sample_sec_bhavdata_csv(tmp_path: Path) -> Path:
    """Create a mock sec_bhavdata_full CSV with whitespace and mixed series."""
    csv_file = tmp_path / "sec_bhavdata_full_16102026.csv"
    content = (
        "SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, "
        "LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER\n"
        " TCS , EQ , 16-Oct-2026 , 2350.0 , 2360.0 , 2370.0 , 2340.0 , 2355.0 , 2355.0 , 2355.0 , 100000 , 2355.0 , 1500 , 55000 , 55.00 \n"
        " INFY , BE , 16-Oct-2026 , 1400.0 , 1410.0 , 1420.0 , 1390.0 , 1405.0 , 1405.0 , 1405.0 , 50000 , 702.5 , 800 , 20000 , 40.00 \n"
        " NIFTYBEES , EQ , 16-Oct-2026 , 250.0 , 251.0 , 252.0 , 249.0 , 250.5 , 250.5 , 250.5 , 10000 , 25.0 , 100 , - , - \n"
    )
    csv_file.write_text(content, encoding="utf-8")
    return csv_file


def test_parse_sec_bhavdata_extracts_delivery_columns(sample_sec_bhavdata_csv: Path) -> None:
    df = parse_sec_bhavdata(sample_sec_bhavdata_csv, trade_date=date(2026, 10, 16))
    assert not df.empty
    tcs = df[df["symbol"] == "TCS"]
    assert len(tcs) == 1
    row = tcs.iloc[0]
    assert row["deliverable_qty"] == 55000
    assert row["delivery_pct"] == 55.0
    assert 0 <= row["delivery_pct"] <= 100


def test_parse_sec_bhavdata_filters_non_eq_series(sample_sec_bhavdata_csv: Path) -> None:
    df = parse_sec_bhavdata(sample_sec_bhavdata_csv, trade_date=date(2026, 10, 16))
    symbols = df["symbol"].tolist()
    assert "INFY" not in symbols  # BE series filtered out


def test_parse_sec_bhavdata_handles_whitespace(sample_sec_bhavdata_csv: Path) -> None:
    df = parse_sec_bhavdata(sample_sec_bhavdata_csv, trade_date=date(2026, 10, 16))
    assert "TCS" in df["symbol"].values
    tcs = df[df["symbol"] == "TCS"].iloc[0]
    assert tcs["trade_date"] == date(2026, 10, 16)


def test_download_skips_existing_cache(tmp_path: Path) -> None:
    cache_dir = tmp_path / "delivery"
    cache_dir.mkdir(parents=True, exist_ok=True)
    stamp = "16102026"
    test_file = cache_dir / f"sec_bhavdata_full_{stamp}.csv"
    test_file.write_text("dummy content", encoding="utf-8")

    with patch("requests.Session.get") as mock_get:
        count = download_sec_bhavdata_range(
            start_date=date(2026, 10, 16),
            end_date=date(2026, 10, 16),
            cache_dir=cache_dir,
            rate_delay=0.0,
        )
        assert count == 1
        mock_get.assert_not_called()


def test_download_skips_404_gracefully(tmp_path: Path) -> None:
    cache_dir = tmp_path / "delivery"
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("requests.Session.get", return_value=mock_resp):
        count = download_sec_bhavdata_range(
            start_date=date(2026, 10, 16),
            end_date=date(2026, 10, 16),
            cache_dir=cache_dir,
            rate_delay=0.0,
        )
        assert count == 0
