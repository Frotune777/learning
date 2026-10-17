"""Index dimension and membership repository (dim_index, fact_index_membership)."""

from __future__ import annotations

from datetime import date
from typing import Any


class IndexRepo:
    """Access layer for index metadata and point-in-time constituent membership."""

    def __init__(self, conn: Any = None) -> None:
        self.conn = conn

    def get_index_constituents(self, index_code: str, as_of: date | None = None) -> list[str]:
        """Fetch index constituents as of a given date."""
        raise NotImplementedError

    def upsert_constituents(self, index_code: str, symbols: list[str], valid_from: date) -> int:
        """Record updated index constituent membership."""
        raise NotImplementedError
