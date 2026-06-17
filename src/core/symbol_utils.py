"""
File: src/core/symbol_utils.py
Purpose: Shared symbol-loading and file-discovery utilities used by CLI actions and menus.
Last Modified: 2026-05-31
"""

import glob
import logging
import os
import re
import sys
from datetime import datetime

import pandas as pd

LOGGER = logging.getLogger("nse_pipeline")


# ---------------------------------------------------------------------------
# File discovery helpers
# ---------------------------------------------------------------------------


def find_latest_master(data_dir: str = "data") -> str | None:
    """
    Find the most recently dated equity master Parquet file in data_dir.

    Parameters:
        data_dir (str): Directory to search. | Default: "data"

    Returns:
        str | None: Path to latest master Parquet, or None if not found.

    Complexity:
        Time: O(F) [F = matching files]
        Space: O(F)

    Example:
        >>> path = find_latest_master()
    """
    pattern = os.path.join(data_dir, "nse_equity_master_*.parquet")
    files = sorted(glob.glob(pattern), reverse=True)
    return files[0] if files else None


def find_latest_raw_zip(raw_dir: str = "data/raw") -> str | None:
    """
    Find the most recently dated Bhavcopy ZIP in raw_dir.

    Parameters:
        raw_dir (str): Raw data directory. | Default: "data/raw"

    Returns:
        str | None: Path to latest raw ZIP, or None if not found.

    Complexity:
        Time: O(F)
        Space: O(F)

    Example:
        >>> path = find_latest_raw_zip()
    """
    pattern = os.path.join(raw_dir, "BhavCopy_NSE_CM_*.zip")
    files = sorted(glob.glob(pattern), reverse=True)
    return files[0] if files else None


# ---------------------------------------------------------------------------
# Symbol loading helpers
# ---------------------------------------------------------------------------


