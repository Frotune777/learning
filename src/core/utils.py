"""
File: src/core/utils.py
Purpose: Cached API client factories and shared string aggregation helpers.
Last Modified: 2026-05-31
"""

import logging
from functools import lru_cache

import pandas as pd

# Re-export canonical items so existing importers don't break
from src.core.config import Config, UserPrefs, setup_logging
from src.core.decorators import (
    dry_run_capable,
    validate_symbol,
    with_progress_bar,
)

logger = logging.getLogger("nse_pipeline")


# ---------------------------------------------------------------------------
# Cached API Clients
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_nse_utils() -> object:
    """
    Return a cached NseUtils instance (created once per process).

    Returns:
        NseUtils: Singleton NSE live data utility object.

    Complexity:
        Time: O(1) after first call (cached)
        Space: O(1)

    Example:
        >>> nse = get_nse_utils()
    """
    from src.nse_live.nse_utils import NseUtils

    return NseUtils()


@lru_cache(maxsize=1)
def get_fyers_fetcher() -> object:
    """
    Return a cached FyersFetcher instance (created once per process).

    Returns:
        FyersFetcher: Singleton Fyers API data fetcher.

    Complexity:
        Time: O(1) after first call (cached)
        Space: O(1)

    Example:
        >>> fetcher = get_fyers_fetcher()
    """
    from src.nse_bhavcopy.fyers_fetcher import FyersFetcher

    return FyersFetcher()


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def combine_strings(values: object) -> str:
    """
    Join non-null string values with ' | ' separator for grouped DataFrame aggregation.

    Parameters:
        values (object): Iterable of values (may include NaN). | Any iterable.

    Returns:
        str: ' | ' separated string of non-null values.

    Complexity:
        Time: O(N)
        Space: O(N)

    Example:
        >>> combine_strings(["Buy", None, "Sell"])
        'Buy | Sell'
    """
    return " | ".join(str(v) for v in values if pd.notna(v))


__all__ = [
    "Config",
    "UserPrefs",
    "combine_strings",
    "dry_run_capable",
    "get_fyers_fetcher",
    "get_nse_utils",
    "setup_logging",
    "validate_symbol",
    "with_progress_bar",
]
