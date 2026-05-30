"""
File: tests/test_downloader.py
Purpose: Complete unit test suite for the BhavcopyDownloader module.

Dependencies:
External:
- pytest>=8.2.2: Unit test runner framework
- pandas>=2.2.3: Mock dataframes and CSV verification
- requests>=2.32.3: Handle requests mock integration
Internal:
- src.storage.downloader: Core module under test

Key Components:
Classes:
- None
Functions:
- test_downloader_init: Verifies downloader directory initialization.
- test_download_raw_bhavcopy_success: Checks successful ZIP downloader retrieval.
- test_download_raw_bhavcopy_http_error: Checks response on bad HTTP code.
- test_download_raw_bhavcopy_exception: Checks requests exception handling.
- test_save_raw_bhavcopy: Verifies downloader saves bytes to raw ZIP file.
- test_clean_dataframe_alternate_columns: Checks cleanup on old/new layouts.
- test_clean_dataframe_missing_columns: Checks KeyError on missing headers.
- test_process_bhavcopy_success: Verifies zip parsing and top list return.

Last Modified: 2026-05-26
Modified By: Fortune

Open Tasks:
- None

Related Files:
- src/nse_bhavcopy/downloader.py: Under-test module.
"""

import io
import os
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from src.storage.downloader import BhavcopyDownloader


def _create_mock_zip(columns_mode: str = "standard") -> bytes:
    """
    Helper function to create a valid mock ZIP archive in-memory for testing.
    Constructs a zip containing a simple mock CSV representing Bhavcopy.

    Logic:
        Step 1: Construct pandas columns based on the requested column mode.
        Step 2: Generate sample records (some equity, some ETFs, some non-numeric).
        Step 3: Pack CSV into in-memory ZIP byte buffer and return bytes.

    Parameters:
        columns_mode (str): Column naming style ('standard'/'alternate'). | String.

    Returns:
        bytes: Binary mock ZIP data.

    Raises:
        None

    Example:
        >>> mock_bytes = _create_mock_zip("standard")

    Performance:
        Time Complexity: O(1) [Fixed size mock generation]
        Space Complexity: O(1) [Fixed size byte structures]

    Edge Cases Handled:
        - Columns configuration style differences.
    """
    if columns_mode == "standard":
        data = {
            "SYMBOL": [
                "RELIANCE",
                "TCS",
                "INFY",
                "NIFTY-ETF",
                "GOLD-BEES",
                "LIQUID-ETF",
            ],
            "SERIES": ["EQ", "EQ", "EQ", "EQ", "EQ", "EQ"],
            "CLOSE": [2500.0, 3200.0, 1500.0, 200.0, 50.0, 100.0],
            "TURNOVER": [1000.0, 2000.0, 1500.0, 5000.0, 6000.0, 7000.0],
            "DlvrbleQty": [500.0, 1000.0, 700.0, 2500.0, 3000.0, 3500.0],
            "PctOfDlvrbleQtyTltTrdQty": [50.0, 50.0, 46.6, 50.0, 50.0, 50.0],
        }
    else:
        # Alternate headers matching older NSE format
        data = {
            "TckrSymb": ["RELIANCE", "TCS", "INFY", "GOLD-BEES"],
            "SctySrs": ["EQ", "EQ", "EQ", "EQ"],
            "ClsPric": [2500.0, 3200.0, 1500.0, 50.0],
            "TtlTrfVal": [1000.0, 2000.0, 1500.0, 6000.0],
            "DlvrbleQty": [500.0, 1000.0, 700.0, 3000.0],
            "PctOfDlvrbleQtyTltTrdQty": [50.0, 50.0, 46.6, 50.0],
        }

    df = pd.DataFrame(data)
    csv_str: str = df.to_csv(index=False)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mock_bhavcopy.csv", csv_str)

    return zip_buffer.getvalue()


def test_downloader_init(tmp_path: Path) -> None:
    """
    Verify that the BhavcopyDownloader correctly sets up output directories.
    Tests directory creation and initialization defaults.

    Logic:
        Step 1: Set paths using pytest's temporary folder.
        Step 2: Instantiate downloader.
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
        Time Complexity: O(1) [Disk checking operations]
        Space Complexity: O(1) [Minimal references]

    Edge Cases Handled:
        - Creating sub-folders that do not exist yet.
    """
    raw_dir: str = str(tmp_path / "raw")
    processed_dir: str = str(tmp_path / "processed")

    downloader = BhavcopyDownloader(
        raw_dir=raw_dir, processed_dir=processed_dir, top_n=2
    )

    assert downloader.raw_dir == raw_dir
    assert downloader.processed_dir == processed_dir
    assert downloader.top_n == 2
    assert os.path.exists(raw_dir)
    assert os.path.exists(processed_dir)


