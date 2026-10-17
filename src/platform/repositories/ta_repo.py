"""Technical indicators fact repository (fact_ta_daily)."""

from __future__ import annotations

from datetime import date
from typing import Any


class TARepo:
    """Access layer for fact_ta_daily."""

    def __init__(self, conn: Any = None) -> None:
        self.conn = conn

    def get_ta_history(self, symbol: str, start_date: date, end_date: date) -> Any:
        """Fetch computed indicators for a symbol within date bounds."""
        raise NotImplementedError

    def upsert_ta(self, batch_id: str, records: Any) -> int:
        """Upsert computed technical indicator records."""
        raise NotImplementedError
