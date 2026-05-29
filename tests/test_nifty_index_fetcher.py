"""
File: tests/test_nifty_index_fetcher.py
Purpose: Unit tests for nifty_index_fetcher module with fully mocked HTTP calls.
Last Modified: 2026-05-29
"""

import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest

from src.nse_bhavcopy.nifty_index_fetcher import (
    _CACHE_TTL_SECONDS,
    _cache_path,
    _is_cache_valid,
    _load_cache,
    _save_cache,
    get_index_symbols,
    get_nifty50,
    get_nifty_next50,
    get_rsi_universe,
)


@pytest.fixture()
def tmp_cache(tmp_path: str) -> str:
    """Return a temporary directory path for cache files."""
    return str(tmp_path)


# ─── _cache_path ──────────────────────────────────────────────────────────────


def test_cache_path_returns_json(tmp_cache: str) -> None:
    """Verify _cache_path appends .json to the index key."""
    result = _cache_path("nifty50", tmp_cache)
    assert result.endswith("nifty50.json")


# ─── _is_cache_valid ──────────────────────────────────────────────────────────


def test_is_cache_valid_missing_file(tmp_cache: str) -> None:
    """Returns False when cache file does not exist."""
    path = os.path.join(tmp_cache, "missing.json")
    assert _is_cache_valid(path) is False


def test_is_cache_valid_fresh_file(tmp_cache: str) -> None:
    """Returns True for a freshly written file."""
    path = os.path.join(tmp_cache, "fresh.json")
    with open(path, "w") as fh:
        fh.write("[]")
    assert _is_cache_valid(path) is True


def test_is_cache_valid_stale_file(tmp_cache: str) -> None:
    """Returns False for a file older than TTL."""
    path = os.path.join(tmp_cache, "stale.json")
    with open(path, "w") as fh:
        fh.write("[]")
    stale_mtime = time.time() - _CACHE_TTL_SECONDS - 1
    os.utime(path, (stale_mtime, stale_mtime))
    assert _is_cache_valid(path) is False


# ─── _load_cache / _save_cache ────────────────────────────────────────────────


def test_save_and_load_cache_roundtrip(tmp_cache: str) -> None:
    """Data written by _save_cache is identical to what _load_cache returns."""
    path = os.path.join(tmp_cache, "nifty50.json")
    symbols = ["RELIANCE", "TCS", "INFY"]
    _save_cache(path, symbols)
    loaded = _load_cache(path)
    assert loaded == symbols


def test_load_cache_raises_on_non_list(tmp_cache: str) -> None:
    """_load_cache raises ValueError when JSON root is not a list."""
    path = os.path.join(tmp_cache, "bad.json")
    with open(path, "w") as fh:
        json.dump({"symbols": []}, fh)
    with pytest.raises(ValueError, match="does not contain a list"):
        _load_cache(path)


# ─── get_index_symbols ────────────────────────────────────────────────────────


def _make_nse_response(symbols: list[str]) -> MagicMock:
    """Build a mock requests.Response with NSE API structure."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"data": [{"symbol": s} for s in symbols]}
    return mock_resp


def test_get_index_symbols_fetches_and_caches(tmp_cache: str) -> None:
    """get_index_symbols returns data from NSE and writes cache file."""
    expected = ["RELIANCE", "TCS", "INFY"]
    mock_session = MagicMock()
    mock_session.get.return_value = _make_nse_response(expected)

    with patch(
        "src.nse_bhavcopy.nifty_index_fetcher.requests.Session",
        return_value=mock_session,
    ):
        result = get_index_symbols("nifty50", cache_dir=tmp_cache)

    assert sorted(result) == sorted(expected)
    assert os.path.isfile(_cache_path("nifty50", tmp_cache))


def test_get_index_symbols_serves_fresh_cache(tmp_cache: str) -> None:
    """get_index_symbols returns cached data without network call."""
    symbols = ["HDFCBANK", "ICICIBANK"]
    _save_cache(_cache_path("nifty50", tmp_cache), symbols)

    with patch("src.nse_bhavcopy.nifty_index_fetcher._fetch_from_nse") as mock_fetch:
        result = get_index_symbols("nifty50", cache_dir=tmp_cache)

    mock_fetch.assert_not_called()
    assert result == symbols


def test_get_index_symbols_raises_on_unknown_key(tmp_cache: str) -> None:
    """get_index_symbols raises KeyError for unsupported index keys."""
    with pytest.raises(KeyError, match="Unsupported index key"):
        get_index_symbols("nifty999", cache_dir=tmp_cache)


def test_get_index_symbols_falls_back_to_stale_cache(tmp_cache: str) -> None:
    """Falls back to stale cache when network fetch fails."""
    symbols = ["WIPRO"]
    path = _cache_path("nifty50", tmp_cache)
    _save_cache(path, symbols)
    stale_mtime = time.time() - _CACHE_TTL_SECONDS - 1
    os.utime(path, (stale_mtime, stale_mtime))

    with patch(
        "src.nse_bhavcopy.nifty_index_fetcher._fetch_from_nse",
        return_value=[],
    ):
        result = get_index_symbols("nifty50", cache_dir=tmp_cache)

    assert result == symbols


# ─── get_nifty50 / get_nifty_next50 ──────────────────────────────────────────


def test_get_nifty50_delegates_correctly(tmp_cache: str) -> None:
    """get_nifty50 calls get_index_symbols with 'nifty50' key."""
    with patch(
        "src.nse_bhavcopy.nifty_index_fetcher.get_index_symbols",
        return_value=["RELIANCE"],
    ) as mock_gis:
        result = get_nifty50(cache_dir=tmp_cache)

    mock_gis.assert_called_once_with("nifty50", tmp_cache, False)
    assert result == ["RELIANCE"]


def test_get_nifty_next50_delegates_correctly(tmp_cache: str) -> None:
    """get_nifty_next50 calls get_index_symbols with 'nifty_next50' key."""
    with patch(
        "src.nse_bhavcopy.nifty_index_fetcher.get_index_symbols",
        return_value=["ABCDEF"],
    ) as mock_gis:
        result = get_nifty_next50(cache_dir=tmp_cache)

    mock_gis.assert_called_once_with("nifty_next50", tmp_cache, False)
    assert result == ["ABCDEF"]


# ─── get_rsi_universe ─────────────────────────────────────────────────────────


def test_get_rsi_universe_deduplicates(tmp_cache: str) -> None:
    """get_rsi_universe returns deduplicated union of Nifty50 + Next50."""
    n50 = ["RELIANCE", "TCS", "SHARED"]
    nn50 = ["HDFCBANK", "SHARED"]
    with (
        patch(
            "src.nse_bhavcopy.nifty_index_fetcher.get_nifty50",
            return_value=n50,
        ),
        patch(
            "src.nse_bhavcopy.nifty_index_fetcher.get_nifty_next50",
            return_value=nn50,
        ),
    ):
        result = get_rsi_universe(cache_dir=tmp_cache)

    assert "SHARED" in result
    assert result.count("SHARED") == 1
    assert len(result) == 4


def test_get_rsi_universe_sorted(tmp_cache: str) -> None:
    """get_rsi_universe returns a sorted list."""
    with (
        patch(
            "src.nse_bhavcopy.nifty_index_fetcher.get_nifty50",
            return_value=["ZZZ", "AAA"],
        ),
        patch(
            "src.nse_bhavcopy.nifty_index_fetcher.get_nifty_next50",
            return_value=["MMM"],
        ),
    ):
        result = get_rsi_universe(cache_dir=tmp_cache)

    assert result == sorted(result)
