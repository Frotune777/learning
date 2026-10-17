"""Data Access Layer (DAL) interface contract and concrete DuckDB implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


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
    def get_price_history(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
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


class DAL(DALInterface):
    """Concrete DuckDB-backed Data Access Layer."""

    def __init__(self, db_path: Path | str = "data/warehouse.duckdb") -> None:
        self.db_path = Path(db_path)

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Warehouse database not found at {self.db_path}")
        return duckdb.connect(str(self.db_path), read_only=True)

    def get_symbol(self, symbol: str, as_of: date | None = None) -> Any:
        raise NotImplementedError

    def get_active_universe(self) -> list[str]:
        with self._get_conn() as conn:
            query = (
                "SELECT symbol FROM dim_symbol "
                "WHERE is_active = TRUE AND is_current = TRUE ORDER BY symbol"
            )
            rows = conn.execute(query).fetchall()
            return [r[0] for r in rows]

    def get_inactive_universe(self) -> Any:
        raise NotImplementedError

    def get_enriched_symbol(self, symbol: str, as_of: date | None = None) -> dict[str, Any]:
        """Fetch combined symbol, price, and TA metrics for a symbol as of a date."""
        sym = symbol.strip().upper()
        with self._get_conn() as conn:
            if as_of is None:
                as_of_res = conn.execute(
                    "SELECT max(trade_date) FROM fact_price_daily WHERE symbol = ?", [sym]
                ).fetchone()
                if not as_of_res or as_of_res[0] is None:
                    return {}
                target_date = as_of_res[0]
            else:
                target_date = as_of

            query = """
            SELECT
                s.symbol, s.company_name, s.series, s.sector,
                p.trade_date, p.open, p.high, p.low, p.close, p.volume, p.vwap,
                ta.rsi_14, ta.ema_20, ta.ema_50, ta.ema_200, ta.adx_14, ta.atr_14
            FROM dim_symbol s
            LEFT JOIN fact_price_daily p
                ON s.symbol_sk = p.symbol_sk AND p.trade_date = ?
            LEFT JOIN fact_ta_daily ta
                ON s.symbol_sk = ta.symbol_sk AND ta.trade_date = ?
            WHERE s.symbol = ? AND s.is_current = TRUE
            """
            row = conn.execute(query, [target_date, target_date, sym]).fetchone()
            if not row:
                return {}
            cols = [d[0] for d in conn.description]
            return dict(zip(cols, row))

    def get_price_history(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """Fetch sorted daily OHLCV bar history between start_date and end_date."""
        sym = symbol.strip().upper()
        query = """
        SELECT
            symbol, trade_date, open, high, low, close, volume, turnover, trades, vwap
        FROM fact_price_daily
        WHERE symbol = ? AND trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date ASC
        """
        with self._get_conn() as conn:
            return conn.execute(query, [sym, start_date, end_date]).df()

    def get_latest_dq_run(self) -> dict[str, Any]:
        """Fetch the most recent data quality audit run summary."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM fact_dq_run ORDER BY run_timestamp DESC LIMIT 1"
            ).fetchone()
            if not row:
                return {}
            cols = [d[0] for d in conn.description]
            return dict(zip(cols, row))

    def get_latest_prices(self, trade_date: date) -> Any:
        raise NotImplementedError

    def get_ta_history(self, symbol: str, start_date: date, end_date: date) -> Any:
        raise NotImplementedError

    def get_delivery_history(self, symbol: str, lookback_days: int = 50) -> Any:
        raise NotImplementedError

    def get_active_signals(self, strategy_code: str | None = None) -> Any:
        raise NotImplementedError

    def get_dq_run_history(self, limit: int = 50) -> Any:
        raise NotImplementedError

    def get_corporate_actions(self, symbol: str | None = None) -> Any:
        raise NotImplementedError
