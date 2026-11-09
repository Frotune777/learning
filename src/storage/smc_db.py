"""
File: src/storage/smc_db.py
Purpose: Compatibility wrapper over signals.db for SMC trading calls.
"""

from __future__ import annotations

from datetime import datetime
import json
import sqlite3
from typing import Any

from src.analytics.db import DEFAULT_DB_PATH, init_db
from src.engine.smc_decision import TradingCall


class SMCDatabase:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        init_db(self.db_path)

    def create_call(self, call: TradingCall, run_id: str | None = None) -> int:
        now_str = datetime.now().isoformat()
        if not run_id:
            run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_smc"

        signal_date = str(call.timestamp)[:10] if getattr(call, "timestamp", None) else now_str[:10]
        context_json = json.dumps({"notes": call.notes}) if getattr(call, "notes", None) else None

        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                INSERT OR IGNORE INTO runs (
                    run_id, run_type, started_at, completed_at, status
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, "smc", now_str, now_str, "COMPLETED"),
            )
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO signals (
                    run_id, symbol, direction, strategy, signal_date, entry,
                    stop_loss, tp1, tp2, rr, confidence, context_json, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    call.symbol,
                    call.direction,
                    call.setup_type,
                    signal_date,
                    call.entry_price,
                    call.stop_loss,
                    call.target_1,
                    call.target_2,
                    call.risk_reward,
                    1.0,
                    context_json,
                    call.status or "PENDING",
                    call.timestamp or now_str,
                    now_str,
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return 0
            return cursor.lastrowid or 0

    def get_calls(self, status: str | None = None) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            query = """
                SELECT
                    signal_id AS id,
                    created_at AS timestamp,
                    symbol,
                    direction,
                    strategy AS setup_type,
                    entry AS entry_price,
                    stop_loss,
                    tp1 AS target_1,
                    tp2 AS target_2,
                    rr AS risk_reward,
                    status,
                    context_json AS notes
                FROM signals
            """
            if status:
                query += " WHERE status = ? ORDER BY signal_id DESC"
                cursor = conn.execute(query, (status,))
            else:
                query += " ORDER BY signal_id DESC"
                cursor = conn.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def update_status(self, call_id: int, new_status: str, notes: str | None = None) -> bool:
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            if notes:
                conn.execute(
                    "UPDATE signals SET status = ?, context_json = ?, updated_at = ? WHERE signal_id = ?",
                    (new_status, json.dumps({"notes": notes}), now_str, call_id),
                )
            else:
                conn.execute(
                    "UPDATE signals SET status = ?, updated_at = ? WHERE signal_id = ?",
                    (new_status, now_str, call_id),
                )
            conn.commit()
            return True

    def delete_call(self, call_id: int) -> bool:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM signals WHERE signal_id = ?", (call_id,))
            conn.commit()
            return True
