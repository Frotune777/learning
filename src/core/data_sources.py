"""
File: src/core/data_sources.py
Purpose: Centralized Data Source Registry and Switcher for Historical & Live Data.
Supports:
  - Fyers Broker REST API (Fast, reliable historical & live 1m/5m/1d candles, quotes)
  - NSE Bhavcopy / Archive (Official daily EOD settlements & delivery metrics)
  - Yahoo Finance (YFinance) (Free global/NSE fallback historical OHLCV)
  - NSE Chart Direct API (Direct nseindia.com chart data)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.config import UserPrefs
from src.data.fetcher.prices.base import AbstractPriceFetcher


@dataclass
class DataSourceSpec:
    id: str
    name: str
    category: str       # "broker", "exchange", "free"
    supports_historical: bool
    supports_live: bool
    requires_auth: bool
    description: str


DATA_SOURCES: dict[str, DataSourceSpec] = {
    "fyers": DataSourceSpec(
        id="fyers",
        name="Fyers API v3 (Broker)",
        category="broker",
        supports_historical=True,
        supports_live=True,
        requires_auth=True,
        description="Official Fyers broker REST API. High-speed, supports intraday + daily OHLCV and live market quotes.",
    ),
    "bhavcopy": DataSourceSpec(
        id="bhavcopy",
        name="NSE Daily Bhavcopy",
        category="exchange",
        supports_historical=True,
        supports_live=False,
        requires_auth=False,
        description="Official NSE End-of-Day Bhavcopy archives. Includes delivery volume and institutional turnover.",
    ),
    "yfinance": DataSourceSpec(
        id="yfinance",
        name="Yahoo Finance (yfinance)",
        category="free",
        supports_historical=True,
        supports_live=True,
        requires_auth=False,
        description="Free public historical data via Yahoo Finance. Works out of the box without any broker credentials.",
    ),
    "nse_charts": DataSourceSpec(
        id="nse_charts",
        name="NSE Website Chart API",
        category="exchange",
        supports_historical=True,
        supports_live=True,
        requires_auth=False,
        description="Direct web scraper from nseindia.com public chart endpoints.",
    ),
}


class DataSourceManager:
    """Manages active data sources and user configuration preferences."""

    PREF_KEY_HISTORICAL = "active_historical_source"
    PREF_KEY_LIVE = "active_live_source"

    def __init__(self) -> None:
        self.prefs = UserPrefs()

    @property
    def active_historical_source(self) -> str:
        # Default priority: Fyers if token/key present, otherwise Bhavcopy or yfinance
        default_src = "fyers" if (os.getenv("FYERS_API_KEY") or os.getenv("BROKER_API_KEY")) else "yfinance"
        return self.prefs.get_last(self.PREF_KEY_HISTORICAL, default_src)

    @active_historical_source.setter
    def active_historical_source(self, source_id: str) -> None:
        if source_id in DATA_SOURCES:
            self.prefs.set_last(self.PREF_KEY_HISTORICAL, source_id)

    @property
    def active_live_source(self) -> str:
        default_live = "fyers" if (os.getenv("FYERS_API_KEY") or os.getenv("BROKER_API_KEY")) else "yfinance"
        return self.prefs.get_last(self.PREF_KEY_LIVE, default_live)

    @active_live_source.setter
    def active_live_source(self, source_id: str) -> None:
        if source_id in DATA_SOURCES:
            self.prefs.set_last(self.PREF_KEY_LIVE, source_id)

    def get_price_fetcher(self, source_id: str | None = None) -> AbstractPriceFetcher:
        """Instantiate the active or requested price fetcher."""
        src = source_id or self.active_historical_source
        if src == "fyers":
            from src.nse_bhavcopy.fyers_fetcher import FyersFetcher
            return FyersFetcher()
        elif src == "yfinance":
            from src.data.fetcher.prices.yfinance_fetcher import YFinanceFetcher
            return YFinanceFetcher()
        elif src == "nse_charts":
            from src.data.fetcher.prices.nse_charts import NSEChartFetcher
            return NSEChartFetcher()
        else:
            # Fallback to FyersFetcher or YFinanceFetcher
            from src.data.fetcher.prices.yfinance_fetcher import YFinanceFetcher
            return YFinanceFetcher()

    def list_sources(self) -> dict[str, DataSourceSpec]:
        """Return all registered data sources."""
        return DATA_SOURCES

    def get_status_summary(self) -> dict[str, Any]:
        """Return connectivity & auth status for each available data source."""
        from src.nse_bhavcopy.fyers_fetcher import FyersFetcher
        fyers = FyersFetcher()
        fyers_has_token = bool(fyers.access_token)
        fyers_has_creds = bool(os.getenv("FYERS_API_KEY") or os.getenv("BROKER_API_KEY"))

        raw_dir = Path("data/raw")
        bhavcopy_files_count = len(list(raw_dir.glob("*.zip"))) + len(list(raw_dir.glob("*.csv"))) if raw_dir.exists() else 0

        hist_1d = Path("data/historical/1d")
        hist_count = len(list(hist_1d.glob("*.parquet"))) if hist_1d.exists() else 0

        return {
            "historical_active": self.active_historical_source,
            "live_active": self.active_live_source,
            "fyers": {
                "configured": fyers_has_creds,
                "authenticated": fyers_has_token,
            },
            "bhavcopy": {
                "archives_available": bhavcopy_files_count,
            },
            "parquet_cache": {
                "synced_symbols": hist_count,
            },
        }


_DATA_SOURCE_MANAGER_INSTANCE: DataSourceManager | None = None


def get_data_source_manager() -> DataSourceManager:
    """Return singleton instance of DataSourceManager."""
    global _DATA_SOURCE_MANAGER_INSTANCE
    if _DATA_SOURCE_MANAGER_INSTANCE is None:
        _DATA_SOURCE_MANAGER_INSTANCE = DataSourceManager()
    return _DATA_SOURCE_MANAGER_INSTANCE
