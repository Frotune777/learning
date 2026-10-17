"""Delivery position fact repository (fact_delivery_daily)."""

from __future__ import annotations

from typing import Any


class DeliveryRepo:
    """Access layer for fact_delivery_daily."""

    def __init__(self, conn: Any = None) -> None:
        self.conn = conn

    def get_delivery_history(self, symbol: str, lookback_days: int = 50) -> Any:
        """Fetch delivery quantity and percentage history for a symbol."""
        raise NotImplementedError

    def upsert_delivery(self, batch_id: str, records: Any) -> int:
        """Upsert daily settlement delivery records."""
        raise NotImplementedError
