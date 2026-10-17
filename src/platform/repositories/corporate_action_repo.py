"""Corporate actions repository (corporate_actions)."""

from __future__ import annotations

from typing import Any


class CorporateActionRepo:
    """Access layer for detected and confirmed corporate actions."""

    def __init__(self, conn: Any = None) -> None:
        self.conn = conn

    def get_corporate_actions(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Fetch corporate splits, bonuses, and adjustment factors."""
        raise NotImplementedError

    def record_actions(self, actions: list[dict[str, Any]]) -> int:
        """Persist newly detected corporate actions."""
        raise NotImplementedError
