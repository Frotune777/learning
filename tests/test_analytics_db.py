"""
Tests for unified signals.db and smc_calls migration.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from src.analytics.db import db, init_db
from src.analytics.migrate_smc_calls import migrate_smc_calls


def test_init_db_and_context_manager(tmp_path: Path) -> None:
    db_file = str(tmp_path / "test_signals.db")

    # Before init, db() should yield None without creating file
    with db(db_file) as conn:
        assert conn is None
    assert not os.path.exists(db_file)

    # Init db
    init_db(db_file)
    assert os.path.exists(db_file)

    # After init, db() yields valid connection
    with db(db_file) as conn:
        assert conn is not None
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        assert "runs" in tables
        assert "signals" in tables


def test_migration_dedupes(tmp_path: Path) -> None:
    src_db = str(tmp_path / "smc_calls.sqlite")
    dest_db = str(tmp_path / "signals.db")

    conn = sqlite3.connect(src_db)
    conn.execute(
        """
        CREATE TABLE trading_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            direction TEXT NOT NULL,
            setup_type TEXT NOT NULL,
            entry_price REAL NOT NULL,
            stop_loss REAL NOT NULL,
            target_1 REAL NOT NULL,
            target_2 REAL NOT NULL,
            risk_reward REAL NOT NULL,
            status TEXT NOT NULL,
            notes TEXT
        )
        """
    )
    # Seed 3 rows: row 1 & row 2 identical on (symbol, setup_type, direction, date, entry)
    conn.execute(
        """
        INSERT INTO trading_calls VALUES
        (1, 'INFY', '2026-10-15 10:00:00', 'BUY', 'FVG_FILL', 1500.0, 1480.0,
         1540.0, 1560.0, 2.0, 'PENDING', 'Note 1'),
        (2, 'INFY', '2026-10-15 10:05:00', 'BUY', 'FVG_FILL', 1500.0, 1480.0,
         1540.0, 1560.0, 2.0, 'PENDING', 'Duplicate of 1'),
        (3, 'TCS',  '2026-10-15 10:00:00', 'BUY', 'FVG_FILL', 3500.0, 3450.0,
         3600.0, 3650.0, 2.0, 'PENDING', 'Different symbol')
        """
    )
    conn.commit()
    conn.close()

    res = migrate_smc_calls(src_path=src_db, dest_path=dest_db)

    assert res["source_rows"] == 3
    assert res["inserted_rows"] == 2
    assert res["duplicates_dropped"] == 1

    # Verify signals table has exactly 2 rows
    with db(dest_db) as dest_conn:
        assert dest_conn is not None
        count = dest_conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        assert count == 2

    # Assert .migrated file exists and original .sqlite no longer exists
    assert os.path.exists(f"{src_db}.migrated")
    assert not os.path.exists(src_db)


def test_create_call_inserts_and_dedupes(tmp_path: Path) -> None:
    from src.engine.smc_decision import TradingCall
    from src.storage.smc_db import SMCDatabase

    db_path = str(tmp_path / "test_signals.db")
    smc_db = SMCDatabase(db_path=db_path)

    call = TradingCall(
        symbol="TCS",
        timestamp="2026-10-15 10:00:00",
        direction="BUY",
        setup_type="OB_BULLISH",
        entry_price=3500.0,
        stop_loss=3450.0,
        target_1=3600.0,
        target_2=3650.0,
        risk_reward=2.0,
        status="PENDING",
        notes="First call",
    )

    id1 = smc_db.create_call(call)
    assert id1 > 0

    id2 = smc_db.create_call(call)
    assert id2 == 0

    calls = smc_db.get_calls()
    assert len(calls) == 1
    assert calls[0]["symbol"] == "TCS"
