"""
File: tests/test_historical_sync.py
Purpose: Complete unit test suite for the HistoricalSync module.
Last Modified: 2026-05-27
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from src.storage.historical_sync import HistoricalSync


def test_historical_sync_needs_full_refresh(tmp_path: Path) -> None:
    """
    Verify coverage-based decision for triggering full history downloads.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture. | Valid path.

    Returns:
        None

    Raises:
        None

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> # Executed by pytest
    """
    sync = HistoricalSync(data_dir=str(tmp_path))

    # Empty df or < 2 rows -> True
    assert sync._needs_full_refresh(pd.DataFrame()) is True
    assert sync._needs_full_refresh(pd.DataFrame({"Close": [100.0]})) is True

    # 100 days with 100 rows -> good coverage (False)
    dates = pd.date_range("2026-01-01", periods=100)
    df_good = pd.DataFrame({"Close": [100.0] * 100}, index=dates)
    assert sync._needs_full_refresh(df_good) is False


def test_historical_sync_corporate_action_split(tmp_path: Path) -> None:
    """
    Verify corporate action adjustment when a 2:1 stock split occurs.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture. | Valid path.

    Returns:
        None

    Raises:
        None

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> # Executed by pytest
    """
    sync_dir = tmp_path / "historical"
    sync = HistoricalSync(data_dir=str(sync_dir))

    # Create existing historical dataframe ending at 2026-05-20 (May 20)
    dates_exist = pd.date_range("2026-05-01", "2026-05-20")
    existing_df = pd.DataFrame(
        {
            "Open": [200.0] * len(dates_exist),
            "High": [210.0] * len(dates_exist),
            "Low": [190.0] * len(dates_exist),
            "Close": [200.0] * len(dates_exist),
            "Volume": [1000.0] * len(dates_exist),
        },
        index=dates_exist,
    )

    # Save to path
    symbol = "SPLIT"
    path = sync._parquet_path(symbol)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing_df.to_parquet(path)

    # Mock new incremental data overlapping at May 20 but adjusted (price 100.0)
    # The ex-date is May 21: price is 100.0. Ratio is 100/200 = 0.5 (2:1 split)
    dates_new = pd.date_range("2026-05-20", "2026-05-22")
    new_df = pd.DataFrame(
        {
            "Open": [100.0] * len(dates_new),
            "High": [105.0] * len(dates_new),
            "Low": [95.0] * len(dates_new),
            "Close": [100.0] * len(dates_new),
            "Volume": [2000.0] * len(dates_new),
        },
        index=dates_new,
    )

    # Mock fetcher
    mock_fetcher = MagicMock()
    mock_fetcher.fetch.return_value = new_df
    sync.fetcher = mock_fetcher

    # Run sync
    res = sync.sync_one(symbol)
    assert res is True

    # Read back and assert adjustment
    adjusted_df = pd.read_parquet(path)
    # The overlapping and previous rows must be adjusted by factor 0.5
    # So close price at 2026-05-19 becomes 100.0 (from 200.0)
    # Volume becomes 2000.0 (from 1000.0)
    assert adjusted_df.loc["2026-05-19", "Close"] == 100.0
    assert adjusted_df.loc["2026-05-19", "Volume"] == 2000.0
    # The new rows are appended and match close 100.0
    assert adjusted_df.loc["2026-05-22", "Close"] == 100.0


def test_historical_sync_corporate_action_gap(tmp_path: Path) -> None:
    """
    Verify corporate action adjustment when ex-date happens in a gap.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture. | Valid path.

    Returns:
        None

    Raises:
        None

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> # Executed by pytest
    """
    sync_dir = tmp_path / "historical"
    sync = HistoricalSync(data_dir=str(sync_dir))

    # Existing data ends at 2026-05-15 (May 15) close 500.0
    dates_exist = pd.date_range("2026-05-01", "2026-05-15")
    existing_df = pd.DataFrame(
        {
            "Open": [500.0] * len(dates_exist),
            "High": [510.0] * len(dates_exist),
            "Low": [490.0] * len(dates_exist),
            "Close": [500.0] * len(dates_exist),
            "Volume": [1000.0] * len(dates_exist),
        },
        index=dates_exist,
    )

    # Save to path
    symbol = "GAP_SPLIT"
    path = sync._parquet_path(symbol)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing_df.to_parquet(path)

    # New incremental data starts at May 22 (no overlap) with close 100.0
    # Ratio = 100.0 / 500.0 = 0.2 (5:1 split)
    dates_new = pd.date_range("2026-05-22", "2026-05-24")
    new_df = pd.DataFrame(
        {
            "Open": [100.0] * len(dates_new),
            "High": [102.0] * len(dates_new),
            "Low": [98.0] * len(dates_new),
            "Close": [100.0] * len(dates_new),
            "Volume": [5000.0] * len(dates_new),
        },
        index=dates_new,
    )

    mock_fetcher = MagicMock()
    mock_fetcher.fetch.return_value = new_df
    sync.fetcher = mock_fetcher

    res = sync.sync_one(symbol)
    assert res is True

    adjusted_df = pd.read_parquet(path)
    # The previous rows must be adjusted by factor 0.2
    assert adjusted_df.loc["2026-05-15", "Close"] == 100.0
    assert adjusted_df.loc["2026-05-15", "Volume"] == 5000.0
    assert adjusted_df.loc["2026-05-24", "Close"] == 100.0
