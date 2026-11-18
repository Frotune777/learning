"""
File: src/storage/sync_ledger.py
Purpose: High-performance SQLite WAL sync ledger & structured ETL audit logger.
Provides sub-millisecond pre-sync filtering so already-current symbols are never queried over network.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import sqlite3
from typing import Any

LOGGER = logging.getLogger(__name__)

# Indian Standard Time (IST = UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def is_nse_market_settled(now_dt: datetime | None = None) -> bool:
    """Return True if today's NSE session has completed & settled (post-16:00 IST or weekend)."""
    dt = now_dt or datetime.now(IST)
    if dt.weekday() >= 5:  # Saturday or Sunday
        return True
    return dt.time() >= datetime.strptime("16:00", "%H:%M").time()


def get_latest_settled_trading_day(now_dt: datetime | None = None) -> date:
    """Return the most recent NSE trading date that is fully settled."""
    dt = now_dt or datetime.now(IST)
    d = dt.date()
    # Before 16:00 IST on a weekday, today's bar is forming/unsettled; latest settled is previous trading day
    if dt.weekday() < 5 and not is_nse_market_settled(dt):
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


class SyncLedger:
    """
    SQLite-backed sync state ledger with WAL mode and JSONL audit logging.
    """

    def __init__(
        self,
        db_path: str | Path = "data/sync_ledger.db",
        log_path: str | Path = "logs/etl_sync.jsonl",
    ) -> None:
        self.db_path = Path(db_path)
        self.log_path = Path(log_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sync_ledger';")
            if cur.fetchone():
                cur.execute("PRAGMA table_info(sync_ledger);")
                cols = [r[1] for r in cur.fetchall()]
                if "timeframe" not in cols:
                    LOGGER.info("Migrating sync_ledger schema to composite (symbol, timeframe) primary key...")
                    conn.execute("ALTER TABLE sync_ledger RENAME TO sync_ledger_old;")
                    conn.execute(
                        """
                        CREATE TABLE sync_ledger (
                            symbol TEXT,
                            timeframe TEXT DEFAULT '1d',
                            first_date TEXT,
                            last_date TEXT,
                            row_count INTEGER DEFAULT 0,
                            last_synced_at TEXT,
                            status TEXT DEFAULT 'OK',
                            source TEXT DEFAULT 'yfinance',
                            PRIMARY KEY (symbol, timeframe)
                        );
                        """
                    )
                    conn.execute(
                        """
                        INSERT INTO sync_ledger (symbol, timeframe, first_date, last_date, row_count, last_synced_at, status, source)
                        SELECT symbol, '1d', first_date, last_date, row_count, last_synced_at, status, source FROM sync_ledger_old;
                        """
                    )
                    conn.execute("DROP TABLE sync_ledger_old;")
            else:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sync_ledger (
                        symbol TEXT,
                        timeframe TEXT DEFAULT '1d',
                        first_date TEXT,
                        last_date TEXT,
                        row_count INTEGER DEFAULT 0,
                        last_synced_at TEXT,
                        status TEXT DEFAULT 'OK',
                        source TEXT DEFAULT 'yfinance',
                        PRIMARY KEY (symbol, timeframe)
                    );
                    """
                )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sync_ledger_last_date ON sync_ledger(last_date);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sync_ledger_status ON sync_ledger(status);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sync_ledger_tf ON sync_ledger(timeframe);"
            )

    def bootstrap_from_parquet_lake(
        self, hist_dir: str | Path = "data/historical/1d", force: bool = False
    ) -> int:
        """
        Fast one-time population of ledger from existing Parquet files.
        Only runs if table is empty, unless force=True.
        """
        p = Path(hist_dir)
        if not p.exists():
            return 0

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sync_ledger")
            count = cur.fetchone()[0]
            if count > 0 and not force:
                return count

        try:
            import pyarrow.parquet as pq
        except ImportError:
            LOGGER.warning("pyarrow not installed, skipping bootstrap")
            return 0

        parquets = list(p.glob("*.parquet"))
        if not parquets:
            return 0

        now_iso = datetime.now().isoformat()
        records: list[tuple[str, str, str, str, int, str, str, str]] = []

        LOGGER.info("Bootstrapping sync_ledger from %d Parquet files...", len(parquets))
        for f in parquets:
            sym = f.stem.strip().upper()
            try:
                table = pq.read_table(f, columns=["Date"])
                dates = table["Date"].to_pylist()
                if dates:
                    first_d = str(dates[0])[:10]
                    last_d = str(dates[-1])[:10]
                    records.append(
                        (sym, timeframe, first_d, last_d, len(dates), now_iso, "OK", "local_parquet")
                    )
            except Exception as exc:
                LOGGER.debug("Could not read %s for bootstrap: %s", f.name, exc)

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO sync_ledger (symbol, timeframe, first_date, last_date, row_count, last_synced_at, status, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timeframe) DO UPDATE SET
                    first_date=excluded.first_date,
                    last_date=excluded.last_date,
                    row_count=excluded.row_count,
                    last_synced_at=excluded.last_synced_at,
                    status=excluded.status,
                    source=excluded.source;
                """,
                records,
            )
            conn.commit()

        LOGGER.info("✔ Bootstrapped %d symbols into sync_ledger.", len(records))
        return len(records)

    def get_stale_symbols(
        self,
        symbols: list[str],
        target_date: str | date | None = None,
        timeframe: str = "1d",
    ) -> list[str]:
        """
        Return symbols that have missing or older data than target_date.
        Sub-millisecond filtering using SQLite index.
        """
        if not symbols:
            return []

        clean_syms = [s.strip().upper() for s in symbols]
        if target_date is None:
            target_str = get_latest_settled_trading_day().isoformat()
        elif isinstance(target_date, date):
            target_str = target_date.isoformat()
        else:
            target_str = str(target_date)[:10]

        with self._get_connection() as conn:
            cur = conn.cursor()
            # Symbols are up to date only if settled (status='OK') on or after target_date
            placeholders = ",".join(["?"] * len(clean_syms))
            query = f"""
                SELECT symbol FROM sync_ledger
                WHERE symbol IN ({placeholders})
                  AND timeframe = ?
                  AND last_date >= ?
                  AND status = 'OK'
            """
            cur.execute(query, (*clean_syms, timeframe, target_str))
            current_symbols = {row[0] for row in cur.fetchall()}

        # Stale symbols are those missing, older than target_date, or marked 'PROVISIONAL'
        stale = [s for s in clean_syms if s not in current_symbols]
        return stale

    def update_symbol(
        self,
        symbol: str,
        first_date: str | date | None,
        last_date: str | date | None,
        row_count: int,
        status: str = "OK",
        source: str = "yfinance",
        timeframe: str = "1d",
    ) -> None:
        """Atomic upsert for a single symbol upon sync completion."""
        sym = symbol.strip().upper()
        f_str = first_date.isoformat() if isinstance(first_date, date) else str(first_date or "")[:10]
        l_str = last_date.isoformat() if isinstance(last_date, date) else str(last_date or "")[:10]
        now_dt = datetime.now(IST)
        now_iso = now_dt.isoformat()

        # Tag today's midday bar as PROVISIONAL so evening/post-market sync replaces it with settled EOD
        today_str = now_dt.date().isoformat()
        if status == "OK" and l_str == today_str and not is_nse_market_settled(now_dt):
            status = "PROVISIONAL"

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sync_ledger (symbol, timeframe, first_date, last_date, row_count, last_synced_at, status, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timeframe) DO UPDATE SET
                    first_date=excluded.first_date,
                    last_date=excluded.last_date,
                    row_count=excluded.row_count,
                    last_synced_at=excluded.last_synced_at,
                    status=excluded.status,
                    source=excluded.source;
                """,
                (sym, timeframe, f_str, l_str, row_count, now_iso, status, source),
            )
            conn.commit()

    def log_etl_run(self, details: dict[str, Any]) -> None:
        """Append structured JSON audit log for ETL sync executions."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            **details,
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            LOGGER.warning("Could not append ETL log: %s", exc)

    def get_summary(self, timeframe: str | None = None) -> dict[str, Any]:
        """Return high-level status summary from ledger in ~2ms."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            tf_clause = "AND timeframe = ?" if timeframe else ""
            params = (timeframe,) if timeframe else ()

            cur.execute(f"SELECT COUNT(*), MIN(last_date), MAX(last_date) FROM sync_ledger WHERE status IN ('OK', 'PROVISIONAL') {tf_clause}", params)
            row = cur.fetchone()
            total_valid = row[0] if row else 0
            min_last = row[1] if row else None
            max_last = row[2] if row else None

            cur.execute(f"SELECT COUNT(*) FROM sync_ledger WHERE status = 'PROVISIONAL' {tf_clause}", params)
            provisional_count = cur.fetchone()[0]

            cur.execute(f"SELECT COUNT(*) FROM sync_ledger WHERE status NOT IN ('OK', 'PROVISIONAL') {tf_clause}", params)
            failed_count = cur.fetchone()[0]

            cur.execute("SELECT timeframe, COUNT(*) FROM sync_ledger GROUP BY timeframe")
            tf_counts = dict(cur.fetchall())

        return {
            "total_symbols": total_valid + failed_count,
            "healthy_count": total_valid - provisional_count,
            "provisional_count": provisional_count,
            "failed_count": failed_count,
            "latest_date": max_last,
            "oldest_last_date": min_last,
            "timeframe_counts": tf_counts,
        }
