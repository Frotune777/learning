"""
File: tests/test_screener.py
Purpose: Unit test suite for the StockScreener analytics processor module.

Dependencies:
External:
- pytest>=8.2.2: Unit test runner framework
- pandas>=2.2.3: Mock dataframes and CSV verification
- numpy>=2.4.6: Mock values and array operations
Internal:
- src.nse_bhavcopy.screener: Core screener module under test

Key Components:
Classes:
- None
Functions:
- test_screener_init: Verify screener output folder setup.
- test_get_ns_ticker: Verify stock suffix normalizer.
- test_fetch_history_success: Verify successful yfinance download.
- test_fetch_history_empty_error: Verify error raised on empty fetch.
- test_calculate_car_rating_edge_cases: Verify CAR behavior on short history.
- test_calculate_car_rating_scenarios: Verify CAR rating outputs.
- test_calculate_bottom_out_scenarios: Verify Bottom Out Hunting calculations.
- test_screen_stocks_success: Verify complete screener workflow and outputs.
- test_screen_stocks_missing_file_error: Verify FileNotFoundError.
- test_screen_stocks_invalid_columns_error: Verify KeyError on bad columns.

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- None

Related Files:
- src/nse_bhavcopy/screener.py: Core module under test.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from src.nse_bhavcopy.screener import StockScreener


def test_screener_init(tmp_path: Path) -> None:
    """
    Verify that the StockScreener correctly sets up processed output folders.

    Logic:
        Step 1: Set paths using pytest's temporary folder.
        Step 2: Instantiate screener.
        Step 3: Confirm directory existence on disk and constructor fields.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture. | Must be valid Path.

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed automatically by pytest runner

    Performance:
        Time Complexity: O(1) [Folder checking]
        Space Complexity: O(1) [Minimal objects]

    Edge Cases Handled:
        - Creates sub-folders that do not exist yet.
    """
    processed_dir: str = str(tmp_path / "processed")
    screener = StockScreener(processed_dir=processed_dir)
    assert screener.processed_dir == processed_dir
    assert os.path.exists(processed_dir)


def test_get_ns_ticker() -> None:
    """
    Verify stock ticker suffix normalization behaves correctly.

    Logic:
        Step 1: Instantiate default screener.
        Step 2: Call suffix normalizer with varying test symbols.
        Step 3: Verify suffixes and uppercase transformations.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed by pytest

    Performance:
        Time Complexity: O(1) [Direct lookup and comparison]
        Space Complexity: O(1) [Static strings]

    Edge Cases Handled:
        - Symbol already normalized (prevents double .NS additions).
        - Whitespace stripping.
    """
    screener = StockScreener()
    assert screener._get_ns_ticker("tcs") == "TCS.NS"
    assert screener._get_ns_ticker("RELIANCE.NS") == "RELIANCE.NS"
    assert screener._get_ns_ticker("  infy  ") == "INFY.NS"


def test_fetch_history_success(tmp_path: Path) -> None:
    """
    Verify successful retrieval of historical prices from yfinance.

    Logic:
        Step 1: Mock YFinanceFetcher to return standard multi-index price data.
        Step 2: Execute downloader wrapper.
        Step 3: Assert download parameters and output matches mock data.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture. | Valid path.

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed by pytest

    Performance:
        Time Complexity: O(1) [Mocked connection]
        Space Complexity: O(1) [Mock allocations]

    Edge Cases Handled:
        - Bypasses real internet call using patch.
    """
    processed_dir = str(tmp_path / "processed")
    screener = StockScreener(processed_dir=processed_dir)
    cols = pd.MultiIndex.from_tuples(
        [
            ("TCS.NS", "Open"),
            ("TCS.NS", "High"),
            ("TCS.NS", "Low"),
            ("TCS.NS", "Close"),
            ("TCS.NS", "Volume"),
        ]
    )
    mock_df = pd.DataFrame(
        [[100.0, 105.0, 95.0, 101.0, 1000.0]],
        columns=cols,
        index=[pd.Timestamp("2026-05-25")],
    )

    with patch("src.nse_bhavcopy.screener.YFinanceFetcher") as MockFetcherClass:
        mock_fetcher = MockFetcherClass.return_value
        mock_fetcher.fetch_batch.return_value = mock_df

        res = screener._fetch_history(["TCS.NS"])
        assert "TCS.NS" in res.columns.get_level_values(0)
        assert res.loc[pd.Timestamp("2026-05-25"), ("TCS.NS", "Close")] == 101.0
        mock_fetcher.fetch_batch.assert_called_once_with(
            ["TCS.NS"],
            timeframe="1d",
            period="1y",
            chunk_size=15,
            rate_delay=3.0,
        )


def test_fetch_history_empty_error(tmp_path: Path) -> None:
    """
    Verify downloader wrapper raises ValueError when yfinance returns empty.

    Logic:
        Step 1: Mock YFinanceFetcher to return completely empty DataFrame.
        Step 2: Assert ValueError is raised when calling downloader wrapper.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture. | Valid path.

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed by pytest

    Performance:
        Time Complexity: O(1) [Direct error checks]
        Space Complexity: O(1) [Static variables]

    Edge Cases Handled:
        - Empty historical datasets.
    """
    processed_dir = str(tmp_path / "processed")
    screener = StockScreener(processed_dir=processed_dir)

    with patch("src.nse_bhavcopy.screener.YFinanceFetcher") as MockFetcherClass:
        mock_fetcher = MockFetcherClass.return_value
        mock_fetcher.fetch_batch.return_value = pd.DataFrame()

        with pytest.raises(ValueError, match="empty history"):
            screener._fetch_history(["TCS.NS"])


def test_calculate_car_rating_edge_cases() -> None:
    """
    Verify CAR ratings handle invalid or short data slices defensively.

    Logic:
        Step 1: Check empty DataFrame outputs.
        Step 2: Check short trading history (< 10 records).
        Step 3: Confirm they return expected ratings gracefully.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed by pytest

    Performance:
        Time Complexity: O(1) [Direct subset checking]
        Space Complexity: O(1) [No allocations]

    Edge Cases Handled:
        - Short history (returns Short History).
        - Missing columns or empty values (returns Avoid/Hold).
    """
    screener = StockScreener()

    # Case 1: Empty DataFrame
    assert screener._calculate_car_rating(pd.DataFrame()) == "Avoid/Hold"

    # Case 2: Missing columns
    bad_df = pd.DataFrame({"Close": [100.0] * 12})
    assert screener._calculate_car_rating(bad_df) == "Avoid/Hold"

    # Case 3: Short history
    short_df = pd.DataFrame(
        {"High": [100.0] * 5, "Close": [100.0] * 5},
        index=pd.date_range("2026-05-01", periods=5),
    )
    assert screener._calculate_car_rating(short_df) == "Short History"


def test_calculate_car_rating_scenarios() -> None:
    """
    Verify CAR rating calculations work correctly under varying trend patterns.

    Logic:
        Step 1: Generate high price early in timeline, leaving a large slice.
        Step 2: Setup strictly increasing cumulative close average slice (Check=9).
        Step 3: Confirm CAR rating is Buy/Average Out.
        Step 4: Setup stable/flat cumulative close average slice.
        Step 5: Confirm CAR rating is Avoid/Hold.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed by pytest

    Performance:
        Time Complexity: O(1) [Small lists evaluations]
        Space Complexity: O(1) [Static variables]

    Edge Cases Handled:
        - Non-increasing bounds or flatlines.
    """
    screener = StockScreener()
    dates = pd.date_range("2026-05-01", periods=15)

    # Scenario A: Strictly increasing cumulative averages since peak
    # Peak High is on Day 1 (index 0)
    highs_a = [150.0] + [100.0] * 14
    # Close prices generated to make expanding mean strictly increase.
    # Expanding means should go up daily for last 10 days.
    # E.g. prices: 10, 20, 30, 40, ...
    closes_a = [10.0 + 5.0 * i for i in range(15)]
    df_a = pd.DataFrame({"High": highs_a, "Close": closes_a}, index=dates)

    assert screener._calculate_car_rating(df_a) == "Buy/Average Out"

    # Scenario B: Flat close prices (Check < 9)
    highs_b = [150.0] + [100.0] * 14
    closes_b = [100.0] * 15
    df_b = pd.DataFrame({"High": highs_b, "Close": closes_b}, index=dates)

    assert screener._calculate_car_rating(df_b) == "Avoid/Hold"


def test_calculate_bottom_out_scenarios() -> None:
    """
    Verify the StockScreener._calculate_bottom_out logic across diverse scenarios.

    Logic:
        Step 1: Instantiate StockScreener with default parameters.
        Step 2: Test empty dataframe returns No Data.
        Step 3: Test dataframe missing columns returns No Data.
        Step 4: Test dataframe with history length < 20 returns Short History.
        Step 5: Test invalid low (low_20d <= 0) returns Invalid Low.
        Step 6: Test floor tested returns Do not start GTT.
        Step 7: Test no bounce returns Do not start GTT.
        Step 8: Test weak bounce returns Start GTT (Basic).
        Step 9: Test strong bounce returns Start GTT.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> test_calculate_bottom_out_scenarios()

    Performance:
        Time Complexity: O(1) [Calculated on mocked structures]
        Space Complexity: O(1) [Temporary test allocation]

    Edge Cases Handled:
        - Missing columns and empty dataframes.
        - Short history constraints and non-positive price limits.
    """
    screener = StockScreener(bottom_out_tolerance=0.5, bounce_buffer=1.0)

    # Step 2: Empty DataFrame
    assert (
        screener._calculate_bottom_out(pd.DataFrame())["BOTTOM_OUT_STATUS"] == "No Data"
    )

    # Step 3: Missing columns
    df_missing = pd.DataFrame({"High": [10.0] * 20, "Low": [9.0] * 20})
    assert screener._calculate_bottom_out(df_missing)["BOTTOM_OUT_STATUS"] == "No Data"

    # Step 4: Short history
    df_short = pd.DataFrame(
        {"High": [10.0] * 10, "Low": [9.0] * 10, "Close": [9.5] * 10}
    )
    assert (
        screener._calculate_bottom_out(df_short)["BOTTOM_OUT_STATUS"] == "Short History"
    )

    # Step 5: Invalid low (low_20d <= 0)
    df_invalid_low = pd.DataFrame(
        {"High": [10.0] * 20, "Low": [0.0] * 20, "Close": [9.5] * 20}
    )
    assert (
        screener._calculate_bottom_out(df_invalid_low)["BOTTOM_OUT_STATUS"]
        == "Invalid Low"
    )

    # Step 6: No floor tested
    highs = [150.0] * 20
    lows = [100.0] * 19 + [101.0]
    closes = [102.0] * 20
    df_no_floor = pd.DataFrame({"High": highs, "Low": lows, "Close": closes})
    res_no_floor = screener._calculate_bottom_out(df_no_floor)
    assert res_no_floor["BOTTOM_OUT_STATUS"] == "Do not start GTT"
    assert res_no_floor["SWING_ADVICE"] == "Wait for best time"

    # Step 7: No bounce
    lows = [100.0] * 19 + [100.2]
    closes = [105.0] * 19 + [100.2]
    df_no_bounce = pd.DataFrame({"High": highs, "Low": lows, "Close": closes})
    res_no_bounce = screener._calculate_bottom_out(df_no_bounce)
    assert res_no_bounce["BOTTOM_OUT_STATUS"] == "Do not start GTT"
    assert res_no_bounce["SWING_ADVICE"] == "No bounce — avoid"

    # Step 8: Weak bounce
    lows = [100.0] * 19 + [100.2]
    closes = [105.0] * 19 + [100.5]
    df_weak = pd.DataFrame({"High": highs, "Low": lows, "Close": closes})
    res_weak = screener._calculate_bottom_out(df_weak)
    assert res_weak["BOTTOM_OUT_STATUS"] == "Start GTT (Basic)"
    assert "Weak bounce" in res_weak["SWING_ADVICE"]

    # Step 9: Strong bounce
    lows = [100.0] * 19 + [100.2]
    closes = [105.0] * 19 + [101.5]
    df_strong = pd.DataFrame({"High": highs, "Low": lows, "Close": closes})
    res_strong = screener._calculate_bottom_out(df_strong)
    assert res_strong["BOTTOM_OUT_STATUS"] == "Start GTT"
    assert "Bounce: 1.50%" in res_strong["SWING_ADVICE"]


def test_screen_stocks_success(tmp_path: Path) -> None:
    """
    Verify complete stock screener operations from source files to final lists.

    Logic:
        Step 1: Create a mock top 250 source CSV containing RELIANCE and TCS.
        Step 2: Construct multi-index historical mock prices.
        Step 3: Set RELIANCE to trigger "In Bull Run" and "Buy/Average Out".
        Step 4: Set TCS to trigger flat results (Avoid/Hold).
        Step 5: Mock _fetch_history and run screen_stocks.
        Step 6: Verify file outputs are created in the processed folder.
        Step 7: Confirm RELIANCE (Bull run targets) is extracted to final list.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture. | Valid path.

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed by pytest

    Performance:
        Time Complexity: O(N * W) [Iterative dataframe analysis]
        Space Complexity: O(N) [Temporary tables storage]

    Edge Cases Handled:
        - Filters out Avoid/Hold symbols from the target final list.
        - Sorts results by volume (turnover) in descending order.
    """
    processed_dir: str = str(tmp_path / "processed")
    screener = StockScreener(processed_dir=processed_dir)

    # 1. Create mock top 250 source file
    source_df = pd.DataFrame(
        {
            "SYMBOL": ["RELIANCE", "TCS", "MISSING_TICKER"],
            "TURNOVER": [10000.0, 20000.0, 500.0],
            "CLOSE": [1500.0, 2200.0, 100.0],
        }
    )
    source_path = str(tmp_path / "top_250_mock.csv")
    source_df.to_csv(source_path, index=False)

    # 2. Build multi-index historical data matching yfinance output structure
    # Standard 200 days history to fulfill CAR and DMA requirements
    dates = pd.date_range("2026-05-01", periods=200)
    cols = pd.MultiIndex.from_tuples(
        [
            ("RELIANCE.NS", "High"),
            ("RELIANCE.NS", "Low"),
            ("RELIANCE.NS", "Close"),
            ("TCS.NS", "High"),
            ("TCS.NS", "Low"),
            ("TCS.NS", "Close"),
        ]
    )

    # RELIANCE.NS will be set up to trigger a "Buy/Average Out"
    # and "In Bull Run" (CMP=107.95, DMA_200=102.975, Diff%=4.83%)
    # Daily closes should make expanding mean strictly increase.
    # Set Low to 106.0 for last 20 days so floor is tested (20D low=106.0)
    rel_close = [98.0 + 0.05 * i for i in range(200)]  # Peak high at 150 early
    rel_high = [150.0] + [110.0] * 199
    rel_low = [97.0] + [106.0] * 199

    # TCS.NS will have stable flat prices (Avoid/Hold)
    tcs_close = [2200.0] * 200
    tcs_high = [2200.0] * 200
    tcs_low = [2200.0] * 200

    hist_data = np.column_stack(
        (rel_high, rel_low, rel_close, tcs_high, tcs_low, tcs_close)
    )
    mock_history = pd.DataFrame(hist_data, columns=cols, index=dates)

    test_date = datetime(2026, 5, 26)

    with patch.object(screener, "_fetch_history", return_value=mock_history):
        final_path = screener.screen_stocks(source_path, test_date)

        # Confirm analyzed complete results exist
        expected_analyzed = os.path.join(processed_dir, "top_250_analyzed_20260526.csv")
        assert os.path.exists(expected_analyzed)

        analyzed_df = pd.read_csv(expected_analyzed)
        assert len(analyzed_df) == 3

        # MISSING_TICKER should be marked with TICKER NOT FOUND
        missing_row = analyzed_df[analyzed_df["SYMBOL"] == "MISSING_TICKER"]
        assert missing_row.iloc[0]["TREND_STATUS"] == "TICKER NOT FOUND"

        # RELIANCE should be marked In Bull Run / Buy/Average Out
        rel_row = analyzed_df[analyzed_df["SYMBOL"] == "RELIANCE"]
        assert rel_row.iloc[0]["TREND_STATUS"] == "In Bull Run"
        assert rel_row.iloc[0]["CAR_RATING"] == "Buy/Average Out"
        assert rel_row.iloc[0]["BOTTOM_OUT_STATUS"] == "Start GTT"

        # TCS should be marked Avoid/Hold
        tcs_row = analyzed_df[analyzed_df["SYMBOL"] == "TCS"]
        assert tcs_row.iloc[0]["CAR_RATING"] == "Avoid/Hold"

        # Check all three filtered lists are correctly generated
        expected_final = os.path.join(processed_dir, "final_list_20260526.csv")
        expected_swing = os.path.join(processed_dir, "swing_list_20260526.csv")
        expected_super = os.path.join(processed_dir, "super_list_20260526.csv")

        assert final_path == expected_super
        assert os.path.exists(expected_final)
        assert os.path.exists(expected_swing)
        assert os.path.exists(expected_super)

        # Verify Filter A
        final_df = pd.read_csv(expected_final)
        assert len(final_df) == 1
        assert final_df.iloc[0]["NSE Code"] == "RELIANCE"
        assert final_df.iloc[0]["CAR"] == "Buy/Average Out"
        assert list(final_df.columns) == [
            "NSE Code",
            "Volume",
            "Qty",
            "Total Traded Value",
            "Previous Close",
            "CMP",
            "Difference from 200 DMA",
            "CAR",
            "RSI",
            "Tech Score",
            "Tech Rating",
        ]

        # Verify Filter B (swing list)
        swing_df = pd.read_csv(expected_swing)
        assert len(swing_df) == 1
        assert swing_df.iloc[0]["NSE Code"] == "RELIANCE"
        assert swing_df.iloc[0]["Swing Signal"] == "Start GTT"
        assert list(swing_df.columns) == [
            "NSE Code",
            "Volume",
            "Qty",
            "Total Traded Value",
            "CMP",
            "20 Day High",
            "20 Day Low",
            "Today Low",
            "GTT Trigger Price",
            "Swing Signal",
            "Action",
            "RSI",
            "Tech Score",
        ]

        # Verify Filter C (super list)
        super_df = pd.read_csv(expected_super)
        assert len(super_df) == 1
        assert super_df.iloc[0]["NSE Code"] == "RELIANCE"
        assert list(super_df.columns) == [
            "NSE Code",
            "Volume",
            "Qty",
            "Total Traded Value",
            "CMP",
            "Diff 200 DMA",
            "CAR",
            "RSI",
            "Tech Score",
            "20 Day High",
            "20 Day Low",
            "Today Low",
            "GTT Trigger",
            "Action",
        ]


def test_screen_stocks_missing_file_error() -> None:
    """
    Verify screen_stocks raises FileNotFoundError when source file is missing.

    Logic:
        Step 1: Call screen_stocks with a non-existent filepath.
        Step 2: Assert FileNotFoundError is raised.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed by pytest

    Performance:
        Time Complexity: O(1) [Instant path check]
        Space Complexity: O(1) [No allocations]

    Edge Cases Handled:
        - Non-existent source paths.
    """
    screener = StockScreener()
    with pytest.raises(FileNotFoundError, match="Source file not found"):
        screener.screen_stocks("non_existent_file.csv", datetime.now())


def test_screen_stocks_invalid_columns_error(tmp_path: Path) -> None:
    """
    Verify screen_stocks raises KeyError on invalid source file columns.

    Logic:
        Step 1: Create CSV with missing critical columns (e.g. no SYMBOL).
        Step 2: Execute screen_stocks.
        Step 3: Assert KeyError is raised.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture. | Valid path.

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed by pytest

    Performance:
        Time Complexity: O(1) [Instant column checks]
        Space Complexity: O(1) [No allocations]

    Edge Cases Handled:
        - Source files containing invalid formatting.
    """
    screener = StockScreener()
    bad_df = pd.DataFrame({"WRONG_COL": ["TCS"]})
    bad_path = str(tmp_path / "bad_columns.csv")
    bad_df.to_csv(bad_path, index=False)

    with pytest.raises(KeyError, match="SYMBOL and TURNOVER columns"):
        screener.screen_stocks(bad_path, datetime.now())


def test_calculate_car_rating_short_rows_after_slice() -> None:
    """
    Verify CAR rating returns Short History if sliced rows are under 10.

    Logic:
        Step 1: Construct 15 rows where high is at index 12 (leaving 3 rows).
        Step 2: Assert CAR rating returns Short History.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed by pytest
    """
    screener = StockScreener()
    # High at 12 leaves only 3 days slice
    highs = [100.0] * 12 + [150.0] + [100.0] * 2
    closes = [90.0] * 15
    df = pd.DataFrame(
        {"High": highs, "Close": closes},
        index=pd.date_range("2026-05-01", periods=15),
    )
    assert screener._calculate_car_rating(df) == "Short History"


def test_screen_stocks_fetch_history_error(tmp_path: Path) -> None:
    """
    Verify screen_stocks re-raises download exceptions.

    Logic:
        Step 1: Create mock source file.
        Step 2: Mock _fetch_history to raise Exception.
        Step 3: Assert exception is raised and logged.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture. | Valid path.

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed by pytest
    """
    screener = StockScreener()
    source_df = pd.DataFrame(
        {"SYMBOL": ["TCS"], "TURNOVER": [1000.0], "CLOSE": [3000.0]}
    )
    source_path = str(tmp_path / "src.csv")
    source_df.to_csv(source_path, index=False)

    with patch.object(
        screener, "_fetch_history", side_effect=ValueError("Failed connection")
    ):
        with pytest.raises(ValueError, match="Failed connection"):
            screener.screen_stocks(source_path, datetime.now())


def test_screen_stocks_ticker_missing_key_or_short_history(
    tmp_path: Path,
) -> None:
    """
    Verify screener handles KeyError or short histories defensively.

    Logic:
        Step 1: Create source file with two tickers (TCS and INFY).
        Step 2: Mock df_history such that INFY has only 1 row of history.
        Step 3: Mock KeyError during lookup for TCS.
        Step 4: Execute screen_stocks.
        Step 5: Verify both are marked as TICKER NOT FOUND.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture. | Valid path.

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed by pytest
    """
    processed_dir: str = str(tmp_path / "processed")
    screener = StockScreener(processed_dir=processed_dir)

    source_df = pd.DataFrame(
        {"SYMBOL": ["TCS", "INFY"], "TURNOVER": [100.0, 200.0], "CLOSE": [10, 20]}
    )
    source_path = str(tmp_path / "src_test.csv")
    source_df.to_csv(source_path, index=False)

    # Multi-index columns levels
    cols = pd.MultiIndex.from_tuples(
        [
            ("TCS.NS", "High"),
            ("TCS.NS", "Close"),
            ("INFY.NS", "High"),
            ("INFY.NS", "Close"),
        ]
    )
    dates = pd.date_range("2026-05-01", periods=15)
    # INFY will only have NaNs except last day to force short history
    infy_close = [np.nan] * 14 + [20.0]
    infy_high = [np.nan] * 14 + [20.0]
    tcs_close = [10.0] * 15
    tcs_high = [10.0] * 15

    hist_data = np.column_stack((tcs_high, tcs_close, infy_high, infy_close))
    mock_history = pd.DataFrame(hist_data, columns=cols, index=dates)

    # Let's mock _fetch_history and df_history indexing
    with patch.object(screener, "_fetch_history", return_value=mock_history):
        # We want TCS.NS lookup to raise KeyError. Let's patch __getitem__
        orig_getitem = pd.DataFrame.__getitem__

        def mock_getitem(self_obj: Any, key: Any) -> Any:
            if isinstance(key, str) and key == "TCS.NS":
                raise KeyError("Mocked KeyError")
            return orig_getitem(self_obj, key)

        with patch("pandas.DataFrame.__getitem__", mock_getitem):
            screener.screen_stocks(source_path, datetime(2026, 5, 26))

    expected_analyzed = os.path.join(processed_dir, "top_250_analyzed_20260526.csv")
    assert os.path.exists(expected_analyzed)
    df_res = pd.read_csv(expected_analyzed)
    assert df_res.iloc[0]["TREND_STATUS"] == "TICKER NOT FOUND"
    assert df_res.iloc[1]["TREND_STATUS"] == "TICKER NOT FOUND"


def test_screen_stocks_bear_run(tmp_path: Path) -> None:
    """
    Verify screen_stocks correctly identifies stocks in Bear Run.

    Logic:
        Step 1: Create source file with RELIANCE.
        Step 2: Mock history with prices below all DMAs (Bear Run).
        Step 3: Assert Bear Run is set in output analyzed CSV.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture. | Valid path.

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed by pytest
    """
    processed_dir: str = str(tmp_path / "processed")
    screener = StockScreener(processed_dir=processed_dir)

    source_df = pd.DataFrame(
        {"SYMBOL": ["RELIANCE"], "TURNOVER": [1000.0], "CLOSE": [95.0]}
    )
    source_path = str(tmp_path / "src_bear.csv")
    source_df.to_csv(source_path, index=False)

    cols = pd.MultiIndex.from_tuples(
        [("RELIANCE.NS", "High"), ("RELIANCE.NS", "Close")]
    )
    dates = pd.date_range("2026-05-01", periods=200)
    # CMP = 95, DMA_50/100/200 = 100
    closes = [100.0] * 199 + [95.0]
    highs = [100.0] * 200

    hist_data = np.column_stack((highs, closes))
    mock_history = pd.DataFrame(hist_data, columns=cols, index=dates)

    with patch.object(screener, "_fetch_history", return_value=mock_history):
        screener.screen_stocks(source_path, datetime(2026, 5, 26))

    expected_analyzed = os.path.join(processed_dir, "top_250_analyzed_20260526.csv")
    df_res = pd.read_csv(expected_analyzed)
    assert df_res.iloc[0]["TREND_STATUS"] == "In Bear Run"


def test_fetch_history_chunk_failure(tmp_path: Path) -> None:
    """
    Verify _fetch_history tolerates chunk exceptions.

    Logic:
        Step 1: Mock fetcher to return empty.
        Step 2: Assert ValueError is raised when all chunks fail.
    """
    processed_dir = str(tmp_path / "processed")
    screener = StockScreener(processed_dir=processed_dir)

    with patch("src.nse_bhavcopy.screener.YFinanceFetcher") as MockFetcherClass:
        mock_fetcher = MockFetcherClass.return_value
        mock_fetcher.fetch_batch.return_value = pd.DataFrame()

        with pytest.raises(ValueError, match="empty history"):
            screener._fetch_history(["TCS.NS"])


def test_screen_stocks_insufficient_history(tmp_path: Path) -> None:
    """
    Verify screen_stocks assigns Insufficient History trend status.
    """
    processed_dir: str = str(tmp_path / "processed")
    screener = StockScreener(processed_dir=processed_dir)

    source_df = pd.DataFrame(
        {"SYMBOL": ["RELIANCE"], "TURNOVER": [1000.0], "CLOSE": [100.0]}
    )
    source_path = str(tmp_path / "src_short.csv")
    source_df.to_csv(source_path, index=False)

    cols = pd.MultiIndex.from_tuples(
        [("RELIANCE.NS", "High"), ("RELIANCE.NS", "Close")]
    )
    # Provide only 15 days of data
    dates = pd.date_range("2026-05-01", periods=15)
    closes = [100.0] * 15
    highs = [105.0] * 15

    hist_data = np.column_stack((highs, closes))
    mock_history = pd.DataFrame(hist_data, columns=cols, index=dates)

    with patch.object(screener, "_fetch_history", return_value=mock_history):
        screener.screen_stocks(source_path, datetime(2026, 5, 26))

    expected_analyzed = os.path.join(processed_dir, "top_250_analyzed_20260526.csv")
    df_res = pd.read_csv(expected_analyzed)
    assert df_res.iloc[0]["TREND_STATUS"] == "Insufficient History"
    assert pd.isna(df_res.iloc[0]["DMA_50"])
    assert pd.isna(df_res.iloc[0]["DMA_200"])


def test_fetch_history_single_ticker(tmp_path: Path) -> None:
    """
    Verify that _fetch_history wraps flat columns into a proper MultiIndex.
    """
    processed_dir: str = str(tmp_path / "processed")
    screener = StockScreener(processed_dir=processed_dir)

    cols = pd.MultiIndex.from_tuples(
        [
            ("TCS.NS", "Open"),
            ("TCS.NS", "High"),
            ("TCS.NS", "Low"),
            ("TCS.NS", "Close"),
            ("TCS.NS", "Volume"),
        ]
    )
    dates = pd.date_range("2026-05-01", periods=5)
    mock_df = pd.DataFrame(
        [[10.0, 12.0, 9.0, 11.0, 100]] * 5,
        columns=cols,
        index=dates,
    )

    with patch("src.nse_bhavcopy.screener.YFinanceFetcher") as MockFetcherClass:
        mock_fetcher = MockFetcherClass.return_value
        mock_fetcher.fetch_batch.return_value = mock_df

        res_df = screener._fetch_history(["TCS.NS"])

    assert isinstance(res_df.columns, pd.MultiIndex)
    assert "TCS.NS" in res_df.columns.get_level_values(0)
    assert list(res_df["TCS.NS"].columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_fetch_history_parquet_cache_loop(tmp_path: Path) -> None:
    """
    Verify that _fetch_history successfully writes Parquet cache files to disk.
    """
    processed_dir: str = str(tmp_path / "processed")
    screener = StockScreener(processed_dir=processed_dir)

    # Setup mock download response (MultiIndexed)
    cols = pd.MultiIndex.from_tuples(
        [
            ("TCS.NS", "Open"),
            ("TCS.NS", "High"),
            ("TCS.NS", "Low"),
            ("TCS.NS", "Close"),
            ("TCS.NS", "Volume"),
        ]
    )
    dates = pd.date_range("2026-05-01", periods=5)
    mock_df = pd.DataFrame(
        [[10.0, 12.0, 9.0, 11.0, 100]] * 5,
        columns=cols,
        index=dates,
    )

    # First download: cache should be populated
    with patch("src.nse_bhavcopy.screener.YFinanceFetcher") as MockFetcherClass:
        mock_fetcher = MockFetcherClass.return_value
        mock_fetcher.fetch_batch.return_value = mock_df

        screener._fetch_history(["TCS.NS"])
        assert mock_fetcher.fetch_batch.call_count == 1

    cache_file = os.path.join(processed_dir, "1d", "TCS.parquet")
    assert os.path.exists(cache_file)

    # Second download: must fetch from the local cache file, fetch_batch call count = 0
    with patch("src.nse_bhavcopy.screener.YFinanceFetcher") as MockFetcherClass_second:
        mock_fetcher_second = MockFetcherClass_second.return_value
        mock_fetcher_second.fetch_batch.return_value = pd.DataFrame()

        second_res = screener._fetch_history(["TCS.NS"])
        mock_fetcher_second.fetch_batch.assert_not_called()

    assert isinstance(second_res.columns, pd.MultiIndex)
    assert "TCS.NS" in second_res.columns.get_level_values(0)


def test_fetch_history_incremental_cache_crud(tmp_path: Path) -> None:
    """
    Verify that _fetch_history performs incremental CRUD on existing Parquet caches.
    """
    processed_dir: str = str(tmp_path / "processed")
    screener = StockScreener(processed_dir=processed_dir)

    cache_dir = os.path.join(processed_dir, "1d")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, "TCS.parquet")

    # Step 1: Write initial mock cache file
    dates = pd.date_range("2026-05-20", periods=5)  # May 20 to May 24
    initial_df = pd.DataFrame(
        {
            "Open": [10.0] * 5,
            "High": [12.0] * 5,
            "Low": [9.0] * 5,
            "Close": [11.0] * 5,
            "Volume": [100.0] * 5,
        },
        index=dates,
    )
    initial_df.to_parquet(cache_file)

    # Step 2: Trigger fetch with May 26 today_prices
    today_prices = {"TCS.NS": 3500.0}
    test_date = datetime(2026, 5, 26)

    with patch("src.nse_bhavcopy.screener.YFinanceFetcher") as MockFetcherClass:
        mock_fetcher = MockFetcherClass.return_value
        mock_fetcher.fetch_batch.return_value = pd.DataFrame()

        res_df = screener._fetch_history(
            ["TCS.NS"], today_prices=today_prices, date_obj=test_date
        )
        # Assert no network call made
        mock_fetcher.fetch_batch.assert_not_called()

    # Step 4: Verify cache file updated on disk
    updated_df = pd.read_parquet(cache_file)
    assert len(updated_df) == 6  # 5 initial + 1 appended
    assert pd.Timestamp("2026-05-26") in updated_df.index
    assert updated_df.loc["2026-05-26", "Close"] == 3500.0

    # Verify return value is MultiIndexed
    assert isinstance(res_df.columns, pd.MultiIndex)
    assert res_df.loc["2026-05-26", ("TCS.NS", "Close")] == 3500.0
