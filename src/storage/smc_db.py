"""
File: src/storage/smc_db.py
Purpose: Local SQLite CRUD interface for active trading calls.
"""

from __future__ import annotations
import sqlite3
from typing import Any
from src.engine.smc_decision import TradingCall

class SMCDatabase:
    def __init__(self, db_path: str = "data/smc_calls.sqlite"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trading_calls (
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
            """)
            conn.commit()

    def create_call(self, call: TradingCall) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO trading_calls (
                    symbol, timestamp, direction, setup_type, entry_price,
                    stop_loss, target_1, target_2, risk_reward, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                call.symbol, call.timestamp, call.direction, call.setup_type,
                call.entry_price, call.stop_loss, call.target_1, call.target_2,
                call.risk_reward, call.status, call.notes
            ))
            conn.commit()
            return cursor.lastrowid

    def get_calls(self, status: str | None = None) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            if status:
                cursor = conn.execute("SELECT * FROM trading_calls WHERE status = ? ORDER BY id DESC", (status,))
            else:
                cursor = conn.execute("SELECT * FROM trading_calls ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    def update_status(self, call_id: int, new_status: str, notes: str | None = None) -> bool:
        with self._get_connection() as conn:
            if notes:
                conn.execute("UPDATE trading_calls SET status = ?, notes = notes || ' | ' || ? WHERE id = ?", (new_status, notes, call_id))
            else:
                conn.execute("UPDATE trading_calls SET status = ? WHERE id = ?", (new_status, call_id))
            conn.commit()
            return True

    def delete_call(self, call_id: int) -> bool:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM trading_calls WHERE id = ?", (call_id,))
            conn.commit()
            return True
