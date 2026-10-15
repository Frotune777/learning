"""
File: src/classes/PersistenceService.py
Purpose: Unified service for managing result persistence and user-facing exports.

Dependencies:
External:
- pandas>=2.0.0: [data handling and parquet/csv serialization]
- json: [standard json export format]
- datetime: [timestamping files and metadata]
- pathlib: [platform-independent path handling]
Internal:
- N/A

Key Components:
Classes:
- PersistenceService: Static utility class for storing and loading scan results.
Functions:
- save_results: Main entry point for saving data in multiple formats.
- load_last_results: Load the most recent scan from persistent storage.
- clear_persistence: Reset the state of the last scanned results.

Last Modified: 2026-02-19
Modified By: LLM

Open Tasks:
- [ ] [MEDIUM] Implement data encryption for sensitive exports [5h]
- [ ] [LOW] Add S3/Dropbox sink for cloud exports [8h]

Related Files:
- src/classes/Screener.py: [generates results for persistence]
- src/classes/ReportingService.py: [uses persistent results for display]
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd


class PersistenceService:
    """
    Handles storage and retrieval of screening results in various formats.

    Design Pattern: Singleton/Utility - primarily static methods for IO.

    Attributes:
        RESULTS_DIR (Path): Root directory for all exported files | user_data/results
        PERSISTENCE_FILE (Path): File for tracking last scan state | last_screened_results_v1.parquet

    Public Methods:
        - save_results(results, scan_name, ...): Exports data to disk.
        - load_last_results(): Returns a DataFrame from the persistence file.
        - clear_persistence(): Deletes current persistence state.

    Private Methods:
        - _validate_schema(df): Ensures basic column compliance.
        - _remove_color(text): Sanitizes strings for flat-file exports.
        - _save_to_csv(df, scan_name): Low-level CSV writer.

    Usage Flow:
        1. Access PersistenceService.save_results(df, "Nifty 50")
        2. Results are saved to Parquet (state) and CSV (user)
        3. App reloads and calls load_last_results() to restore UI state.

    State Management:
        - Valid states: Persistence file exists | Missing
        - State transitions: Created on save_results | Deleted on clear_persistence

    Thread Safety: Partial - Atomic file writes used where possible, but concurrent IO may collide.

    Dependencies:
        External: pandas, json
        Internal: N/A
    """

    RESULTS_DIR = Path("user_data/results")
    PERSISTENCE_FILE = Path("last_screened_results_v1.parquet")
    REQUIRED_COLUMNS = ["Stock", "Score", "Signal", "LTP"]

    @staticmethod
    def save_results(
        results: Union[List[Dict[str, Any]], pd.DataFrame],
        scan_name: str = "Stock Scan",
        formats: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        Orchestrate the saving of scan results across multiple formats.

        Logic:
            Step 1: Normalize input to a pandas DataFrame.
            Step 2: Ensure the results directory exists.
            Step 3: Inject metadata (version, timestamp) into the DataFrame.
            Step 4: Execute writers for each requested format (Parquet, CSV, JSON).

        Parameters:
            results (Union[List, pd.DataFrame]): Input data to store.
            scan_name (str): Human-readable name used for filenames.
            formats (Optional[List[str]]): Target formats (default: csv, parquet).

        Returns:
            Dict[str, str]: Mapping of formats to their relative file paths.

        Example:
            >>> paths = PersistenceService.save_results(my_df, "Breakout_Scan")
            >>> print(paths['csv'])
            'user_data/results/scanner_breakout_scan_20230101.csv'

        Performance:
            Time Complexity: O(N) [where N is rows in the dataset]
            Space Complexity: O(N) [requires copy of DF for cleaning]
        """
        if formats is None:
            formats = ["csv", "parquet"]

        if results is None:
            return {}

        if isinstance(results, list):
            df = pd.DataFrame(results)
        else:
            df = results.copy()

        if df.empty:
            print(f"ℹ️  No results to save for {scan_name}")
            PersistenceService.clear_persistence()
            return {}

        PersistenceService.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        export_paths = {}

        df["_meta_version"] = "1.0"
        df["_meta_timestamp"] = datetime.now().isoformat()

        # 1. Parquet (Persistence)
        if "parquet" in formats:
            try:
                # A. Transient Persistence (Current State)
                df.to_parquet(PersistenceService.PERSISTENCE_FILE, index=False)
                export_paths["persistence"] = str(PersistenceService.PERSISTENCE_FILE)

                # B. User Export (Timestamped)
                path = PersistenceService._save_to_parquet(df, scan_name)
                if path:
                    export_paths["parquet"] = path
            except Exception as e:
                print(f"⚠️  Failed to update persistence: {e}")

        # 2. CSV (User Export)
        if "csv" in formats:
            path = PersistenceService._save_to_csv(df, scan_name)
            if path:
                export_paths["csv"] = path

        # 3. JSON (User Export)
        if "json" in formats:
            path = PersistenceService.save_results_json(df, scan_name)
            if path:
                export_paths["json"] = path

        return export_paths

    @staticmethod
    def save_results_json(df: pd.DataFrame, scan_name: str) -> Optional[str]:
        """
        Export scan results specifically to a JSON format with structured metadata.

        Parameters:
            df (pd.DataFrame): Data to export.
            scan_name (str): Label for the scan.

        Returns:
            Optional[str]: Absolute path to the saved JSON file.
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = scan_name.replace(" ", "_").lower()
            filename = (
                PersistenceService.RESULTS_DIR / f"scanner_{safe_name}_{timestamp}.json"
            )

            export_df = df.copy()
            if "_meta_version" in export_df.columns:
                export_df = export_df.drop(columns=["_meta_version", "_meta_timestamp"])

            clean_records = export_df.to_dict("records")
            output = {
                "metadata": {
                    "scan_name": scan_name,
                    "timestamp": datetime.now().isoformat(),
                    "row_count": len(clean_records),
                },
                "results": clean_records,
            }

            with open(filename, "w") as f:
                json.dump(output, f, indent=2, default=str)

            print(f"✅ exported to: {filename}")
            return str(filename)
        except Exception as e:
            print(f"⚠️  JSON Export failed: {e}")
            return None

    @staticmethod
    def _validate_schema(df: pd.DataFrame) -> bool:
        """
        Verify that the DataFrame complies with minimum operational schema.

        Parameters:
            df (pd.DataFrame): DataFrame to check.

        Returns:
            bool: True if schema is valid.
        """
        missing = [
            col for col in PersistenceService.REQUIRED_COLUMNS if col not in df.columns
        ]
        return not bool(missing)

    @staticmethod
    def _remove_color(text: Any) -> Any:
        """
        Strip ANSI escape sequences (colors) from string values.

        Parameters:
            text (Any): Input object, processed if string.

        Returns:
            Any: Cleaned text or original object.
        """
        if isinstance(text, str):
            ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
            return ansi_escape.sub("", text)
        return text

    @staticmethod
    def _save_to_parquet(df: pd.DataFrame, scan_name: str) -> Optional[str]:
        """
        Export scan results to a timestamped Parquet file for analytics.

        Parameters:
            df (pd.DataFrame): Data to save.
            scan_name (str): Scan label.

        Returns:
            Optional[str]: Path to file.
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = scan_name.replace(" ", "_").lower()
            filename = (
                PersistenceService.RESULTS_DIR
                / f"scanner_{safe_name}_{timestamp}.parquet"
            )

            export_df = df.copy()
            if "_meta_version" in export_df.columns:
                export_df = export_df.drop(columns=["_meta_version", "_meta_timestamp"])

            # Stripping CLI colors might not be necessary for Parquet but good for consistency
            df_clean = export_df.map(PersistenceService._remove_color)
            df_clean.to_parquet(filename, index=False)
            print(f"✅ exported to: {filename}")
            return str(filename)
        except Exception as e:
            print(f"⚠️  Parquet Export failed: {e}")
            return None

    @staticmethod
    def _save_to_csv(df: pd.DataFrame, scan_name: str) -> Optional[str]:
        """
        Low-level handler for CSV serialization.

        Parameters:
            df (pd.DataFrame): Data to save.
            scan_name (str): Scan label.

        Returns:
            Optional[str]: Path to file.
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = scan_name.replace(" ", "_").lower()
            filename = (
                PersistenceService.RESULTS_DIR / f"scanner_{safe_name}_{timestamp}.csv"
            )

            export_df = df.copy()
            if "_meta_version" in export_df.columns:
                export_df = export_df.drop(columns=["_meta_version", "_meta_timestamp"])

            # Map the cleaning function over the DataFrame
            df_clean = export_df.map(PersistenceService._remove_color)
            df_clean.to_csv(filename, index=False)
            print(f"✅ exported to: {filename}")
            return str(filename)
        except Exception as e:
            print(f"⚠️  CSV Export failed: {e}")
            return None

    @staticmethod
    def load_last_results() -> pd.DataFrame:
        """
        Reload the results from the most recent persistent Parquet file.

        Returns:
            pd.DataFrame: Loaded results or empty DataFrame if not found.
        """
        if PersistenceService.PERSISTENCE_FILE.exists():
            try:
                return pd.read_parquet(PersistenceService.PERSISTENCE_FILE)
            except Exception as e:
                print(f"Error loading persistence: {e}")
        return pd.DataFrame()

    @staticmethod
    def clear_persistence() -> None:
        """
        Clear the persistent state and reset the file to an empty schema.
        """
        if PersistenceService.PERSISTENCE_FILE.exists():
            try:
                os.remove(PersistenceService.PERSISTENCE_FILE)
                # Re-initialize with header schema
                df = pd.DataFrame(columns=["Stock", "Status", "_meta_version"])
                df.to_parquet(PersistenceService.PERSISTENCE_FILE)
            except Exception:
                pass
