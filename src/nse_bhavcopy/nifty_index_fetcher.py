"""
File: src/nse_bhavcopy/nifty_index_fetcher.py
Purpose: Fetch and cache NSE index constituent lists for Nifty 50/Next50/100/250.
Last Modified: 2026-05-29
"""

import json
import logging
import os
import time
from typing import Any

import requests

LOGGER: logging.Logger = logging.getLogger(__name__)

# NSE equity index API endpoint
_NSE_INDEX_URL = "https://www.nseindia.com/api/equity-stockIndices?index={index}"
_NSE_HOME = "https://www.nseindia.com"

# Default cache directory and TTL (7 days — indices change quarterly)
_DEFAULT_CACHE_DIR = "data/indices"
_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60

# Map human-readable names to NSE API index identifiers
_INDEX_MAP: dict[str, str] = {
    "nifty50": "NIFTY%2050",
    "nifty_next50": "NIFTY%20NEXT%2050",
    "nifty100": "NIFTY%20100",
    "nifty200": "NIFTY%20200",
    "nifty250": "NIFTY%20MIDCAP%20SELECT",  # Proxy; update if NSE exposes 250
}

_REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

# Request timeout in seconds
_REQUEST_TIMEOUT: int = 30


def _cache_path(index_key: str, cache_dir: str) -> str:
    """
    Return the absolute path for a cached index JSON file.

    Parameters:
        index_key (str): Short key such as 'nifty50'. | Non-empty string.
        cache_dir (str): Directory to store JSON files. | Valid path.

    Returns:
        str: Absolute path to the cache file.

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> _cache_path("nifty50", "data/indices")
        'data/indices/nifty50.json'
    """
    return os.path.join(cache_dir, f"{index_key}.json")


def _is_cache_valid(path: str) -> bool:
    """
    Return True when a cache file exists and was written within the TTL window.

    Parameters:
        path (str): Absolute or relative path to the cache file. | Existing file.

    Returns:
        bool: True if cache is fresh, False otherwise.

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> _is_cache_valid("/tmp/nifty50.json")
        False
    """
    if not os.path.isfile(path):
        return False
    age = time.time() - os.path.getmtime(path)
    return age < _CACHE_TTL_SECONDS


def _load_cache(path: str) -> list[str]:
    """
    Load a list of symbols from a JSON cache file.

    Parameters:
        path (str): Path to the JSON file. | Must exist and be valid JSON.

    Returns:
        list[str]: List of NSE symbol strings.

    Raises:
        ValueError: If the JSON file does not contain a list.

    Complexity:
        Time: O(N) where N = number of symbols
        Space: O(N)

    Example:
        >>> _load_cache("data/indices/nifty50.json")
        ['RELIANCE', 'TCS', ...]
    """
    with open(path, encoding="utf-8") as fh:
        data: Any = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Cache file {path} does not contain a list.")
    return [str(s) for s in data]


def _save_cache(path: str, symbols: list[str]) -> None:
    """
    Persist a list of symbols to a JSON cache file.

    Parameters:
        path (str): Destination file path. | Parent directory must exist.
        symbols (list[str]): NSE symbols to persist. | Non-empty list.

    Returns:
        None: Writes file as side-effect.

    Complexity:
        Time: O(N)
        Space: O(N)

    Example:
        >>> _save_cache("data/indices/nifty50.json", ["RELIANCE", "TCS"])
    """
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(symbols, fh)


