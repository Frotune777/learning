"""
Unified SQLite database for signal tracking.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
from collections.abc import Generator

DEFAULT_DB_PATH = "data/signals.db"

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    run_type        TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    filters_json    TEXT,
    universe_size   INTEGER,
    signals_found   INTEGER,
    engine_version  TEXT,
    status          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS signals (
    signal_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,
    strategy        TEXT NOT NULL,
    signal_date     TEXT NOT NULL,
    entry           REAL NOT NULL,
    stop_loss       REAL NOT NULL,
    tp1             REAL,
    tp2             REAL,
    rr              REAL,
    confidence      REAL,
    context_json    TEXT,
    status          TEXT NOT NULL DEFAULT 'PENDING',
    triggered_at    TEXT,
    triggered_price REAL,
    exit_at         TEXT,
    exit_price      REAL,
    exit_reason     TEXT,
    realized_rr     REAL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_signals_natural
    ON signals(symbol, strategy, direction, signal_date, entry);
CREATE INDEX IF NOT EXISTS ix_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS ix_signals_strategy ON signals(strategy);
CREATE INDEX IF NOT EXISTS ix_signals_symbol ON signals(symbol);
CREATE INDEX IF NOT EXISTS ix_signals_run ON signals(run_id);
"""


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize signals database and create tables/indexes if missing."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10.0)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA_DDL)
        conn.commit()
    finally:
        conn.close()


@contextlib.contextmanager
def db(db_path: str = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection | None, None, None]:
    """
    Context manager yielding connection to signals.db with WAL mode and timeout=10.0.
    No-op if the database does not exist yet.
    """
    if not os.path.exists(db_path):
        yield None
        return

    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
    finally:
        conn.close()
