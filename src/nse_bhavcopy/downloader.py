"""
File: src/nse_bhavcopy/downloader.py
Purpose: Download and process National Stock Exchange (NSE) Bhavcopy files.

Dependencies:
External:
- pandas>=2.2.3: Clean and filter stock records, sort by turnover
- requests>=2.32.3: Make HTTP requests to download files from NSE archive
Internal:
- None

Key Components:
Classes:
- BhavcopyDownloader: Orchestrator for downloading and processing NSE Bhavcopies.
Functions:
- None

Last Modified: 2026-05-26
Modified By: Fortune

Open Tasks:
- [ ] [LOW] Add support for custom column configurations via env (2h)

Related Files:
- lerarning.py: Script running the downloader back to a valid trading day.
- tests/test_downloader.py: Unit tests covering downloader logic.
"""

import io
import logging
import os
import zipfile
from datetime import datetime

import pandas as pd
import requests

# Initialize institutional logger
LOGGER: logging.Logger = logging.getLogger(__name__)


class BhavcopyDownloader:
    """
    Class responsible for downloading and processing NSE Bhavcopy ZIP files.

    Design Pattern: Strategy - Implements a local market data collection strategy.

    Attributes:
        raw_dir (str): Path to raw file downloads directory.
        processed_dir (str): Path to processed CSVs directory.
        top_n (int): Number of top equity stocks by turnover to keep.

    Public Methods:
        - download_raw_bhavcopy(date_obj: datetime) -> bytes: Downloads ZIP bytes.
        - save_raw_bhavcopy(date_obj: datetime, file_bytes: bytes) -> str: Saves ZIP.
        - process_bhavcopy(date_obj: datetime, file_bytes: bytes) ->
          list[list[str | float]]: Processes ZIP, filters and saves top N CSV.

    Private Methods:
        - _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame: Cleans headers/series.

    Usage Flow:
        1. Instantiate with raw_dir, processed_dir, and top_n configurations.
        2. Call download_raw_bhavcopy to fetch ZIP bytes.
        3. Call save_raw_bhavcopy to save the zip file locally.
        4. Call process_bhavcopy to filter, save, and return list representation.

    State Management:
        - Valid states: Configured, Ready
        - State transitions: Initialized -> ready to query and write.

    Thread Safety: Yes - Operations are self-contained and atomic.

    Dependencies:
        External: pandas, requests, zipfile, io, os
        Internal: None
    """

    def __init__(
        self,
        raw_dir: str = "data/raw",
        processed_dir: str = "data/processed",
        top_n: int = 250,
    ) -> None:
        """
        Initialize the BhavcopyDownloader with directories and configurations.
        Sets up local folder destinations for files.

        Logic:
            Step 1: Save directories and top N constants to attributes.
            Step 2: Create directory trees recursively if they do not exist.

        Parameters:
            raw_dir (str): Target directory for raw files. | Must be valid.
            processed_dir (str): Target directory for processed CSVs. | Must be valid.
            top_n (int): Number of top elements to retain. | Positive int, default 250.

        Returns:
            None: Void constructor return.

        Raises:
            OSError: If directory creation fails due to filesystem permissions.

        Example:
            >>> downloader = BhavcopyDownloader("data/raw", "data/processed", 250)

        Performance:
            Time Complexity: O(1) [Directory creation is independent of input size]
            Space Complexity: O(1) [Minimal attribute storage]

        Edge Cases Handled:
            - Target directories already exist (handled gracefully via exist_ok=True).
            - Empty strings passed as directories (throws error in os.makedirs).

        TODO:
            - [ ] Allow reading configs from pyproject.toml (MEDIUM 2h)

        Notes:
            Paths can be absolute or relative to execution path.
        """
        self.raw_dir: str = raw_dir
        self.processed_dir: str = processed_dir
        self.top_n: int = top_n

        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
        LOGGER.info(
            "Initialized downloader with raw: %s, processed: %s",
            self.raw_dir,
            self.processed_dir,
        )

    def download_raw_bhavcopy(self, date_obj: datetime) -> bytes:
        """
        Download raw Bhavcopy zip bytes from official NSE archives.
        Fetches ZIP archives from the official nseindia archives.

        Logic:
            Step 1: Generate date string and URL for NSE CM archives.
            Step 2: Initialize headers to bypass server blocking.
            Step 3: Perform GET request with a 20-second timeout.
            Step 4: Return content if HTTP 200, raise exception otherwise.

        Parameters:
            date_obj (datetime): Date instance to download. | Valid past/present date.

        Returns:
            bytes: Binary content of the downloaded ZIP archive.

        Raises:
            requests.exceptions.RequestException: If the network request fails.
            ValueError: If the response status code is not 200.

        Example:
            >>> downloader = BhavcopyDownloader()
            >>> # bytes_data = downloader.download_raw_bhavcopy(datetime(2026, 5, 26))

        Performance:
            Time Complexity: O(N) [Bounded by network latency and payload transfer size]
            Space Complexity: O(M) [Memory scale proportional to ZIP size, ~3-4MB]

        Edge Cases Handled:
            - Non-200 HTTP status (raises ValueError with status detail).
            - Network dropouts (handled via standard request timeout exceptions).

        TODO:
            - [ ] Implement request retries with exponential backoff (HIGH 3h)

        Notes:
            The official NSE archive domain used is nsearchives.nseindia.com.
        """
        date_str: str = date_obj.strftime("%Y%m%d")
        url: str = (
            f"https://nsearchives.nseindia.com/content/cm/"
            f"BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
        )
        headers: dict[str, str] = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/webp,*/*;q=0.8"
            ),
        }

        LOGGER.info("Checking file for date: %s", date_str)
        response: requests.Response = requests.get(url, headers=headers, timeout=20)

        if response.status_code != 200:
            LOGGER.warning(
                "Failed to fetch Bhavcopy for date %s, Status: %d",
                date_str,
                response.status_code,
            )
            raise ValueError(
                f"File not found on NSE. HTTP status: {response.status_code}"
            )

        LOGGER.info("Successfully fetched %d bytes from NSE", len(response.content))
        return response.content

    def save_raw_bhavcopy(self, date_obj: datetime, file_bytes: bytes) -> str:
        """
        Save raw downloaded ZIP file bytes to the configured directory.
        Saves the file to local disk for record keeping.

        Logic:
            Step 1: Build the output file name using the date string.
            Step 2: Write binary file to the raw downloads directory.
            Step 3: Return the absolute file path.

        Parameters:
            date_obj (datetime): Date of the Bhavcopy. | Must be valid datetime.
            file_bytes (bytes): ZIP archive binary content. | Non-empty bytes.

        Returns:
            str: Path to the saved zip file.

        Raises:
            OSError: If writing to the filesystem fails.

        Example:
            >>> downloader = BhavcopyDownloader()
            >>> # path = downloader.save_raw_bhavcopy(datetime(2026, 5, 26), raw_bytes)

        Performance:
            Time Complexity: O(M) [Linear write operation depending on file size M]
            Space Complexity: O(1) [No memory structures instantiated during write]

        Edge Cases Handled:
            - Empty file bytes (writes empty ZIP file to disk).
            - Read-only partition or disk full (throws OSError).

        TODO:
            - [ ] Validate zip integrity before saving (MEDIUM 1.5h)

        Notes:
            Files are saved using the exact date format in the file name.
        """
        date_str: str = date_obj.strftime("%Y%m%d")
        filename: str = f"BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
        filepath: str = os.path.join(self.raw_dir, filename)

        with open(filepath, "wb") as f:
            f.write(file_bytes)

        LOGGER.info("Raw zip saved locally at: %s", filepath)
        return filepath

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and normalize raw Bhavcopy DataFrame structures.
        Strips whitespace, extracts equity series and strips non-equity keywords.

        Logic:
            Step 1: Strip whitespaces from column headers.
            Step 2: Locate standard columns (symbol, series, turnover, close).
            Step 3: Filter rows containing series EQ and reject ETFs/Bees.
            Step 4: Clean turnover formats and drop invalid NaN lines.

        Parameters:
            df (pd.DataFrame): Raw parsed CSV pandas dataframe. | Must have columns.

        Returns:
            pd.DataFrame: Cleaned and structured pandas dataframe.

        Raises:
            KeyError: If mandatory columns like symbol, close, or turnover are missing.

        Example:
            >>> downloader = BhavcopyDownloader()
            >>> # clean_df = downloader._clean_dataframe(raw_df)

        Performance:
            Time Complexity: O(N) [Iterates rows to filter and clean series]
            Space Complexity: O(N) [Duplicates DataFrame with subsets]

        Edge Cases Handled:
            - Alternate column headers 'TckrSymb' vs 'SYMBOL'.
            - Missing 'SERIES' or 'SctySrs' columns (treated as warning and bypassed).

        TODO:
            - [ ] Handle new or custom stock suffix exclusions (MEDIUM 2h)

        Notes:
            Bhavcopy layouts were slightly changed by NSE; this handles both formats.
        """
        df.columns = [c.strip() for c in df.columns]

        sym_col: str | None = next(
            (c for c in ["TckrSymb", "SYMBOL"] if c in df.columns), None
        )
        close_col: str | None = next(
            (c for c in ["ClsPric", "CLOSE"] if c in df.columns), None
        )
        series_col: str | None = next(
            (c for c in ["SctySrs", "SERIES"] if c in df.columns), None
        )
        turnover_col: str | None = next(
            (
                c
                for c in ["TtlTrfVal", "TtlTrdVal", "TURNOVER_LACS", "TURNOVER"]
                if c in df.columns
            ),
            None,
        )

        deliv_qty_col: str | None = next(
            (
                c
                for c in ["DlvrbleQty", "DELIV_QTY", "1S_DELIV_QTY", "DELIVERABLE_QTY"]
                if c in df.columns
            ),
            None,
        )
        deliv_pct_col: str | None = next(
            (
                c
                for c in [
                    "PctOfDlvrbleQtyTltTrdQty",
                    "DELIV_PCT",
                    "1S_DELIV_PCT",
                    "DELIVERABLE_PCT",
                ]
                if c in df.columns
            ),
            None,
        )

        if not sym_col or not close_col or not turnover_col:
            missing: list[str] = []
            if not sym_col:
                missing.append("SYMBOL")
            if not close_col:
                missing.append("CLOSE")
            if not turnover_col:
                missing.append("TURNOVER")
            LOGGER.error("Missing mandatory columns: %s", missing)
            raise KeyError(f"Mandatory columns missing: {missing}")

        # Filter for Eq Series only
        if series_col:
            df = df[df[series_col].astype(str).str.strip() == "EQ"]

        # Filter out ETFs, Bees and gold keywords using exact boundary patterns
        filter_pattern: str = r"(?:BEES|ETF)$|^(?:GOLD|LIQUID)$"
        df = df[
            ~df[sym_col]
            .astype(str)
            .str.contains(filter_pattern, case=False, na=False, regex=True)
        ]

        # Convert turnover to numeric safely
        df = df.copy()
        df[turnover_col] = pd.to_numeric(df[turnover_col], errors="coerce")
        if turnover_col == "TURNOVER_LACS":
            df[turnover_col] = df[turnover_col] * 100_000
        df = df.dropna(subset=[turnover_col])

        # Clean and convert delivery columns
        if deliv_qty_col:
            df[deliv_qty_col] = pd.to_numeric(df[deliv_qty_col], errors="coerce")
        else:
            df["DELIV_QTY"] = float("nan")

        if deliv_pct_col:
            df[deliv_pct_col] = pd.to_numeric(df[deliv_pct_col], errors="coerce")
        else:
            df["DELIV_PCT"] = float("nan")

        # Rename standard columns for clean English CSV output
        rename_dict: dict[str, str] = {
            sym_col: "SYMBOL",
            turnover_col: "TURNOVER",
            close_col: "CLOSE",
        }
        if deliv_qty_col:
            rename_dict[deliv_qty_col] = "DELIV_QTY"
        if deliv_pct_col:
            rename_dict[deliv_pct_col] = "DELIV_PCT"

        df = df.rename(columns=rename_dict)

        return df[["SYMBOL", "TURNOVER", "CLOSE", "DELIV_QTY", "DELIV_PCT"]]

    def process_bhavcopy(
        self, date_obj: datetime, file_bytes: bytes
    ) -> list[list[str | float]]:
        """
        Process the downloaded raw ZIP file, clean its data, sort it,
        and save the output.
        Saves a local CSV file of the top equity stocks.

        Logic:
            Step 1: Verify ZIP file magic bytes.
            Step 2: Open ZIP byte array in-memory using ZipFile.
            Step 3: Find and read CSV contents into pandas DataFrame.
            Step 4: Call private _clean_dataframe method to extract relevant columns.
            Step 5: Sort values by turnover in descending order and slice top N records.
            Step 6: Write the processed DataFrame to CSV in data/processed/.
            Step 7: Return the raw values as a nested list for caller consumption.

        Parameters:
            date_obj (datetime): Date of Bhavcopy data. | Valid datetime object.
            file_bytes (bytes): ZIP binary content. | Valid ZIP structure.

        Returns:
            list[list[str | float]]: Top N stocks, each element is
            [SYMBOL, TURNOVER, CLOSE].
            Example return structure:
            [
                ['RELIANCE', 12345678.9, 2450.5],
                ['TCS', 9876543.2, 3210.0]
            ]

        Raises:
            zipfile.BadZipFile: If the provided file bytes are not a valid ZIP file.
            KeyError: If mandatory headers are missing.

        Example:
            >>> downloader = BhavcopyDownloader()
            >>> # result = downloader.process_bhavcopy(datetime(2026, 5, 26), zip_bytes)

        Performance:
            Time Complexity: O(N log N) [Sorting clean list of size N]
            Space Complexity: O(N) [Memory footprint for storing final datasets]

        Edge Cases Handled:
            - Invalid zip file bytes (throws BadZipFile).
            - Empty CSV rows or records (dropna clears non-numeric turnover).

        TODO:
            - [ ] Support saving as compressed parquet files (MEDIUM 2h)

        Notes:
            Processed files are saved in data/processed directory as top_250_<date>.csv.
        """
        if not file_bytes.startswith(b"PK\x03\x04"):
            LOGGER.error("Invalid ZIP file bytes: Magic header PK\\x03\\x04 not found.")
            raise zipfile.BadZipFile("Invalid raw ZIP file bytes.")

        date_str: str = date_obj.strftime("%Y%m%d")
        processed_filename: str = f"top_{self.top_n}_{date_str}.csv"
        processed_filepath: str = os.path.join(self.processed_dir, processed_filename)

        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            csv_files: list[str] = [n for n in z.namelist() if n.endswith(".csv")]
            if not csv_files:
                LOGGER.error("No CSV file found inside Zip archive.")
                raise ValueError("No CSV file found in Zip archive.")
            csv_filename: str = csv_files[0]
            with z.open(csv_filename) as f:
                df: pd.DataFrame = pd.read_csv(f)

        cleaned_df: pd.DataFrame = self._clean_dataframe(df)

        # Sort and take top N stocks
        sorted_df: pd.DataFrame = cleaned_df.sort_values(
            by="TURNOVER", ascending=False
        ).head(self.top_n)

        # Save to local processed CSV
        sorted_df.to_csv(processed_filepath, index=False)
        LOGGER.info("Processed CSV saved locally at: %s", processed_filepath)

        # Convert to nested list
        result_list: list[list[str | float]] = sorted_df.values.tolist()
        return result_list

    def get_eq_symbols(self, file_bytes: bytes) -> list[str]:
        """
        Extract the full EQ symbol list from a Bhavcopy ZIP without top_n limit.

        Logic:
            Step 1: Open ZIP bytes and parse CSV.
            Step 2: Run _clean_dataframe to filter EQ series.
            Step 3: Return sorted uppercase list of all SYMBOL values.

        Parameters:
            file_bytes (bytes): Valid Bhavcopy ZIP binary. | Non-empty bytes.

        Returns:
            list[str]: Sorted list of all EQ symbols that traded that day.

        Raises:
            zipfile.BadZipFile: If bytes are not a valid ZIP.
            KeyError: If mandatory columns are missing.

        Example:
            >>> dl = BhavcopyDownloader()
            >>> symbols = dl.get_eq_symbols(zip_bytes)
            >>> print(len(symbols))  # ~1800

        Performance:
            Time Complexity: O(N)
            Space Complexity: O(N)

        Edge Cases Handled:
            - Returns empty list on any parse failure.
        """
        if not file_bytes.startswith(b"PK\x03\x04"):
            LOGGER.error("Invalid ZIP file bytes for get_eq_symbols.")
            raise zipfile.BadZipFile("Invalid raw ZIP file bytes.")
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                csv_files = [n for n in z.namelist() if n.endswith(".csv")]
                if not csv_files:
                    LOGGER.error("No CSV in ZIP for get_eq_symbols.")
                    return []
                with z.open(csv_files[0]) as f:
                    df: pd.DataFrame = pd.read_csv(f)
            cleaned = self._clean_dataframe(df)
            return sorted(cleaned["SYMBOL"].str.strip().str.upper().tolist())
        except Exception as exc:
            LOGGER.error("get_eq_symbols failed: %s", exc)
            return []
