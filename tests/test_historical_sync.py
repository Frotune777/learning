"""
File: tests/test_historical_sync.py
Purpose: Complete unit test suite for the HistoricalSync module.
Last Modified: 2026-05-27
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.fetcher.prices.yfinance_fetcher import YFinanceFetcher
from src.nse_bhavcopy.fyers_fetcher import FyersAuthError
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


def test_historical_sync_circuit_breaker(tmp_path: Path) -> None:
    sync_dir = tmp_path / "historical"
    sync = HistoricalSync(data_dir=str(sync_dir))

    mock_fyers = MagicMock()
    mock_fyers.fetch.side_effect = FyersAuthError("401 Unauthorized")
    sync.fetcher = mock_fyers

    dates = pd.date_range("2026-01-01", periods=10)
    fallback_df = pd.DataFrame(
        {
            "Close": [100.0] * 10,
            "Open": [100.0] * 10,
            "High": [105.0] * 10,
            "Low": [95.0] * 10,
            "Volume": [1000.0] * 10,
        },
        index=dates,
    )

    with patch.object(YFinanceFetcher, "fetch", return_value=fallback_df):
        res = sync.sync_one("RELIANCE")
        assert res is True
        # Verify circuit breaker shifted fetcher instance to YFinanceFetcher
        assert isinstance(sync.fetcher, YFinanceFetcher)


def test_historical_sync_extract_symbol_from_batch(tmp_path: Path) -> None:
    sync = HistoricalSync(data_dir=str(tmp_path))
    dates = pd.date_range("2026-01-01", periods=5)
    cols = pd.MultiIndex.from_tuples(
        [
            ("RELIANCE.NS", "Open"),
            ("RELIANCE.NS", "High"),
            ("RELIANCE.NS", "Low"),
            ("RELIANCE.NS", "Close"),
            ("RELIANCE.NS", "Volume"),
            ("TCS.NS", "Close"),
        ]
    )
    df_batch = pd.DataFrame(
        [
            [100.0, 105.0, 95.0, 102.0, 1000.0, 3000.0],
            [102.0, 106.0, 101.0, 104.0, 1500.0, 3050.0],
            [104.0, 107.0, 103.0, 105.0, 1200.0, 3020.0],
            [105.0, 108.0, 104.0, 106.0, 1100.0, 3010.0],
            [106.0, 109.0, 105.0, 107.0, 1300.0, 3040.0],
        ],
        index=dates,
        columns=cols,
    )

    extracted = sync._extract_symbol_from_batch(df_batch, "RELIANCE")
    assert not extracted.empty
    assert list(extracted.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(extracted) == 5
    assert extracted.loc["2026-01-01", "Close"] == 102.0


def test_historical_sync_batch_yfinance(tmp_path: Path) -> None:
    from src.data.fetcher.prices.yfinance_fetcher import YFinanceFetcher

    sync = HistoricalSync(data_dir=str(tmp_path))
    mock_yf = MagicMock(spec=YFinanceFetcher)
    dates = pd.date_range("2026-01-01", periods=5)
    cols = pd.MultiIndex.from_tuples(
        [
            ("INFY.NS", "Open"),
            ("INFY.NS", "High"),
            ("INFY.NS", "Low"),
            ("INFY.NS", "Close"),
            ("INFY.NS", "Volume"),
            ("WIPRO.NS", "Open"),
            ("WIPRO.NS", "High"),
            ("WIPRO.NS", "Low"),
            ("WIPRO.NS", "Close"),
            ("WIPRO.NS", "Volume"),
        ]
    )
    batch_df = pd.DataFrame(
        [
            [100.0, 105.0, 95.0, 102.0, 1000.0, 50.0, 52.0, 48.0, 51.0, 500.0],
            [102.0, 106.0, 101.0, 104.0, 1500.0, 51.0, 53.0, 49.0, 52.0, 600.0],
            [104.0, 107.0, 103.0, 105.0, 1200.0, 52.0, 54.0, 50.0, 53.0, 550.0],
            [105.0, 108.0, 104.0, 106.0, 1100.0, 53.0, 55.0, 51.0, 54.0, 700.0],
            [106.0, 109.0, 105.0, 107.0, 1300.0, 54.0, 56.0, 52.0, 55.0, 800.0],
        ],
        index=dates,
        columns=cols,
    )
    mock_yf.fetch_batch.return_value = batch_df
    sync.fetcher = mock_yf

    results = sync.sync_batch(["INFY", "WIPRO"])
    assert results == {"INFY": True, "WIPRO": True}
    assert os.path.exists(sync._parquet_path("INFY"))
    assert os.path.exists(sync._parquet_path("WIPRO"))
    df_infy = pd.read_parquet(sync._parquet_path("INFY"))
    assert len(df_infy) == 5
    assert "Close" in df_infy.columns


def test_historical_sync_atomic_save_mid_write_failure(tmp_path: Path) -> None:
    sync = HistoricalSync(data_dir=str(tmp_path))
    symbol = "TESTSYM"
    final_path = sync._parquet_path(symbol)
    os.makedirs(os.path.dirname(final_path), exist_ok=True)

    # Pre-populate an existing valid Parquet file
    dates = pd.date_range("2026-01-01", periods=5)
    orig_df = pd.DataFrame(
        {
            "Close": [100.0] * 5,
            "Open": [100.0] * 5,
            "High": [105.0] * 5,
            "Low": [95.0] * 5,
            "Volume": [1000.0] * 5,
        },
        index=dates,
    )
    orig_df.to_parquet(final_path)

    # Prepare new data that fails mid-write
    new_dates = pd.date_range("2026-01-01", periods=10)
    new_df = pd.DataFrame(
        {
            "Close": [200.0] * 10,
            "Open": [200.0] * 10,
            "High": [205.0] * 10,
            "Low": [195.0] * 10,
            "Volume": [2000.0] * 10,
        },
        index=new_dates,
    )

    # Patch DataFrame.to_parquet to raise an error
    with patch.object(pd.DataFrame, "to_parquet", side_effect=OSError("Disk write failed")):
        with pytest.raises(OSError, match="Disk write failed"):
            sync._save(symbol, new_df)

    # Assert existing file is preserved and uncorrupted
    assert os.path.exists(final_path)
    preserved_df = pd.read_parquet(final_path)
    assert len(preserved_df) == 5
    assert preserved_df["Close"].iloc[0] == 100.0

    # Assert no leftover temporary files in directory
    parent_dir = os.path.dirname(final_path)
    tmp_files = [f for f in os.listdir(parent_dir) if f.endswith(".tmp")]
    assert len(tmp_files) == 0


