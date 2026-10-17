"""Data Access Layer (DAL) interface contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any


class DALInterface(ABC):
    """Abstract Data Access Layer specifying all entity queries."""

    @abstractmethod
    def get_symbol(self, symbol: str, as_of: date | None = None) -> Any:
        """Retrieve current or point-in-time symbol metadata."""
        raise NotImplementedError

    @abstractmethod
    def get_active_universe(self) -> list[str]:
        """Retrieve all currently active equity symbols."""
        raise NotImplementedError

    @abstractmethod
    def get_inactive_universe(self) -> Any:
        """Retrieve inactive or delisted symbols with classification."""
        raise NotImplementedError

    @abstractmethod
    def get_price_history(self, symbol: str, start_date: date, end_date: date) -> Any:
        """Retrieve sorted time series with OHLCV data."""
        raise NotImplementedError

    @abstractmethod
    def get_latest_prices(self, trade_date: date) -> Any:
        """Retrieve cross-sectional price snapshot for a date."""
        raise NotImplementedError

    @abstractmethod
    def get_ta_history(self, symbol: str, start_date: date, end_date: date) -> Any:
        """Retrieve computed technical indicators."""
        raise NotImplementedError

    @abstractmethod
    def get_delivery_history(self, symbol: str, lookback_days: int = 50) -> Any:
        """Retrieve delivery statistics history."""
        raise NotImplementedError

    @abstractmethod
    def get_active_signals(self, strategy_code: str | None = None) -> Any:
        """Retrieve active strategy and SMC signals."""
        raise NotImplementedError

    @abstractmethod
    def get_dq_run_history(self, limit: int = 50) -> Any:
        """Retrieve audit log of data quality gate runs."""
        raise NotImplementedError

    @abstractmethod
    def get_corporate_actions(self, symbol: str | None = None) -> Any:
        """Retrieve detected or confirmed corporate actions."""
        raise NotImplementedError
