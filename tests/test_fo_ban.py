"""
File: tests/test_fo_ban.py
Purpose: Unit tests for FOBanManager.
Last Modified: 2026-05-27
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from src.scrapers.fo_ban import FOBanManager


def test_fo_ban_parsing() -> None:
    """
    Verify F&O ban list parsing logic extracts symbols correctly.

    Parameters:
        None

    Returns:
        None

    Complexity:
        Time: O(1)
        Space: O(1)
    """
    csv_content = (
        "SYMBOL,SECURITY NAME\n"
        "IBULHSGFIN,Indiabulls Housing Finance\n"
        "ZEEL,Zee Entertainment Enterprises Ltd\n"
    )
    manager = FOBanManager(cache_dir="data")
    symbols = manager._parse_csv_content(csv_content)

    assert "IBULHSGFIN" in symbols
    assert "ZEEL" in symbols
    assert "SYMBOL" not in symbols
    assert len(symbols) == 2


@patch("requests.get")
def test_fo_ban_fetch_network_success(mock_get: MagicMock, tmp_path: Path) -> None:
    """
    Verify successful network download and cache writing.

    Parameters:
        mock_get (MagicMock): Mocked requests.get method.
        tmp_path (Path): Pytest temporary path.

    Returns:
        None

    Complexity:
        Time: O(1)
        Space: O(1)
    """
    csv_content = "SYMBOL,SECURITY NAME\n" "IBULHSGFIN,Indiabulls Housing Finance\n"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = csv_content
    mock_get.return_value = mock_resp

    manager = FOBanManager(cache_dir=str(tmp_path))
    symbols = manager.fetch_fo_ban_list()

    assert "IBULHSGFIN" in symbols
    assert os.path.exists(manager.cache_path)


@patch("requests.get")
def test_fo_ban_fetch_fallback_to_cache(mock_get: MagicMock, tmp_path: Path) -> None:
    """
    Verify network failure gracefully falls back to local cached files.

    Parameters:
        mock_get (MagicMock): Mocked requests.get method.
        tmp_path (Path): Pytest temporary path.

    Returns:
        None

    Complexity:
        Time: O(1)
        Space: O(1)
    """
    # Write mock cache first
    cache_file = tmp_path / "fo_secban.csv"
    cache_file.write_text(
        "SYMBOL,SECURITY NAME\nZEEL,Zee Entertainment\n", encoding="utf-8"
    )

    # Force network failure
    mock_get.side_effect = requests.RequestException("Network Error")

    manager = FOBanManager(cache_dir=str(tmp_path))
    symbols = manager.fetch_fo_ban_list()

    assert "ZEEL" in symbols
    assert "SYMBOL" not in symbols


def test_is_banned_checks() -> None:
    """
    Verify F&O ban checks with and without suffixes.

    Parameters:
        None

    Returns:
        None

    Complexity:
        Time: O(1)
        Space: O(1)
    """
    manager = FOBanManager()
    ban_list = ["ZEEL", "TCS"]

    assert manager.is_banned("ZEEL", ban_list)
    assert manager.is_banned("zeel", ban_list)
    assert manager.is_banned("ZEEL.NS", ban_list)
    assert not manager.is_banned("INFY", ban_list)
