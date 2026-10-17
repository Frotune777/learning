"""Daily price fact repository (fact_price_daily)."""

from __future__ import annotations

from datetime import date
from typing import Any


class PriceRepo:
    """Access layer for fact_price_daily."""

    def __init__(self, conn: Any = None) -> None:
        self.conn = conn

    def get_price_history(self, symbol: str, start_date: date, end_date: date) -> Any:
        """Fetch daily OHLCV bar history for a symbol."""
        raise NotImplementedError

    def get_latest_prices(self, trade_date: date) -> Any:
        """Fetch cross-sectional snapshot for all symbols on trade_date."""
        raise NotImplementedError

    def upsert_prices(self, batch_id: str, records: Any) -> int:
        """Upsert staged price records into fact_price_daily."""
        raise NotImplementedError
