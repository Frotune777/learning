import json
import os
from pathlib import Path
from typing import Any, ClassVar


class Config:
    """Central configuration management."""

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
        return os.getenv("NSE_DATA_DIR", cls.DEFAULT_DATA_DIR)

    @classmethod
    def get_hist_dir(cls) -> str:
        return os.getenv("NSE_HIST_DIR", cls.DEFAULT_HIST_DIR)


# ---------------------------------------------------------------------------
# User Preferences Persistence
# ---------------------------------------------------------------------------


class UserPrefs:
    """Persistent user preferences across sessions."""

    def __init__(self):
        self.path = Path.home() / ".nse_pipeline_prefs.json"
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path) as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                return {}
        return {}

    def _save(self) -> None:
        try:
            with open(self.path, "w") as f:
                json.dump(self.data, f, indent=2)
        except OSError:
            pass

    def get_last(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set_last(self, key: str, value: Any) -> None:
        self.data[key] = value
        self._save()


import structlog


def setup_logging() -> None:
    """Configure structured logging."""
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


setup_logging()
logger = structlog.get_logger("nse_pipeline")
