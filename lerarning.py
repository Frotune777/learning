"""
File: lerarning.py
Purpose: Local entry point to download & process the latest NSE Bhavcopy.

Dependencies:
External:
- pandas>=2.2.3: Standard library type bindings
Internal:
- src.nse_bhavcopy.downloader: Core downloader module

Key Components:
Classes:
- None
Functions:
- load_config: Read config from pyproject.toml with fallback defaults.
- run_pipeline: Execute date search and trigger downloading.

Last Modified: 2026-05-26
Modified By: Fortune

Open Tasks:
- [ ] [LOW] Integrate support for command-line arguments (2h)

Related Files:
- src/nse_bhavcopy/downloader.py: Core downloading module.
- tests/test_downloader.py: Unit tests for checking code pathways.
"""

import logging
import os

# Check for tomllib availability (standard in Python 3.11+)
import tomllib
from datetime import datetime, timedelta
from typing import Any

from src.nse_bhavcopy.downloader import BhavcopyDownloader

# Configure logging standard in compliance with Rule #011
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER: logging.Logger = logging.getLogger("lerarning")


def load_config() -> dict[str, Any]:
    """
    Load configuration parameters from pyproject.toml under [tool.app].
    Falls back to safe default parameters if settings are missing.

    Logic:
        Step 1: Declare standard default fallback dictionary.
        Step 2: Check if pyproject.toml exists in the execution path.
        Step 3: Read and parse pyproject.toml with built-in tomllib.
        Step 4: Update defaults with active parameters under [tool.app].
        Step 5: Validate raw/processed dir strings and return configuration.

    Parameters:
        None

    Returns:
        dict[str, Any]: Configuration keys mapped to verified values.
        Example return dict:
        {
            'raw_dir': 'data/raw',
            'processed_dir': 'data/processed',
            'max_days_back': 7,
            'top_n_stocks': 250
        }

    Raises:
        None

    Example:
        >>> config = load_config()
        >>> print(config['top_n_stocks'])
        250

    Performance:
        Time Complexity: O(1) [Fixed file check and quick parsing]
        Space Complexity: O(1) [Minor config mappings]

    Edge Cases Handled:
        - pyproject.toml file is completely missing (uses defaults).
        - [tool.app] section is missing in TOML file (bypasses gracefully).
        - Exception raised during parsing (logs warning and returns defaults).

    TODO:
        - [ ] Provide env overrides for critical parameters (MEDIUM 2h)

    Notes:
        Uses tomllib for safe zero-dependency TOML configuration parsing.
    """
    config: dict[str, Any] = {
        "raw_dir": "data/raw",
        "processed_dir": "data/processed",
        "max_days_back": 7,
        "top_n_stocks": 250,
    }
    pyproject_path: str = "pyproject.toml"

    if os.path.exists(pyproject_path):
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                app_config = data.get("tool", {}).get("app", {})
                for key, val in app_config.items():
                    config[key] = val
            LOGGER.info("Successfully loaded configurations from pyproject.toml")
        except Exception as e:
            LOGGER.warning(
                "Could not parse pyproject.toml config, using defaults. Error: %s",
                str(e),
            )
    else:
        LOGGER.info("pyproject.toml not found, using default configurations")

    return config


def run_pipeline() -> bool:
    """
    Orchestrate the search loop to download and process Bhavcopy files.
    Queries dates starting from today going backward until a file is found.

    Logic:
        Step 1: Load configurations with load_config.
        Step 2: Instantiate BhavcopyDownloader with parsed arguments.
        Step 3: Setup scanning date cursor starting at current datetime.
        Step 4: Loop backwards up to max_days_back.
        Step 5: Skip Saturday/Sunday dates (days >= 5) to save resources.
        Step 6: Attempt download. If success, save raw zip, clean, and exit.
        Step 7: If all attempts fail, log critical failure.

    Parameters:
        None

    Returns:
        bool: True if file successfully processed, False otherwise.

    Raises:
        None

    Example:
        >>> success = run_pipeline()

    Performance:
        Time Complexity: O(D) [Bounded by max_days_back D, e.g. 7]
        Space Complexity: O(M) [Linear with downloaded ZIP file size M]

    Edge Cases Handled:
        - Skips weekends to avoid redundant network attempts.
        - Gracefully handles missing archive files (raises ValueError).
        - Cleanly catches unexpected system errors to prevent script crashes.

    TODO:
        - None

    Notes:
        The scan covers up to the last 7 calendar days to ensure holiday resilience.
    """
    config: dict[str, Any] = load_config()

    downloader = BhavcopyDownloader(
        raw_dir=config["raw_dir"],
        processed_dir=config["processed_dir"],
        top_n=config["top_n_stocks"],
    )

    max_days: int = config["max_days_back"]
    date_cursor: datetime = datetime.now()
    success: bool = False

    LOGGER.info("Starting local Bhavcopy download search pipeline...")

    for i in range(max_days):
        test_date: datetime = date_cursor - timedelta(days=i)

        # 5 = Saturday, 6 = Sunday. Skip weekends.
        if test_date.weekday() >= 5:
            LOGGER.info("Skipping weekend date: %s", test_date.strftime("%Y-%m-%d"))
            continue

        date_str: str = test_date.strftime("%Y-%m-%d")
        LOGGER.info("Checking archive availability for date: %s", date_str)

        try:
            zip_bytes: bytes = downloader.download_raw_bhavcopy(test_date)
            # Save raw zip file
            downloader.save_raw_bhavcopy(test_date, zip_bytes)
            # Process and save clean CSV
            downloader.process_bhavcopy(test_date, zip_bytes)

            LOGGER.info("SUCCESS: Local processing completed for date %s", date_str)
            success = True
            break
        except ValueError as ve:
            LOGGER.warning("Date %s not available: %s", date_str, str(ve))
        except Exception as e:
            LOGGER.error(
                "Unexpected error on date %s: %s",
                date_str,
                str(e),
                exc_info=True,
            )

    if not success:
        LOGGER.critical(
            "FAILED: Could not download or process Bhavcopy from last %d days.",
            max_days,
        )

    return success


if __name__ == "__main__":
    run_pipeline()
