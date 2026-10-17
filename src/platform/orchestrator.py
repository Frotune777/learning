"""Platform pipeline orchestrator."""

from __future__ import annotations

from datetime import date


class PlatformOrchestrator:
    """Orchestrates end-to-end ingestion, staging, and warehouse loading."""

    def __init__(self, data_root: str = "data") -> None:
        self.data_root = data_root

    def ingest(self, source: str, trade_date: date) -> str:
        """Download raw data into immutable landing layer and return batch_id."""
        raise NotImplementedError

    def stage(self, batch_id: str) -> str:
        """Validate and stage landed data into canonical Parquet tables."""
        raise NotImplementedError

    def load_warehouse(self, batch_id: str) -> None:
        """Atomically load staged data into DuckDB warehouse."""
        raise NotImplementedError