def test_download_raw_bhavcopy_success() -> None:
    """
    Verify successful retrieval of raw Bhavcopy zip file.
    Tests HTTP connection status code matching 200.

    Logic:
        Step 1: Mock requests.get to return 200 response with custom bytes.
        Step 2: Execute download method.
        Step 3: Assert download matches the mocked byte string.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed automatically by pytest runner

    Performance:
        Time Complexity: O(1) [Mocked connection speed]
        Space Complexity: O(1) [Standard allocations]

    Edge Cases Handled:
        - Bypasses real internet call using unittest.mock.patch.
    """
    downloader = BhavcopyDownloader(raw_dir="data/raw", processed_dir="data/processed")
    test_date: datetime = datetime(2026, 5, 26)
    expected_bytes: bytes = b"mock_zip_bytes"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = expected_bytes

    with patch("requests.get", return_value=mock_response) as mock_get:
        retrieved_bytes: bytes = downloader.download_raw_bhavcopy(test_date)
        assert retrieved_bytes == expected_bytes
        mock_get.assert_called_once()


def test_download_raw_bhavcopy_http_error() -> None:
    """
    Verify downloader behavior when HTTP response yields error code.
    Tests expected ValueError handling on bad status codes.

    Logic:
        Step 1: Mock requests.get to return a non-200 status code response.
        Step 2: Assert ValueError is raised when executing download.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed automatically by pytest runner

    Performance:
        Time Complexity: O(1) [Mocked logic execution]
        Space Complexity: O(1) [Static variables]

    Edge Cases Handled:
        - Non-200 HTTP code returns (e.g. 404 Not Found).
    """
    downloader = BhavcopyDownloader()
    test_date: datetime = datetime(2026, 5, 26)

    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("requests.get", return_value=mock_response):
        with pytest.raises(ValueError, match="HTTP status: 404"):
            downloader.download_raw_bhavcopy(test_date)


def test_download_raw_bhavcopy_exception() -> None:
    """
    Verify downloader handles connection exceptions properly.
    Tests propagation of RequestException from requests module.

    Logic:
        Step 1: Mock requests.get to raise RequestException.
        Step 2: Assert requests.exceptions.RequestException is raised during download.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed automatically by pytest runner

    Performance:
        Time Complexity: O(1) [Static error raises]
        Space Complexity: O(1) [Static structures]

    Edge Cases Handled:
        - Network dropouts throwing lower level RequestExceptions.
    """
    downloader = BhavcopyDownloader()
    test_date: datetime = datetime(2026, 5, 26)

    with patch(
        "requests.get",
        side_effect=requests.exceptions.RequestException("Timeout"),
    ):
        with pytest.raises(requests.exceptions.RequestException):
            downloader.download_raw_bhavcopy(test_date)


def test_save_raw_bhavcopy(tmp_path: Path) -> None:
    """
    Verify that raw ZIP files are stored on local storage accurately.
    Checks file presence and identical binary content after writing.

    Logic:
        Step 1: Instantiate downloader in temporary directories.
        Step 2: Call save method with mock data.
        Step 3: Read file from disk and assert matches input payload.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture. | Must be valid Path.

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed automatically by pytest runner

    Performance:
        Time Complexity: O(M) [Disk write and read matching length M]
        Space Complexity: O(1) [Static variables]

    Edge Cases Handled:
        - Checks exact filepath formats using absolute path resolutions.
    """
    raw_dir: str = str(tmp_path / "raw")
    downloader = BhavcopyDownloader(
        raw_dir=raw_dir, processed_dir=str(tmp_path / "processed")
    )
    test_date: datetime = datetime(2026, 5, 26)
    file_content: bytes = b"binary_zip_content"

    saved_path: str = downloader.save_raw_bhavcopy(test_date, file_content)

    assert os.path.exists(saved_path)
    with open(saved_path, "rb") as f:
        assert f.read() == file_content


def test_clean_dataframe_alternate_columns() -> None:
    """
    Verify DataFrame cleanup logic works with older alternate column names.
    Checks headers mapping and standardizations.
    """
    downloader = BhavcopyDownloader()
    data = {
        "TckrSymb": ["RELIANCE", "TCS"],
        "SctySrs": ["EQ", "EQ"],
        "ClsPric": [2500.0, 3200.0],
        "TtlTrfVal": [1000.0, 2000.0],
    }
    raw_df = pd.DataFrame(data)

    cleaned_df: pd.DataFrame = downloader._clean_dataframe(raw_df)

    assert list(cleaned_df.columns) == [
        "SYMBOL",
        "TURNOVER",
        "CLOSE",
        "DELIV_QTY",
        "DELIV_PCT",
    ]
    assert cleaned_df.iloc[0]["SYMBOL"] == "RELIANCE"
    assert cleaned_df.iloc[0]["TURNOVER"] == 1000.0
    assert cleaned_df.iloc[0]["CLOSE"] == 2500.0
    assert pd.isna(cleaned_df.iloc[0]["DELIV_QTY"])
    assert pd.isna(cleaned_df.iloc[0]["DELIV_PCT"])


def test_clean_dataframe_missing_columns() -> None:
    """
    Verify cleaner raises KeyError when mandatory columns are completely missing.
    """
    downloader = BhavcopyDownloader()
    data = {"INVALID_COL": ["VAL1", "VAL2"]}
    raw_df = pd.DataFrame(data)

    with pytest.raises(KeyError, match="Mandatory columns missing"):
        downloader._clean_dataframe(raw_df)


