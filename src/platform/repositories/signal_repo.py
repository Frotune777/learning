"""Strategy and SMC signals fact repository (fact_signal_daily)."""

from __future__ import annotations

from typing import Any


class SignalRepo:
    """Access layer for fact_signal_daily."""

    def __init__(self, conn: Any = None) -> None:
        self.conn = conn

    def get_active_signals(self, strategy_code: str | None = None) -> Any:
        """Fetch active strategy recommendations."""
        raise NotImplementedError

    def insert_signals(self, batch_id: str, signals: list[dict[str, Any]]) -> int:
        """Insert newly generated strategy signal records."""
        raise NotImplementedError

    def update_signal_status(
        self, signal_id: int, new_status: str, exit_price: float | None = None
    ) -> None:
        """Update lifecycle status of an existing signal."""
        raise NotImplementedError
