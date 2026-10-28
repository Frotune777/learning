"""
File: tests/test_historical_sync_quarantine.py
Purpose: Unit test suite for failed symbols quarantine registry (SQLite WAL).
"""

import os
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from src.data.fetcher.prices.yfinance_fetcher import YFinanceFetcher
from src.nse_bhavcopy.fyers_fetcher import FyersAuthError
from src.storage.historical_sync import HistoricalSync


def test_quarantine_round_trip(tmp_path: Path) -> None:
    sync = HistoricalSync(data_dir=str(tmp_path))
    symbols = ["TCS", "INFY", "RELIANCE"]
    for sym in symbols:
        sync._record_failed_symbol(sym, reason="Test error")

    loaded = sync._load_failed_symbols()
    assert loaded == set(symbols)

    sync._remove_failed_symbol("INFY")
    assert sync._load_failed_symbols() == {"TCS", "RELIANCE"}


def test_quarantine_idempotency(tmp_path: Path) -> None:
    sync = HistoricalSync(data_dir=str(tmp_path))
    sym = "TATAMOTORS"
    sync._record_failed_symbol(sym, reason="Initial attempt")
    sync._record_failed_symbol(sym, reason="Updated attempt")

    db_path = os.path.join(str(tmp_path), "failed_symbols.db")
    assert os.path.exists(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT symbol, reason FROM failed WHERE symbol = ?", (sym,))
    rows = cur.fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0][0] == sym
    assert rows[0][1] == "Updated attempt"


def test_quarantine_csv_migration(tmp_path: Path) -> None:
    csv_path = tmp_path / "failed_symbols.csv"
    csv_content = (
        "SYMBOL,LAST_ATTEMPT,ERROR_REASON\n"
        "WIPRO,2026-05-01 10:00:00,Timeout\n"
        "HCLTECH,2026-05-01 10:05:00,No data\n"
        "  ltim  ,2026-05-01 10:10:00,Delisted\n"
    )
    csv_path.write_text(csv_content)

    db_path = tmp_path / "failed_symbols.db"
    assert not db_path.exists()

    sync = HistoricalSync(data_dir=str(tmp_path))
    loaded = sync._load_failed_symbols()

    assert loaded == {"WIPRO", "HCLTECH", "LTIM"}
    assert db_path.exists()
    assert (tmp_path / "failed_symbols.csv.migrated").exists()
    assert not csv_path.exists()


def test_quarantine_auth_failure_guard(tmp_path: Path) -> None:
    sync = HistoricalSync(data_dir=str(tmp_path))

    mock_fyers = MagicMock()
    mock_fyers.fetch.side_effect = FyersAuthError("401 Unauthorized")
    sync.fetcher = mock_fyers

    dates = pd.date_range("2026-01-01", periods=5)
    fallback_df = pd.DataFrame(
        {
            "Open": [100.0] * 5,
            "High": [105.0] * 5,
            "Low": [95.0] * 5,
            "Close": [102.0] * 5,
            "Volume": [1000.0] * 5,
        },
        index=dates,
    )

    with patch.object(YFinanceFetcher, "fetch", return_value=fallback_df):
        results = sync.sync_batch(["RELIANCE"])
        assert results.get("RELIANCE") is True

    # Ensure auth error triggering fallback does NOT quarantine symbol
    failed = sync._load_failed_symbols()
    assert "RELIANCE" not in failed


def test_quarantine_concurrent_writes(tmp_path: Path) -> None:
    # Two connections write separate symbols
    sync1 = HistoricalSync(data_dir=str(tmp_path))
    sync2 = HistoricalSync(data_dir=str(tmp_path))

    sync1._record_failed_symbol("WRITER_ONE", reason="Worker 1 failure")
    sync2._record_failed_symbol("WRITER_TWO", reason="Worker 2 failure")

    # A third connection/instance reads
    sync3 = HistoricalSync(data_dir=str(tmp_path))
    loaded = sync3._load_failed_symbols()

    assert "WRITER_ONE" in loaded
    assert "WRITER_TWO" in loaded

    # Verify journal_mode is WAL
    db_path = tmp_path / "failed_symbols.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode")
    mode = cur.fetchone()[0]
    conn.close()
    assert mode.lower() == "wal"

