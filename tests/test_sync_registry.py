"""
File: tests/test_sync_registry.py
Purpose: Regression tests for SyncRegistry date typing and DataHealthCheck fallback.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.data.health import DataHealthCheck
from src.storage.sync_registry import SyncRecord, SyncRegistry


def test_sync_registry_date_typing(tmp_path: Path) -> None:
    """Ensure SyncRegistry handles mixed None and date values without TypeError on sort/max."""
    reg = SyncRegistry(registry_dir=str(tmp_path), timeframe="1d")
    reg.register(["PENDING_SYM"])
    reg._store["ACTIVE_SYM"] = SyncRecord(
        symbol="ACTIVE_SYM",
        status="ok",
        first_bar_date=datetime.date(2025, 1, 1),
        last_bar_date=datetime.date(2026, 10, 15),
        row_count=450,
        timeframe="1d",
    )

    summary = reg.summary()
    assert len(summary) == 2
    assert pd.isna(summary.loc[summary["symbol"] == "PENDING_SYM", "last_bar_date"].iloc[0])
    assert (
        summary.loc[summary["symbol"] == "ACTIVE_SYM", "last_bar_date"].iloc[0]
        == pd.Timestamp("2026-10-15")
    )

    saved_path = reg.save()
    df = pd.read_parquet(saved_path)
    # Regression: calling max/min must not raise TypeError on mixed date and float/NaN
    assert df["last_bar_date"].max() == pd.Timestamp("2026-10-15")
    assert df["first_bar_date"].min() == pd.Timestamp("2025-01-01")


def test_data_health_check_holiday_fallback() -> None:
    """Ensure DataHealthCheck falls back to TAValidator holidays when config is missing."""
    with patch("src.data.health.Path.exists", return_value=False):
        checker = DataHealthCheck()
        assert len(checker.nse_holidays) > 0
        assert pd.Timestamp("2026-01-26") in checker.nse_holidays