def _fetch_from_nse(index_key: str) -> list[str]:
    """
    Fetch constituent symbols from the NSE equity index API.

    Uses a two-step session: first load NSE homepage to acquire cookies,
    then call the index API. Returns an empty list on any network failure
    so callers can fall back to cached data.

    Parameters:
        index_key (str): Key from _INDEX_MAP. | Must exist in _INDEX_MAP.

    Returns:
        list[str]: Sorted list of NSE symbol strings, or [] on failure.

    Raises:
        KeyError: If index_key is not in _INDEX_MAP.

    Complexity:
        Time: O(N) — two HTTP round trips + JSON parse
        Space: O(N)

    Example:
        >>> symbols = _fetch_from_nse("nifty50")
        >>> len(symbols) >= 50
        True
    """
    nse_id = _INDEX_MAP[index_key]
    url = _NSE_INDEX_URL.format(index=nse_id)

    session = requests.Session()
    session.headers.update(_REQUEST_HEADERS)

    try:
        # Step 1: Prime session cookies
        session.get(_NSE_HOME, timeout=_REQUEST_TIMEOUT)
        time.sleep(0.5)

        # Step 2: Fetch index data
        resp = session.get(url, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        payload: Any = resp.json()

        data_key = "data"
        if not isinstance(payload, dict) or data_key not in payload:
            LOGGER.warning("Unexpected NSE API response structure for %s", index_key)
            return []

        rows: Any = payload[data_key]
        symbols: list[str] = []
        for row in rows:
            if isinstance(row, dict) and "symbol" in row:
                sym = str(row["symbol"]).strip().upper()
                if sym:
                    symbols.append(sym)

        LOGGER.info(
            "Fetched %d symbols for index '%s' from NSE API.",
            len(symbols),
            index_key,
        )
        return sorted(symbols)

    except requests.RequestException as exc:
        LOGGER.error("NSE API request failed for index '%s': %s", index_key, exc)
        return []


def get_index_symbols(
    index_key: str,
    cache_dir: str = _DEFAULT_CACHE_DIR,
    force_refresh: bool = False,
) -> list[str]:
    """
    Return NSE constituent symbols for a given index, using a file cache.

    Falls back to stale cache if a fresh network fetch fails. Returns []
    only when neither cache nor network is available.

    Parameters:
        index_key (str): One of 'nifty50', 'nifty_next50', 'nifty100',
            'nifty200', 'nifty250'. | Must be in _INDEX_MAP.
        cache_dir (str): Directory for JSON cache files. | Writable path.
        force_refresh (bool): Skip cache and always fetch from network.
            | Default: False.

    Returns:
        list[str]: Sorted list of NSE symbol strings.

    Raises:
        KeyError: If index_key is not supported.

    Complexity:
        Time: O(N) for cache hit; O(N + 2 HTTP) for network fetch
        Space: O(N)

    Example:
        >>> syms = get_index_symbols("nifty50")
        >>> "RELIANCE" in syms
        True
    """
    if index_key not in _INDEX_MAP:
        raise KeyError(
            f"Unsupported index key '{index_key}'. "
            f"Valid options: {list(_INDEX_MAP.keys())}"
        )

    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(index_key, cache_dir)

    # Serve from cache when fresh
    if not force_refresh and _is_cache_valid(path):
        LOGGER.debug("Serving '%s' from cache: %s", index_key, path)
        try:
            return _load_cache(path)
        except (ValueError, json.JSONDecodeError) as exc:
            LOGGER.warning("Cache load failed for %s: %s", index_key, exc)

    # Fetch from NSE
    symbols = _fetch_from_nse(index_key)

    if symbols:
        _save_cache(path, symbols)
        return symbols

    # Fallback: stale cache is better than nothing
    if os.path.isfile(path):
        LOGGER.warning("Network fetch failed; serving stale cache for '%s'.", index_key)
        try:
            return _load_cache(path)
        except (ValueError, json.JSONDecodeError):
            pass

    LOGGER.error("No data available for index '%s'.", index_key)
    return []


def get_nifty50(
    cache_dir: str = _DEFAULT_CACHE_DIR,
    force_refresh: bool = False,
) -> list[str]:
    """
    Return Nifty 50 constituent symbols.

    Parameters:
        cache_dir (str): Cache directory. | Default: 'data/indices'.
        force_refresh (bool): Bypass cache. | Default: False.

    Returns:
        list[str]: Sorted list of up to 50 NSE symbols.

    Complexity:
        Time: O(N)  Space: O(N)

    Example:
        >>> symbols = get_nifty50()
        >>> len(symbols) > 0
        True
    """
    return get_index_symbols("nifty50", cache_dir, force_refresh)


def get_nifty_next50(
    cache_dir: str = _DEFAULT_CACHE_DIR,
    force_refresh: bool = False,
) -> list[str]:
    """
    Return Nifty Next 50 constituent symbols.

    Parameters:
        cache_dir (str): Cache directory. | Default: 'data/indices'.
        force_refresh (bool): Bypass cache. | Default: False.

    Returns:
        list[str]: Sorted list of up to 50 NSE symbols.

    Complexity:
        Time: O(N)  Space: O(N)

    Example:
        >>> symbols = get_nifty_next50()
        >>> len(symbols) > 0
        True
    """
    return get_index_symbols("nifty_next50", cache_dir, force_refresh)


def get_nifty100(
    cache_dir: str = _DEFAULT_CACHE_DIR,
    force_refresh: bool = False,
) -> list[str]:
    """
    Return Nifty 100 constituent symbols (Nifty 50 + Nifty Next 50).

    Parameters:
        cache_dir (str): Cache directory. | Default: 'data/indices'.
        force_refresh (bool): Bypass cache. | Default: False.

    Returns:
        list[str]: Sorted list of up to 100 NSE symbols.

    Complexity:
        Time: O(N)  Space: O(N)

    Example:
        >>> symbols = get_nifty100()
        >>> len(symbols) > 0
        True
    """
    return get_index_symbols("nifty100", cache_dir, force_refresh)


def get_rsi_universe(
    cache_dir: str = _DEFAULT_CACHE_DIR,
    force_refresh: bool = False,
) -> list[str]:
    """
    Return the combined RSI strategy universe: Nifty 50 + Nifty Next 50.

    Deduplicates and sorts the union of both index lists. Used exclusively
    by rsi_scanner.py as the eligible stock universe for RSI < 35 signals.

    Parameters:
        cache_dir (str): Cache directory. | Default: 'data/indices'.
        force_refresh (bool): Bypass cache for both indices. | Default: False.

    Returns:
        list[str]: Sorted, deduplicated list of up to 100 NSE symbols.

    Complexity:
        Time: O(N log N)  Space: O(N)

    Example:
        >>> universe = get_rsi_universe()
        >>> len(universe) >= 50
        True
    """
    n50 = get_nifty50(cache_dir, force_refresh)
    nn50 = get_nifty_next50(cache_dir, force_refresh)
    combined = sorted(set(n50) | set(nn50))
    LOGGER.info(
        "RSI universe: %d symbols (Nifty50=%d, NiftyNext50=%d)",
        len(combined),
        len(n50),
        len(nn50),
    )
    return combined
