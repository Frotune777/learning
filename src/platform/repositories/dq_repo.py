"""Data Quality Gate audit runs repository (fact_dq_run)."""

from __future__ import annotations

from typing import Any


class DQRepo:
    """Access layer for fact_dq_run audit log."""

    def __init__(self, conn: Any = None) -> None:
        self.conn = conn

    def record_run(self, run_summary: dict[str, Any]) -> str:
        """Record DQ gate execution metrics and halt status."""
        raise NotImplementedError

    def get_history(self, limit: int = 50) -> Any:
        """Fetch past data quality audit run records."""
        raise NotImplementedError
