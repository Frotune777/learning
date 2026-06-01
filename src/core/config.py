"""
File: src/core/config.py
Purpose: Centralized application configuration, user preferences, and logging setup.
Last Modified: 2026-05-31
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, ClassVar

import structlog


class Config:
    """
    Central configuration management for the NSE pipeline.

    Attributes:
        DEFAULT_DATA_DIR (str): Root data directory. | "data"
        DEFAULT_HIST_DIR (str): Historical Parquet storage path. | "data/historical"
        DEFAULT_START_DATE (str): Default sync start date. | "2000-01-01"
        DEFAULT_TIMEFRAME (str): Default OHLCV timeframe. | "1d"
        SYNC_DEFAULTS (dict): Sync operation defaults.
        DISPLAY_LIMITS (dict): CLI table display limits.
        TECH_THRESHOLDS (dict): RSI/ADX/CCI threshold constants.

    Public Methods:
        - get_data_dir(): Return data dir from env or default.
        - get_hist_dir(): Return hist dir from env or default.

    Thread Safety: Yes — class attributes are read-only.
    """

    # Default paths
    DEFAULT_DATA_DIR: str = "data"
    DEFAULT_HIST_DIR: str = "data/historical"
    DEFAULT_MASTER_DIR: str = "data"
    DEFAULT_START_DATE: str = "2000-01-01"
    DEFAULT_TIMEFRAME: str = "1d"

    # Sync defaults
    SYNC_DEFAULTS: ClassVar[dict[str, Any]] = {
        "max_pairs": 50,
        "default_symbol_limit": 100,
        "max_pval_threshold": 0.05,
        "default_days_back": 10,
        "rate_delay": 0.5,
        "default_delay": 1.0,
    }

    # Display limits
    DISPLAY_LIMITS: ClassVar[dict[str, int]] = {
        "symbol_preview": 15,
        "top_synced": 10,
        "heatmap_preview": 25,
        "max_failed_display": 15,
    }

    # Technical thresholds
    TECH_THRESHOLDS: ClassVar[dict[str, int]] = {
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "adx_trending": 25,
        "cci_overbought": 100,
        "cci_oversold": -100,
    }

    @classmethod
    def get_data_dir(cls) -> str:
        """Return data directory from NSE_DATA_DIR env var or default."""
        return os.getenv("NSE_DATA_DIR", cls.DEFAULT_DATA_DIR)

    @classmethod
    def get_hist_dir(cls) -> str:
        """Return historical directory from NSE_HIST_DIR env var or default."""
        return os.getenv("NSE_HIST_DIR", cls.DEFAULT_HIST_DIR)


# ---------------------------------------------------------------------------
# Screener strategies declarative configuration
# ---------------------------------------------------------------------------

SCREENER_STRATEGIES: list[dict[str, str]] = [
    {
        "name": "Nifty Shop (Single Leg)",
        "file_prefix": "strategy_nifty_shop",
        "description": (
            "RSI laddering strategy for mean reversion. "
            "Level 1 (RSI < 35), Level 2 (< 30), Level 3 (< 25). "
            "Targets 6.28% profit."
        ),
        "category": "momentum",
    },
    {
        "name": "Buy Low Sell High",
        "file_prefix": "strategy_buy_low",
        "description": (
            "Demand level accumulation. Triggers when CMP is within "
            "2.0% of the 200-Day Low."
        ),
        "category": "mean_reversion",
    },
    {
        "name": "Turtle Trading",
        "file_prefix": "strategy_turtle",
        "description": (
            "Explosive momentum breakout. Triggers a 'Buy' only when CMP "
            "forcefully crosses the previous 55-Day High."
        ),
        "category": "breakout",
    },
    {
        "name": "RDX Indicator",
        "file_prefix": "strategy_rdx",
        "description": (
            "Strict momentum screener. Requires ADX > 25, bullish DI "
            "crossover, and RSI > 60."
        ),
        "category": "momentum",
    },
    {
        "name": "100 SMA Breakout",
        "file_prefix": "strategy_100sma_breakout",
        "description": (
            "Institutional 6-month base breakout. Triggers crossing 100 SMA "
            "while trading > 20% above 6-month lows."
        ),
        "category": "breakout",
    },
    {
        "name": "ETF Shop Method",
        "file_prefix": "strategy_etf_shop",
        "description": (
            "Index fund retracement variant. Triggers a 'Buy' if the ETF "
            "falls more than 2.0% below its 20 DMA."
        ),
        "category": "etf",
    },
    {
        "name": "Super BO Stocks",
        "file_prefix": "strategy_super_bo",
        "description": (
            "Recovery strategy. Stocks rising from downtrends facing 200 SMA "
            "resistance while above 50, 100, 150 SMAs."
        ),
        "category": "recovery",
    },
    {
        "name": "DMADMA (Reverse)",
        "file_prefix": "strategy_dmadma_reverse",
        "description": (
            "Bull market continuation. Triggers on a 150 SMA breakout while "
            "the stock remains above the 200 SMA."
        ),
        "category": "trend",
    },
    {
        "name": "DMADMA (No SL)",
        "file_prefix": "strategy_dmadma_no_sl",
        "description": (
            "Pure momentum following — no stop loss. Golden cross analog "
            "where the 50 SMA rises above the 200 SMA."
        ),
        "category": "trend",
    },
]


# ---------------------------------------------------------------------------
# User Preferences Persistence
# ---------------------------------------------------------------------------


class UserPrefs:
    """
    Persistent user preferences stored as JSON across CLI sessions.

    Attributes:
        path (Path): Path to preferences JSON file. | ~/.nse_pipeline_prefs.json
        data (dict): Loaded preferences dictionary. | {}

    Public Methods:
        - get_last(key, default): Retrieve a saved preference value.
        - set_last(key, value): Save a preference value.

    Thread Safety: No — single-user CLI tool.
    """

    def __init__(self) -> None:
        """Initialize UserPrefs by loading the JSON preferences file."""
        self.path: Path = Path.home() / ".nse_pipeline_prefs.json"
        self.data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        """Load preferences from JSON file, returning empty dict on failure."""
        if self.path.exists():
            try:
                with open(self.path) as f:
                    return json.load(f)  # type: ignore[no-any-return]
            except (OSError, json.JSONDecodeError):
                return {}
        return {}

    def _save(self) -> None:
        """Persist current preferences to JSON file."""
        try:
            with open(self.path, "w") as f:
                json.dump(self.data, f, indent=2)
        except OSError:
            pass

    def get_last(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a stored preference value by key.

        Parameters:
            key (str): Preference key. | Non-empty string.
            default (Any): Return value if key not found. | None.

        Returns:
            Any: Stored value or default.

        Complexity:
            Time: O(1)
            Space: O(1)

        Example:
            >>> prefs = UserPrefs()
            >>> prefs.get_last("last_symbol", "TCS")
            'TCS'
        """
        return self.data.get(key, default)

    def set_last(self, key: str, value: Any) -> None:
        """
        Store a preference value and persist to disk.

        Parameters:
            key (str): Preference key. | Non-empty string.
            value (Any): Value to store. | JSON-serializable.

        Returns:
            None

        Complexity:
            Time: O(1)
            Space: O(1)

        Example:
            >>> prefs = UserPrefs()
            >>> prefs.set_last("last_symbol", "RELIANCE")
        """
        self.data[key] = value
        self._save()


# ---------------------------------------------------------------------------
# Structured Logging Setup
# ---------------------------------------------------------------------------


def setup_logging() -> None:
    """
    Configure structlog with console renderer for the NSE pipeline.

    Returns:
        None

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> setup_logging()
    """
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
