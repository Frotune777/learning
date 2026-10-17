"""Unit tests for DALInterface abstract contract."""

from datetime import date
from typing import Any

import pytest

from src.platform.dal import DALInterface


def test_dal_interface_cannot_be_instantiated_directly() -> None:
    """Verify DALInterface is an abstract base class."""
    with pytest.raises(TypeError):
        DALInterface()  # type: ignore[abstract]


def test_dal_interface_concrete_implementation() -> None:
    """Verify concrete subclass can satisfy contract."""

    class ConcreteDAL(DALInterface):
        def get_symbol(self, symbol: str, as_of: date | None = None) -> Any:
            return {"symbol": symbol}

        def get_active_universe(self) -> list[str]:
            return ["TCS", "RELIANCE"]

        def get_inactive_universe(self) -> Any:
            return []

        def get_price_history(self, symbol: str, start_date: date, end_date: date) -> Any:
            return []

        def get_latest_prices(self, trade_date: date) -> Any:
            return []

        def get_ta_history(self, symbol: str, start_date: date, end_date: date) -> Any:
            return []

        def get_delivery_history(self, symbol: str, lookback_days: int = 50) -> Any:
            return []

        def get_active_signals(self, strategy_code: str | None = None) -> Any:
            return []

        def get_dq_run_history(self, limit: int = 50) -> Any:
            return []

        def get_corporate_actions(self, symbol: str | None = None) -> Any:
            return []

    dal = ConcreteDAL()
    assert dal.get_active_universe() == ["TCS", "RELIANCE"]
    assert dal.get_symbol("TCS") == {"symbol": "TCS"}
