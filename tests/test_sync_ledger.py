"""Unit tests for SQLite SyncLedger & ETL Audit Logger."""

from datetime import date
from pathlib import Path
import pytest

from src.storage.sync_ledger import SyncLedger


def test_sync_ledger_init_and_upsert(tmp_path: Path):
    db_file = tmp_path / "test_ledger.db"
    log_file = tmp_path / "test_etl.jsonl"
    ledger = SyncLedger(db_path=db_file, log_path=log_file)

    # Initially empty
    summary = ledger.get_summary()
    assert summary["total_symbols"] == 0

    # Insert settled historical symbol
    ledger.update_symbol("RELIANCE", "2000-01-01", "2026-11-10", 6000, status="OK", source="yfinance")
    summary = ledger.get_summary()
    assert summary["total_symbols"] == 1
    assert summary["latest_date"] == "2026-11-10"

    # Query stale symbols against 2026-11-10
    stale = ledger.get_stale_symbols(["RELIANCE", "TCS"], target_date="2026-11-10")
    assert "TCS" in stale
    assert "RELIANCE" not in stale

    # Upsert with newer settled date
    ledger.update_symbol("RELIANCE", "2000-01-01", "2026-11-11", 6001, status="OK", source="yfinance")
    summary = ledger.get_summary()
    assert summary["total_symbols"] == 1
    assert summary["latest_date"] == "2026-11-11"


def test_sync_ledger_provisional_intraday(tmp_path: Path):
    from datetime import date
    from src.storage.sync_ledger import is_nse_market_settled

    db_file = tmp_path / "test_ledger.db"
    log_file = tmp_path / "test_etl.jsonl"
    ledger = SyncLedger(db_path=db_file, log_path=log_file)

    today_str = date.today().isoformat()
    # Inserting today's date
    ledger.update_symbol("INFY", "2000-01-01", today_str, 5000, status="OK", source="yfinance")
    summary = ledger.get_summary()
    assert summary["total_symbols"] == 1
    assert summary["latest_date"] == today_str

    if not is_nse_market_settled():
        # During market hours, today's bar must be PROVISIONAL
        assert summary["provisional_count"] == 1
        # When target_date is today, INFY is flagged as stale because it needs final EOD bar
        stale = ledger.get_stale_symbols(["INFY"], target_date=today_str)
        assert "INFY" in stale


def test_sync_ledger_etl_log(tmp_path: Path):
    db_file = tmp_path / "test_ledger.db"
    log_file = tmp_path / "test_etl.jsonl"
    ledger = SyncLedger(db_path=db_file, log_path=log_file)

    ledger.log_etl_run({"action": "test_run", "updated": 5, "status": "COMPLETED"})
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "test_run" in content
    assert "COMPLETED" in content
