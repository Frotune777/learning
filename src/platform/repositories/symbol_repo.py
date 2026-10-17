"""Symbol dimension repository (dim_symbol)."""

from __future__ import annotations

from datetime import date
from typing import Any


class SymbolRepo:
    """Access layer for dim_symbol SCD Type 2 dimension."""

    def __init__(self, conn: Any = None) -> None:
        self.conn = conn

    def get_symbol(self, symbol: str, as_of: date | None = None) -> Any:
        """Fetch current or point-in-time symbol record."""
        raise NotImplementedError

    def get_active_universe(self) -> list[str]:
        """Fetch all active EQ equity symbols."""
        raise NotImplementedError

    def get_inactive_universe(self) -> Any:
        """Fetch all inactive or delisted symbols."""
        raise NotImplementedError

    def upsert_symbol(self, record: dict[str, Any]) -> None:
        """Insert or apply SCD2 transition for symbol record."""
        raise NotImplementedError