def load_symbols(
    master_path: str | None,
    cap_filter: str | None = None,
    index_filter: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """
    Load symbol list from master Parquet with optional filters
    (soft — returns [] on error).

    Parameters:
        master_path (str | None): Path to master Parquet. | None returns empty list.
        cap_filter (str | None): "Large", "Mid", "Small", "Other". | Default None.
        index_filter (str | None): Column like "is_nifty_50". | Default None.
        limit (int | None): Max symbols to return. | Default None (all).

    Returns:
        list[str]: Filtered and sorted symbol list (empty on any error).

    Complexity:
        Time: O(N)
        Space: O(N)

    Example:
        >>> syms = load_symbols("data/nse_equity_master_20260531.parquet")
    """
    if master_path is None or not os.path.exists(master_path):
        LOGGER.warning("Master not found: %s", master_path)
        return []

    try:
        df = pd.read_parquet(master_path)
    except Exception as exc:
        LOGGER.error("Failed to read master Parquet: %s", exc)
        return []

    if cap_filter and "market_cap_category" in df.columns:
        df = df[df["market_cap_category"] == cap_filter]
        LOGGER.info("Cap filter '%s': %d symbols", cap_filter, len(df))

    if index_filter:
        if index_filter in df.columns:
            df = df[df[index_filter] == True]  # noqa: E712
            LOGGER.info("Index filter '%s': %d symbols", index_filter, len(df))
        else:
            LOGGER.warning("Index column '%s' not found — ignoring.", index_filter)

    sym_col = "symbol" if "symbol" in df.columns else "Symbol"
    symbols = sorted(df[sym_col].dropna().str.strip().str.upper().tolist())
    if limit:
        symbols = symbols[:limit]
    LOGGER.info("Loaded %d symbols from master.", len(symbols))
    return symbols


def load_symbols_strict(
    master_path: str | None,
    cap_filter: str | None = None,
    index_filter: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """
    Load symbols from master Parquet — exits with error if master is
    missing (strict CLI mode).

    Parameters:
        master_path (str | None): Path to master Parquet. | None triggers sys.exit(1).
        cap_filter (str | None): Market cap category filter. | Default None.
        index_filter (str | None): Index membership column filter. | Default None.
        limit (int | None): Max symbols to return. | Default None.

    Returns:
        list[str]: Filtered and sorted symbol list.

    Raises:
        SystemExit: If master_path is None or file unreadable.

    Complexity:
        Time: O(N)
        Space: O(N)

    Example:
        >>> syms = load_symbols_strict("data/nse_equity_master_20260531.parquet")
    """
    if master_path is None:
        LOGGER.error("No master table found. Run 'build-master' first.")
        sys.exit(1)

    symbols = load_symbols(master_path, cap_filter, index_filter, limit)
    if not symbols:
        LOGGER.error("Master found but returned zero symbols — check filters.")
        sys.exit(1)
    return symbols


def load_symbols_from_bhavcopy(
    raw_dir: str,
    cap_filter: str | None = None,
    index_filter: str | None = None,
    master_path: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """
    Load EQ symbols from the latest Bhavcopy ZIP with optional master
    intersection filters.

    Parameters:
        raw_dir (str): Directory containing raw Bhavcopy ZIPs. | Writable path.
        cap_filter (str | None): Market cap filter applied via master intersection.
        index_filter (str | None): Index column filter applied via master.
        master_path (str | None): Path to master Parquet for intersection filters.
        limit (int | None): Max symbols to return.

    Returns:
        list[str]: Sorted EQ symbols that traded in the latest Bhavcopy.

    Raises:
        SystemExit: If no raw ZIP found.

    Complexity:
        Time: O(N)
        Space: O(N)

    Example:
        >>> syms = load_symbols_from_bhavcopy("data/raw")
        >>> print(len(syms))  # ~1800
    """
    from src.storage.downloader import BhavcopyDownloader

    zip_path = find_latest_raw_zip(raw_dir)
    if zip_path is None:
        LOGGER.error(
            "No Bhavcopy ZIP found in '%s'. Run 'build-master' first "
            "or use --source master.",
            raw_dir,
        )
        sys.exit(1)

    LOGGER.info("Loading EQ symbols from Bhavcopy ZIP: %s", zip_path)
    with open(zip_path, "rb") as fh:
        file_bytes = fh.read()

    dl = BhavcopyDownloader(raw_dir=raw_dir)
    symbols = dl.get_eq_symbols(file_bytes)
    LOGGER.info("Bhavcopy EQ symbols: %d", len(symbols))

    if (cap_filter or index_filter) and master_path:
        master_symbols = set(load_symbols(master_path, cap_filter, index_filter))
        before = len(symbols)
        symbols = [s for s in symbols if s in master_symbols]
        LOGGER.info("After filter intersection: %d (from %d)", len(symbols), before)

    if limit:
        symbols = symbols[:limit]
    LOGGER.info("Using %d symbols for sync.", len(symbols))
    return symbols


def get_delivery_history_from_bhavcopy(
    processed_dir: str,
    symbol: str,
) -> pd.DataFrame | None:
    """
    Aggregate delivery percentage history from processed Bhavcopy top_250 CSV files.

    Parameters:
        processed_dir (str): Directory containing top_250_*.csv files. | Must exist.
        symbol (str): Ticker symbol to look up. | Case-insensitive.

    Returns:
        pd.DataFrame | None: DataFrame with Date and DELIV_PCT columns, or None.

    Complexity:
        Time: O(F * N) [F = files, N = rows per file]
        Space: O(F)

    Example:
        >>> df = get_delivery_history_from_bhavcopy("data/processed", "TCS")
    """
    rows: list[dict] = []
    pattern = os.path.join(processed_dir, "top_250_*.csv")
    for path in glob.glob(pattern):
        if "analyzed" in path:
            continue
        filename = os.path.basename(path)
        match = re.search(r"top_250_(\d{8})\.csv", filename)
        if match:
            date_str = match.group(1)
            try:
                dt = datetime.strptime(date_str, "%Y%m%d")
                df = pd.read_csv(path)
                if "SYMBOL" in df.columns and "DELIV_PCT" in df.columns:
                    row_slice = df[df["SYMBOL"].str.upper() == symbol.upper()]
                    if not row_slice.empty:
                        deliv_pct = float(row_slice["DELIV_PCT"].values[0])
                        rows.append({"Date": dt, "DELIV_PCT": deliv_pct})
            except Exception:
                continue
    if rows:
        return pd.DataFrame(rows).sort_values("Date")
    return None


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def combine_strings(values: object) -> str:
    """
    Join non-null string values with ' | ' separator for grouped DataFrame aggregation.

    Parameters:
        values (object): Iterable of values (may include NaN). | Any iterable.

    Returns:
        str: ' | ' separated string of non-null values.

    Complexity:
        Time: O(N)
        Space: O(N)

    Example:
        >>> combine_strings(["Buy", None, "Sell"])
        'Buy | Sell'
    """
    return " | ".join(str(v) for v in values if pd.notna(v))
