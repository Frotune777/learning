import json
import logging
import os
import sys
from collections.abc import Callable
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, ClassVar

import structlog
from tqdm import tqdm

from src.cli.formatters import (
    dim,
)

logger = logging.getLogger("nse_pipeline")

# ---------------------------------------------------------------------------
# Constants & Configuration
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Structured Logging Setup
# ---------------------------------------------------------------------------


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

# Basic logging fallback
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
_USE_COLOR = sys.stdout.isatty()


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


def validate_symbol(func: Callable) -> Callable:
    """Validate stock symbol input."""

    @wraps(func)
    def wrapper(symbol: str, *args, **kwargs):
        if not symbol or not symbol.replace(".", "").replace("^", "").isalnum():
            raise ValueError(f"Invalid symbol format: {symbol}")
        return func(symbol.upper(), *args, **kwargs)

    return wrapper


def with_progress_bar(description: str = "Processing"):
    """Add progress bar to iterator functions."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if isinstance(result, list | dict) and len(result) > 0:
                yield from tqdm(result, desc=description)
            else:
                yield from result

        return wrapper

    return decorator


def dry_run_capable(func: Callable) -> Callable:
    """Add dry-run capability to functions."""

    @wraps(func)
    def wrapper(*args, dry_run: bool = False, **kwargs):
        if dry_run:
            logger.info("dry_run_mode", function=func.__name__)
            print(f"\n  {dim('[DRY RUN] Would execute:')} {func.__name__}")
            return None
        return func(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Cached API Clients
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_nse_utils():
    """Get cached NseUtils instance."""
    from src.nse_live.nse_utils import NseUtils

    return NseUtils()


@lru_cache(maxsize=1)
def get_fyers_fetcher():
    """Get cached FyersFetcher instance."""
    from src.nse_bhavcopy.fyers_fetcher import FyersFetcher

    return FyersFetcher()


import pandas as pd


def combine_strings(values):
    """Helper for aggregating string values in grouped data."""
    return " | ".join(str(v) for v in values if pd.notna(v))