def test_process_bhavcopy_success(tmp_path: Path) -> None:
    """
    Verify complete pipeline from ZIP file to generating sorted records.
    """
    raw_dir: str = str(tmp_path / "raw")
    processed_dir: str = str(tmp_path / "processed")
    downloader = BhavcopyDownloader(
        raw_dir=raw_dir, processed_dir=processed_dir, top_n=2
    )

    test_date: datetime = datetime(2026, 5, 26)
    zip_bytes: bytes = _create_mock_zip(columns_mode="standard")

    result: list[list[str | float]] = downloader.process_bhavcopy(test_date, zip_bytes)

    # Sorted by turnover descending: TCS, INFY
    assert len(result) == 2
    assert result[0] == ["TCS", 2000.0, 3200.0, 1000.0, 50.0]
    assert result[1] == ["INFY", 1500.0, 1500.0, 700.0, 46.6]

    # Check that processed CSV exists on disk
    expected_csv_path: str = os.path.join(processed_dir, "top_2_20260526.csv")
    assert os.path.exists(expected_csv_path)

    # Read saved file to confirm accuracy
    saved_df = pd.read_csv(expected_csv_path)
    assert list(saved_df.columns) == [
        "SYMBOL",
        "TURNOVER",
        "CLOSE",
        "DELIV_QTY",
        "DELIV_PCT",
    ]
    assert len(saved_df) == 2
    assert saved_df.iloc[0]["SYMBOL"] == "TCS"
    assert saved_df.iloc[0]["DELIV_QTY"] == 1000.0
    assert saved_df.iloc[0]["DELIV_PCT"] == 50.0
    assert saved_df.iloc[1]["SYMBOL"] == "INFY"
    assert saved_df.iloc[1]["DELIV_QTY"] == 700.0
    assert saved_df.iloc[1]["DELIV_PCT"] == 46.6


def test_clean_dataframe_turnover_lacs() -> None:
    """
    Verify turnover normalization multiplies TURNOVER_LACS values by 100,000.
    """
    downloader = BhavcopyDownloader()
    data = {
        "SYMBOL": ["RELIANCE", "TCS"],
        "SERIES": ["EQ", "EQ"],
        "CLOSE": [2500.0, 3200.0],
        "TURNOVER_LACS": [10.0, 20.0],
    }
    raw_df = pd.DataFrame(data)

    cleaned_df: pd.DataFrame = downloader._clean_dataframe(raw_df)

    assert cleaned_df.iloc[0]["TURNOVER"] == 1_000_000.0
    assert cleaned_df.iloc[1]["TURNOVER"] == 2_000_000.0


def test_clean_dataframe_etf_boundaries() -> None:
    """
    Verify precise ETF regex patterns correctly filter out ETFs
    without accidentally removing legitimate equity symbols like GOLDIAM.
    """
    downloader = BhavcopyDownloader()
    data = {
        "SYMBOL": ["GOLDIAM", "LIQUIDFLEX", "GOLD", "LIQUID", "GOLD-BEES", "NIFTY-ETF"],
        "SERIES": ["EQ", "EQ", "EQ", "EQ", "EQ", "EQ"],
        "CLOSE": [100.0, 200.0, 300.0, 400.0, 500.0, 600.0],
        "TURNOVER": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
    }
    raw_df = pd.DataFrame(data)

    cleaned_df: pd.DataFrame = downloader._clean_dataframe(raw_df)

    # Legitimate equities (GOLDIAM, LIQUIDFLEX) must be preserved.
    # ETFs (GOLD, LIQUID, GOLD-BEES, NIFTY-ETF) must be filtered.
    symbols_present = cleaned_df["SYMBOL"].tolist()
    assert "GOLDIAM" in symbols_present
    assert "LIQUIDFLEX" in symbols_present
    assert "GOLD" not in symbols_present
    assert "LIQUID" not in symbols_present
    assert "GOLD-BEES" not in symbols_present
    assert "NIFTY-ETF" not in symbols_present


def test_process_bhavcopy_invalid_magic_bytes() -> None:
    """
    Verify process_bhavcopy raises BadZipFile if magic bytes PK\\x03\\x04 are missing.
    """
    downloader = BhavcopyDownloader()
    test_date = datetime(2026, 5, 26)
    bad_bytes = b"NOT_A_ZIP_FILE"

    with pytest.raises(zipfile.BadZipFile, match="Invalid raw ZIP file bytes"):
        downloader.process_bhavcopy(test_date, bad_bytes)


def test_process_bhavcopy_no_csv() -> None:
    """
    Verify process_bhavcopy raises ValueError if ZIP archive has no CSV file.
    """
    downloader = BhavcopyDownloader()
    test_date = datetime(2026, 5, 26)

    # Create a valid ZIP archive without a CSV file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        z.writestr("test.txt", "some dummy content")
    zip_bytes = zip_buffer.getvalue()

    with pytest.raises(ValueError, match="No CSV file found in Zip archive"):
        downloader.process_bhavcopy(test_date, zip_bytes)
