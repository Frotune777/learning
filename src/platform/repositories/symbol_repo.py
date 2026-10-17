"""Symbol dimension repository (dim_symbol) supporting SCD Type 2."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb


class SymbolRepo:
    """Access layer and SCD Type 2 lifecycle manager for dim_symbol."""

    TRACKED_COLS = (
        "isin",
        "company_name",
        "series",
        "sector",
        "macro_sector",
        "is_active",
        "is_tradable",
        "listing_board",
    )

    def __init__(self, conn: Any = None, db_path: Path | str = "data/warehouse.duckdb") -> None:
        self.db_path = Path(db_path)
        self.conn = conn
        self._owned_conn = False

    def _ensure_conn(self) -> duckdb.DuckDBPyConnection:
        if self.conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = duckdb.connect(str(self.db_path))
            self._owned_conn = True
        return self.conn

    def _close_conn(self) -> None:
        if self._owned_conn and self.conn is not None:
            self.conn.close()
            self.conn = None
            self._owned_conn = False

    def compute_record_hash(self, record: dict[str, Any]) -> str:
        """Compute MD5 checksum for SCD2 tracked attributes."""
        payload = [str(record.get(col, "") or "") for col in self.TRACKED_COLS]
        return hashlib.md5("|".join(payload).encode("utf-8")).hexdigest()

    def get_symbol(self, symbol: str, as_of: date | None = None) -> dict[str, Any] | None:
        """Fetch current or point-in-time symbol record."""
        conn = self._ensure_conn()
        sym = symbol.strip().upper()
        if as_of is None:
            query = "SELECT * FROM dim_symbol WHERE symbol = ? AND is_current = TRUE"
            row = conn.execute(query, [sym]).fetchone()
        else:
            query = (
                "SELECT * FROM dim_symbol "
                "WHERE symbol = ? AND valid_from <= ? AND valid_to >= ? "
                "ORDER BY valid_from DESC LIMIT 1"
            )
            row = conn.execute(query, [sym, as_of, as_of]).fetchone()

        if not row:
            return None
        cols = [desc[0] for desc in conn.description]
        return dict(zip(cols, row))

    def get_active_universe(self) -> list[str]:
        """Fetch all currently active tradable symbols."""
        conn = self._ensure_conn()
        query = (
            "SELECT symbol FROM dim_symbol "
            "WHERE is_current = TRUE AND is_active = TRUE AND is_tradable = TRUE "
            "ORDER BY symbol"
        )
        rows = conn.execute(query).fetchall()
        return [r[0] for r in rows]

    def get_inactive_universe(self) -> list[str]:
        """Fetch all inactive or delisted symbols."""
        conn = self._ensure_conn()
        query = "SELECT DISTINCT symbol FROM dim_symbol WHERE is_active = FALSE ORDER BY symbol"
        rows = conn.execute(query).fetchall()
        return [r[0] for r in rows]

    def upsert_scd2(
        self,
        records: list[dict[str, Any]],
        effective_date: date | None = None,
    ) -> dict[str, int]:
        """Apply SCD2 upsert semantics for incoming symbol records."""
        conn = self._ensure_conn()
        eff_date = effective_date or date.today()
        yesterday = eff_date - timedelta(days=1)

        counts = {"inserted": 0, "updated": 0, "unchanged": 0}

        # Cache current rows: symbol -> row dict
        current_rows = conn.execute(
            """
            SELECT symbol_sk, symbol, isin, company_name, series, sector,
                   macro_sector, is_active, is_tradable, listing_board, valid_from
            FROM dim_symbol
            WHERE is_current = TRUE
            """
        ).fetchall()
        cols = [
            "symbol_sk", "symbol", "isin", "company_name", "series", "sector",
            "macro_sector", "is_active", "is_tradable", "listing_board", "valid_from"
        ]
        curr_map: dict[str, dict[str, Any]] = {
            r[1]: dict(zip(cols, r)) for r in current_rows
        }

        inserts: list[tuple[Any, ...]] = []
        updates_to_close: list[tuple[Any, ...]] = []

        for rec in records:
            sym = str(rec.get("symbol", "")).strip().upper()
            if not sym:
                continue

            isin = (rec.get("isin") or "").strip() or None
            company_name = str(rec.get("company_name") or sym).strip()
            series = str(rec.get("series") or "EQ").strip().upper()
            sector = rec.get("sector")
            macro_sector = rec.get("macro_sector")
            is_active = bool(rec.get("is_active", True))
            classification = str(rec.get("classification") or "HEALTHY")
            delisting_date = rec.get("delisting_date")

            # Determine tradability & listing board
            is_tradable = bool(series in ("EQ", "BE", "BZ") and is_active)
            listing_board = "SME" if series == "SM" else "Main"

            incoming_dict = {
                "isin": isin,
                "company_name": company_name,
                "series": series,
                "sector": sector,
                "macro_sector": macro_sector,
                "is_active": is_active,
                "is_tradable": is_tradable,
                "listing_board": listing_board,
            }
            inc_hash = self.compute_record_hash(incoming_dict)

            existing = curr_map.get(sym)
            if existing is None:
                # Brand new symbol
                v_from = rec.get("valid_from") or date(2000, 1, 1)
                v_to = rec.get("valid_to") or date(9999, 12, 31)
                is_curr = bool(rec.get("is_current", is_active))

                inserts.append((
                    sym, isin, company_name, series, sector, macro_sector,
                    is_active, classification, v_from, v_to, is_curr,
                    is_tradable, listing_board, delisting_date,
                ))
                counts["inserted"] += 1
            else:
                existing_hash = self.compute_record_hash(existing)
                # If existing ISIN was null and incoming has ISIN, or attributes changed
                if existing_hash != inc_hash or (existing["isin"] is None and isin is not None):
                    # Close old record
                    updates_to_close.append((yesterday, existing["symbol_sk"]))
                    # Insert new active record
                    inserts.append((
                        sym, isin or existing["isin"], company_name, series,
                        sector or existing["sector"], macro_sector or existing["macro_sector"],
                        is_active, classification, eff_date, date(9999, 12, 31),
                        is_active, is_tradable, listing_board, delisting_date,
                    ))
                    counts["updated"] += 1
                else:
                    counts["unchanged"] += 1

        if updates_to_close:
            conn.execute("DROP INDEX IF EXISTS idx_dim_symbol_lookup")
            conn.execute("DROP INDEX IF EXISTS idx_dim_symbol_tradable")
            conn.executemany(
                "UPDATE dim_symbol SET valid_to = ?, is_current = FALSE WHERE symbol_sk = ?",
                updates_to_close,
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_dim_symbol_lookup ON dim_symbol(symbol, is_current)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_dim_symbol_tradable "
                "ON dim_symbol(is_current, is_tradable)"
            )

        if inserts:
            conn.executemany(
                """
                INSERT INTO dim_symbol (
                    symbol_sk, symbol, isin, company_name, series, sector, macro_sector,
                    is_active, classification, valid_from, valid_to, is_current,
                    is_tradable, listing_board, delisting_date
                ) VALUES (nextval('seq_symbol_sk'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                inserts,
            )

        return counts
