"""
Migration script: smc_calls.sqlite to signals.db.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime

from src.analytics.db import init_db

logger = logging.getLogger(__name__)


def migrate_smc_calls(
    src_path: str = "data/smc_calls.sqlite",
    dest_path: str = "data/signals.db",
) -> dict[str, int]:
    """
    Migrate existing smc_calls.sqlite records into signals.db with deduplication.
    Renames source to {src_path}.migrated upon completion.
    """
    if not os.path.exists(src_path):
        logger.warning("Source database %s does not exist; skipping migration.", src_path)
        return {"source_rows": 0, "inserted_rows": 0, "duplicates_dropped": 0}

    init_db(dest_path)

    src_conn = sqlite3.connect(src_path)
    src_conn.row_factory = sqlite3.Row
    try:
        tables = [
            r[0]
            for r in src_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        target_table = "trading_calls" if "trading_calls" in tables else "calls"
        if target_table not in tables:
            logger.warning("No calls table found in %s; found tables: %s", src_path, tables)
            return {"source_rows": 0, "inserted_rows": 0, "duplicates_dropped": 0}

        rows = src_conn.execute(f"SELECT * FROM {target_table}").fetchall()
    finally:
        src_conn.close()

    source_count = len(rows)
    run_id = f"migration_smc_calls_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    now_str = datetime.now().isoformat()

    dest_conn = sqlite3.connect(dest_path, timeout=10.0)
    try:
        dest_conn.execute("PRAGMA foreign_keys=ON")
        dest_conn.execute("PRAGMA journal_mode=WAL")
        dest_conn.execute(
            """
            INSERT OR IGNORE INTO runs (
                run_id, run_type, started_at, completed_at, filters_json,
                universe_size, signals_found, engine_version, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "migration",
                now_str,
                now_str,
                json.dumps({"source": src_path, "table": target_table}),
                source_count,
                0,
                "1.0.0",
                "COMPLETED",
            ),
        )

        inserted_count = 0
        for r in rows:
            r_dict = dict(r)
            symbol = r_dict["symbol"]
            direction = r_dict["direction"]
            strategy = (
                r_dict.get("setup_type")
                or r_dict.get("pattern")
                or r_dict.get("strategy")
                or "SMC"
            )
            timestamp = str(r_dict.get("timestamp") or r_dict.get("signal_date") or now_str)
            signal_date = timestamp[:10]
            entry_raw = (
                r_dict.get("entry_price")
                if "entry_price" in r_dict
                else r_dict.get("entry")
            )
            entry = float(entry_raw)
            stop_loss = float(r_dict["stop_loss"])
            tp1_raw = r_dict.get("target_1") if "target_1" in r_dict else r_dict.get("tp1")
            tp1 = float(tp1_raw) if tp1_raw is not None else None
            tp2_raw = r_dict.get("target_2") if "target_2" in r_dict else r_dict.get("tp2")
            tp2 = float(tp2_raw) if tp2_raw is not None else None
            rr_raw = r_dict.get("risk_reward") if "risk_reward" in r_dict else r_dict.get("rr")
            rr = float(rr_raw) if rr_raw is not None else None
            conf_raw = r_dict.get("confidence")
            confidence = float(conf_raw) if conf_raw is not None else 1.0
            notes = r_dict.get("notes")
            context_json = json.dumps({"notes": notes}) if notes else None
            status = r_dict.get("status") or "PENDING"

            cur = dest_conn.execute(
                """
                INSERT OR IGNORE INTO signals (
                    run_id, symbol, direction, strategy, signal_date, entry,
                    stop_loss, tp1, tp2, rr, confidence, context_json, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    symbol,
                    direction,
                    strategy,
                    signal_date,
                    entry,
                    stop_loss,
                    tp1,
                    tp2,
                    rr,
                    confidence,
                    context_json,
                    status,
                    timestamp,
                    now_str,
                ),
            )
            if cur.rowcount > 0:
                inserted_count += 1

        dest_conn.execute(
            "UPDATE runs SET signals_found = ? WHERE run_id = ?",
            (inserted_count, run_id),
        )
        dest_conn.commit()
    finally:
        dest_conn.close()

    migrated_path = f"{src_path}.migrated"
    os.rename(src_path, migrated_path)

    dropped = source_count - inserted_count
    logger.info(
        "Migrated %d rows from %s to %s (inserted=%d, dropped_duplicates=%d)",
        source_count,
        src_path,
        dest_path,
        inserted_count,
        dropped,
    )
    return {
        "source_rows": source_count,
        "inserted_rows": inserted_count,
        "duplicates_dropped": dropped,
    }


if __name__ == "__main__":
    import sys

    res = migrate_smc_calls()
    print(f"Migration completed: {res}")
    sys.exit(0)
