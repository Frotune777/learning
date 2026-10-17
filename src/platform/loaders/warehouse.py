"""Warehouse layer loader for transactional ingestion into DuckDB."""

from __future__ import annotations

from pathlib import Path


class WarehouseLoader:
    """Loads validated staging Parquets into DuckDB warehouse."""

    def __init__(self, db_path: Path | str = "data/warehouse.duckdb") -> None:
        self.db_path = Path(db_path)

    def load_staged(self, batch_id: str, target_table: str) -> int:
        """Atomically upsert staged Parquet rows into DuckDB target table."""
        raise NotImplementedError

    def acquire_lock(self) -> None:
        """Acquire process-level mutual exclusion lock."""
        raise NotImplementedError

    def release_lock(self) -> None:
        """Release process-level mutual exclusion lock."""
        raise NotImplementedError
