"""
Tests for offline analysis, coverage checking, and fill-from-raw.
"""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

import pandas as pd
import pytest

import src.core.config as config
from src.analytics.data_availability import build_from_raw, check_coverage
from src.core.config import OfflineError
from src.data.fetcher.prices.yfinance_fetcher import YFinanceFetcher


def _create_mock_bhavcopy_zip(
    zip_path: str,
    date_str: str,
    symbols: list[str],
) -> None:
    """Helper to create a realistic mock Bhavcopy ZIP archive."""
    rows = []
    for sym in symbols:
        rows.append(
            {
                "TradDt": date_str,
                "BizDt": date_str,
                "Sgmt": "CM",
                "Src": "NSE",
                "TckrSymb": sym,
                "SctySrs": "EQ",
                "OpnPric": 100.0,
                "HghPric": 105.0,
                "LwPric": 98.0,
                "ClsPric": 102.0,
                "TtlTradgVol": 10000,
            }
        )
    df = pd.DataFrame(rows)
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"BhavCopy_NSE_CM_0_0_0_{date_str.replace('-', '')}_F_0000.csv", csv_bytes)

    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with open(zip_path, "wb") as f:
        f.write(buf.getvalue())


def test_check_coverage_available(tmp_path: Path) -> None:
    hist_dir = str(tmp_path / "historical" / "1d")
    raw_dir = str(tmp_path / "raw")
    os.makedirs(hist_dir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)

    dates = pd.date_range("2026-06-01", "2026-06-10", freq="B")
    df = pd.DataFrame(
        {
            "Open": [100.0] * len(dates),
            "High": [105.0] * len(dates),
            "Low": [98.0] * len(dates),
            "Close": [102.0] * len(dates),
            "Volume": [1000] * len(dates),
        },
        index=dates,
    )
    df.index.name = "Date"
    df.to_parquet(os.path.join(hist_dir, "INFY.parquet"))

    # Also seed raw zips for reference dates
    for d in dates:
        d_str = d.strftime("%Y%m%d")
        _create_mock_bhavcopy_zip(
            os.path.join(raw_dir, f"BhavCopy_NSE_CM_0_0_0_{d_str}_F_0000.csv.zip"),
            d.strftime("%Y-%m-%d"),
            ["INFY"],
        )

    cov = check_coverage(
        ["INFY"],
        start="2026-06-01",
        end="2026-06-10",
        hist_dir=hist_dir,
        raw_dir=raw_dir,
    )
    assert "INFY" in cov["available"]


def test_check_coverage_loadable(tmp_path: Path) -> None:
    hist_dir = str(tmp_path / "historical" / "1d")
    raw_dir = str(tmp_path / "raw")
    os.makedirs(hist_dir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)

    dates = pd.date_range("2026-06-01", "2026-06-05", freq="B")
    for d in dates:
        d_str = d.strftime("%Y%m%d")
        _create_mock_bhavcopy_zip(
            os.path.join(raw_dir, f"BhavCopy_NSE_CM_0_0_0_{d_str}_F_0000.csv.zip"),
            d.strftime("%Y-%m-%d"),
            ["TCS"],
        )

    # TCS has NO parquet in hist_dir, but exists in raw_dir
    cov = check_coverage(
        ["TCS"],
        start="2026-06-01",
        end="2026-06-05",
        hist_dir=hist_dir,
        raw_dir=raw_dir,
    )
    assert "TCS" in cov["loadable"]


def test_build_from_raw_success(tmp_path: Path) -> None:
    hist_dir = str(tmp_path / "historical" / "1d")
    raw_dir = str(tmp_path / "raw")

    dates = pd.date_range("2026-06-01", "2026-06-03", freq="B")
    for d in dates:
        d_str = d.strftime("%Y%m%d")
        _create_mock_bhavcopy_zip(
            os.path.join(raw_dir, f"BhavCopy_NSE_CM_0_0_0_{d_str}_F_0000.csv.zip"),
            d.strftime("%Y-%m-%d"),
            ["WIPRO"],
        )

    res = build_from_raw(
        "WIPRO",
        start="2026-06-01",
        end="2026-06-03",
        raw_dir=raw_dir,
        hist_dir=hist_dir,
    )
    assert res is True

    parquet_file = os.path.join(hist_dir, "WIPRO.parquet")
    assert os.path.exists(parquet_file)

    df = pd.read_parquet(parquet_file)
    assert len(df) == 3
    assert "Close" in df.columns
    assert "Volume" in df.columns


def test_build_from_raw_missing(tmp_path: Path) -> None:
    hist_dir = str(tmp_path / "historical" / "1d")
    raw_dir = str(tmp_path / "raw")
    os.makedirs(hist_dir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)

    res = build_from_raw(
        "NONEXISTENT",
        start="2026-06-01",
        end="2026-06-05",
        raw_dir=raw_dir,
        hist_dir=hist_dir,
    )
    assert res is False
    assert not os.path.exists(os.path.join(hist_dir, "NONEXISTENT.parquet"))


def test_screen_offline_skips_network(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure offline flag blocks network calls
    monkeypatch.setattr(config, "OFFLINE", True)
    monkeypatch.setattr(config.Config, "OFFLINE", True)

    fetcher = YFinanceFetcher()
    with pytest.raises(OfflineError):
        fetcher.fetch("RELIANCE")


def test_screen_fill_from_raw(tmp_path: Path) -> None:
    hist_dir = str(tmp_path / "historical" / "1d")
    raw_dir = str(tmp_path / "raw")

    d_str = "20260601"
    _create_mock_bhavcopy_zip(
        os.path.join(raw_dir, f"BhavCopy_NSE_CM_0_0_0_{d_str}_F_0000.csv.zip"),
        "2026-06-01",
        ["RELIANCE"],
    )

    parquet_path = os.path.join(hist_dir, "RELIANCE.parquet")
    if os.path.exists(parquet_path):
        os.remove(parquet_path)

    # Parquet does not exist before
    assert not os.path.exists(parquet_path)

    res = build_from_raw(
        "RELIANCE",
        start="2026-06-01",
        end="2026-06-01",
        raw_dir=raw_dir,
        hist_dir=hist_dir,
    )
    assert res is True

    # Parquet exists after
    assert os.path.exists(parquet_path)
    df = pd.read_parquet(parquet_path)
    assert len(df) == 1
