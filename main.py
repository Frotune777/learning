"""
File: main.py
Purpose: Unified CLI and interactive menu for the NSE data pipeline.

Dependencies:
External:
- pandas>=2.2.3: DataFrame utilities and Parquet reading
Internal:
- src.nse_bhavcopy.equity_master: [NSEEquityMasterBuilder]
- src.nse_bhavcopy.historical_sync: [HistoricalSync]
- src.nse_bhavcopy.screener: [StockScreener]

Key Components:
Classes:
- None
Functions:
- cmd_build_master: Subcommand to build/refresh the equity master table.
- cmd_sync_history: Subcommand to sync historical Parquet files.
- cmd_screen: Subcommand to run the technical screener.
- menu_build_master: Interactive menu handler for master build.
- menu_sync_history: Interactive menu handler for history sync.
- menu_screen: Interactive menu handler for screening.
- interactive_menu: REPL-style menu loop.
- main: CLI argument parse entry point.

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- [ ] [LOW] Add --output flag to redirect CSV results [1h]
- [ ] [MEDIUM] Add --filter flag (e.g. --filter nifty50) to restrict symbols [2h]

Related Files:
- src/nse_bhavcopy/equity_master.py: Master table builder.
- src/nse_bhavcopy/historical_sync.py: Parquet CRUD sync engine.
- src/nse_bhavcopy/screener.py: Technical screening logic.
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import sys
from datetime import datetime

import pandas as pd

from src.nse_bhavcopy.downloader import BhavcopyDownloader
from src.nse_bhavcopy.equity_master import NSEEquityMasterBuilder
from src.nse_bhavcopy.historical_sync import HistoricalSync
from src.nse_bhavcopy.screener import StockScreener
from src.nse_bhavcopy.sync_registry import SyncRegistry
from src.nse_bhavcopy.ta_indicators import (
    add_ta_indicators,
    calculate_technical_score,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
LOGGER: logging.Logger = logging.getLogger("nse_pipeline")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_DATA_DIR: str = "data"
DEFAULT_HIST_DIR: str = "data/historical"
DEFAULT_MASTER_DIR: str = "data"
DEFAULT_START_DATE: str = "2000-01-01"
DEFAULT_TIMEFRAME: str = "1d"


# ===========================================================================
# Helpers
# ===========================================================================


def _find_latest_master(data_dir: str = DEFAULT_DATA_DIR) -> str | None:
    """
    Find the most recently dated master Parquet file in data_dir.

    Logic:
        Step 1: Glob for nse_equity_master_*.parquet files.
        Step 2: Sort by name (date-stamped) descending.
        Step 3: Return first match or None.

    Parameters:
        data_dir (str): Directory to search. | Default "data".

    Returns:
        str | None: Path to latest master Parquet, or None if not found.

    Raises:
        None

    Example:
        >>> path = _find_latest_master()

    Performance:
        Time Complexity: O(F) [F = number of matching files]
        Space Complexity: O(F)

    Edge Cases Handled:
        - Returns None gracefully when no master exists yet.
    """
    pattern = os.path.join(data_dir, "nse_equity_master_*.parquet")
    files = sorted(glob.glob(pattern), reverse=True)
    return files[0] if files else None


def _find_latest_raw_zip(raw_dir: str = "data/raw") -> str | None:
    """
    Find the most recently dated Bhavcopy ZIP in raw_dir.

    Logic:
        Step 1: Glob for BhavCopy_NSE_CM_*.zip files.
        Step 2: Sort by name (date-stamped) descending.
        Step 3: Return first match or None.

    Parameters:
        raw_dir (str): Raw data directory. | Default "data/raw".

    Returns:
        str | None: Path to latest raw ZIP, or None.

    Raises:
        None

    Example:
        >>> path = _find_latest_raw_zip()

    Performance:
        Time Complexity: O(F)
        Space Complexity: O(F)

    Edge Cases Handled:
        - Returns None gracefully when no ZIP exists yet.
    """
    pattern = os.path.join(raw_dir, "BhavCopy_NSE_CM_*.zip")
    files = sorted(glob.glob(pattern), reverse=True)
    return files[0] if files else None


def _load_symbols_from_bhavcopy(
    raw_dir: str,
    cap_filter: str | None = None,
    index_filter: str | None = None,
    master_path: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """
    Load EQ symbols from the latest Bhavcopy ZIP with optional master filters.

    Logic:
        Step 1: Find the latest raw Bhavcopy ZIP.
        Step 2: Extract all EQ symbols using BhavcopyDownloader.get_eq_symbols().
        Step 3: If cap_filter or index_filter given, intersect with master symbols.
        Step 4: Apply limit and return sorted list.

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

    Example:
        >>> syms = _load_symbols_from_bhavcopy("data/raw")
        >>> print(len(syms))  # ~1800

    Performance:
        Time Complexity: O(N)
        Space Complexity: O(N)

    Edge Cases Handled:
        - No ZIP found exits with clear message.
        - Filter intersection reduces to empty list — logged as warning.
    """
    zip_path = _find_latest_raw_zip(raw_dir)
    if zip_path is None:
        LOGGER.error(
            "No Bhavcopy ZIP found in '%s'. Run 'build-master' first "
            "(it downloads the Bhavcopy) or use --source master.",
            raw_dir,
        )
        sys.exit(1)

    LOGGER.info("Loading EQ symbols from Bhavcopy ZIP: %s", zip_path)
    with open(zip_path, "rb") as fh:
        file_bytes = fh.read()

    dl = BhavcopyDownloader(raw_dir=raw_dir)
    symbols = dl.get_eq_symbols(file_bytes)
    LOGGER.info("Bhavcopy EQ symbols: %d", len(symbols))

    # Optionally intersect with master filters
    if (cap_filter or index_filter) and master_path:
        master_symbols = set(_load_symbols(master_path, cap_filter, index_filter))
        before = len(symbols)
        symbols = [s for s in symbols if s in master_symbols]
        LOGGER.info("After filter intersection: %d (from %d)", len(symbols), before)

    if limit:
        symbols = symbols[:limit]
    LOGGER.info("Using %d symbols for sync.", len(symbols))
    return symbols


def _load_symbols(
    master_path: str | None,
    cap_filter: str | None = None,
    index_filter: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """
    Load symbol list from master Parquet with optional filters.

    Logic:
        Step 1: Load Parquet to DataFrame.
        Step 2: Apply market_cap_category filter if provided.
        Step 3: Apply index membership filter if provided.
        Step 4: Apply limit if provided.
        Step 5: Return sorted uppercase symbol list.

    Parameters:
        master_path (str | None): Path to master Parquet. | None raises error.
        cap_filter (str | None): "Large", "Mid", "Small", "Other". | Default None.
        index_filter (str | None): Column like "is_nifty_50". | Default None.
        limit (int | None): Max symbols to return. | Default None (all).

    Returns:
        list[str]: Filtered and sorted symbol list.

    Raises:
        SystemExit: If master_path is None (no master built yet).

    Example:
        >>> symbols = _load_symbols("data/nse_equity_master_20260527.parquet",
        ...                         cap_filter="Large")

    Performance:
        Time Complexity: O(N)
        Space Complexity: O(N)

    Edge Cases Handled:
        - Missing master file exits with informative error message.
        - Unknown filter columns logged as warning.
    """
    if master_path is None:
        LOGGER.error("No master table found. Run 'build-master' first.")
        sys.exit(1)

    df = pd.read_parquet(master_path)

    if cap_filter:
        df = df[df["market_cap_category"] == cap_filter]
        LOGGER.info("Cap filter '%s': %d symbols", cap_filter, len(df))

    if index_filter:
        if index_filter in df.columns:
            df = df[df[index_filter] == True]  # noqa: E712
            LOGGER.info("Index filter '%s': %d symbols", index_filter, len(df))
        else:
            LOGGER.warning(
                "Index column '%s' not found — ignoring filter.",
                index_filter,
            )

    symbols = sorted(df["Symbol"].dropna().str.strip().str.upper().tolist())
    if limit:
        symbols = symbols[:limit]
    LOGGER.info("Using %d symbols for operation.", len(symbols))
    return symbols


# ===========================================================================
# Subcommand handlers (non-interactive)
# ===========================================================================


def cmd_build_master(args: argparse.Namespace) -> None:
    """
    Execute the 'build-master' CLI subcommand.

    Logic:
        Step 1: Instantiate NSEEquityMasterBuilder.
        Step 2: Call build_and_save() with configured delay.
        Step 3: Print saved path.

    Parameters:
        args (argparse.Namespace): Parsed CLI args with .data_dir, .delay.

    Returns:
        None

    Raises:
        SystemExit: On RuntimeError from builder.

    Example:
        >>> cmd_build_master(args)

    Performance:
        Time Complexity: O(N * I) [N securities, I indices]
        Space Complexity: O(N)

    Edge Cases Handled:
        - RuntimeError from builder prints friendly message and exits 1.
    """
    LOGGER.info("=== PHASE 1: BUILD EQUITY MASTER ===")
    builder = NSEEquityMasterBuilder(
        output_dir=args.data_dir,
        cache_dir=os.path.join(args.data_dir, "cache"),
    )
    try:
        path = builder.build_and_save(delay=args.delay)
        print(f"\n✅ Master table saved: {path}")
    except RuntimeError as exc:
        LOGGER.error("Master build failed: %s", exc)
        sys.exit(1)


def cmd_sync_history(args: argparse.Namespace) -> None:
    """
    Execute the 'sync-history' CLI subcommand.

    Logic:
        Step 1: Choose symbol source — 'bhavcopy' (default) or 'master'.
        Step 2: Load symbol list with optional cap/index filters.
        Step 3: Instantiate HistoricalSync and call sync().
        Step 4: Print summary of successes and failures.

    Parameters:
        args (argparse.Namespace): Parsed CLI args with hist_dir, timeframe,
            start_date, cap_filter, index_filter, limit, resume, source.

    Returns:
        None

    Raises:
        SystemExit: If no symbol source found.

    Example:
        >>> cmd_sync_history(args)

    Performance:
        Time Complexity: O(S * C) [S symbols, C chunks per symbol]
        Space Complexity: O(N) peak per symbol

    Edge Cases Handled:
        - Missing Bhavcopy falls back to error with clear message.
        - Individual symbol failures tracked in result dict.
    """
    LOGGER.info("=== PHASE 2: SYNC HISTORICAL DATA ===")

    source: str = getattr(args, "source", "bhavcopy")
    raw_dir: str = os.path.join(args.data_dir, "raw")
    master_path = _find_latest_master(args.data_dir)
    cap_filter = getattr(args, "cap_filter", None)
    index_filter = getattr(args, "index_filter", None)
    limit = getattr(args, "limit", None)

    if source == "bhavcopy":
        symbols = _load_symbols_from_bhavcopy(
            raw_dir=raw_dir,
            cap_filter=cap_filter,
            index_filter=index_filter,
            master_path=master_path,
            limit=limit,
        )
    else:
        symbols = _load_symbols(
            master_path,
            cap_filter=cap_filter,
            index_filter=index_filter,
            limit=limit,
        )

    hs = HistoricalSync(
        data_dir=args.hist_dir,
        timeframe=args.timeframe,
        start_date=args.start_date,
        rate_delay=args.delay,
    )
    results = hs.sync(symbols, resume=args.resume)

    ok = sum(v for v in results.values())
    failed = [s for s, v in results.items() if not v]
    print(f"\n✅ Sync complete: {ok}/{len(symbols)} symbols succeeded.")
    if failed:
        print(f"⚠️  Failed symbols ({len(failed)}): " f"{', '.join(failed[:20])}")


def cmd_screen(args: argparse.Namespace) -> None:
    """
    Execute the 'screen' CLI subcommand.

    Logic:
        Step 1: Find latest master Parquet and load processed Bhavcopy.
        Step 2: Instantiate StockScreener with Parquet-based data dir.
        Step 3: Load symbol list with optional filters.
        Step 4: Run screen_stocks and print output file locations.

    Parameters:
        args (argparse.Namespace): Parsed CLI args with data_dir, hist_dir,
            processed_dir, cap_filter, index_filter, limit.

    Returns:
        None

    Raises:
        SystemExit: If no master or no processed Bhavcopy found.

    Example:
        >>> cmd_screen(args)

    Performance:
        Time Complexity: O(S * H) [S symbols, H history rows each]
        Space Complexity: O(S * H)

    Edge Cases Handled:
        - Missing Bhavcopy exits with message.
    """
    LOGGER.info("=== PHASE 3: STOCK SCREENING ===")

    # Find the latest processed Bhavcopy CSV
    processed_dir: str = args.processed_dir
    csv_pattern = os.path.join(processed_dir, "*.csv")
    csv_files = sorted(glob.glob(csv_pattern), reverse=True)
    if not csv_files:
        LOGGER.error(
            "No processed Bhavcopy CSV found in '%s'. " "Run 'sync-history' first.",
            processed_dir,
        )
        sys.exit(1)

    top_csv: str = csv_files[0]
    LOGGER.info("Using Bhavcopy: %s", top_csv)

    screener = StockScreener(
        processed_dir=args.hist_dir,
    )
    screener.screen_stocks(
        top_250_path=top_csv,
        date_obj=datetime.now(),
    )
    print(f"\n✅ Screening complete. Results saved to: {args.hist_dir}")


# ===========================================================================
# Interactive menu
# ===========================================================================


def _print_banner() -> None:
    """Print the application banner."""
    print("\n" + "=" * 60)
    print("    NSE DATA PIPELINE — Interactive Menu")
    print("=" * 60)


def _print_main_menu() -> None:
    """Print top-level menu options."""
    print("\n  [1] Build / Refresh Equity Master Table")
    print("  [2] Sync Historical Data (all Bhavcopy symbols)")
    print("  [3] Sync Historical Data (filtered symbols)")
    print("  [4] Run Technical Screener")
    print("  [5] Show Parquet Sync Status")
    print("  [6] Show Sync Registry (pending/failed/ok)")
    print("  [7] Advanced Technical Analysis Dashboard (Single Stock)")
    print("  [8] Recompute / Update TA Indicators on All Local Data")
    print("  [9] Exit")
    print()


def menu_build_master(data_dir: str) -> None:
    """
    Interactive handler for building the equity master table.

    Logic:
        Step 1: Ask user to confirm before starting.
        Step 2: Accept custom delay or use default.
        Step 3: Run NSEEquityMasterBuilder.build_and_save().

    Parameters:
        data_dir (str): Root data directory. | Writable path.

    Returns:
        None

    Raises:
        None

    Example:
        >>> menu_build_master("data")

    Performance:
        Time Complexity: O(N * I)
        Space Complexity: O(N)

    Edge Cases Handled:
        - User cancels at confirmation prompt.
    """
    print("\n--- Build Equity Master ---")
    print("This downloads sec_list.csv and all index constituent data.")
    confirm = input("Proceed? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    try:
        delay = float(
            input("API delay between index calls (default 1.0s): ").strip() or "1.0"
        )
    except ValueError:
        delay = 1.0

    builder = NSEEquityMasterBuilder(
        output_dir=data_dir,
        cache_dir=os.path.join(data_dir, "cache"),
    )
    try:
        path = builder.build_and_save(delay=delay)
        print(f"\n✅ Master saved: {path}")
    except RuntimeError as exc:
        print(f"\n❌ Failed: {exc}")


def menu_sync_history(
    data_dir: str,
    hist_dir: str,
    cap_filter: str | None = None,
    index_filter: str | None = None,
) -> None:
    """
    Interactive handler for syncing historical Parquet data.

    Logic:
        Step 1: Find latest master and load symbol list.
        Step 2: Apply optional cap/index filter from parameters.
        Step 3: Ask for timeframe and start_date overrides.
        Step 4: Run HistoricalSync.sync().

    Parameters:
        data_dir (str): Root data directory. | Writable path.
        hist_dir (str): Historical Parquet storage directory.
        cap_filter (str | None): Market cap category filter.
        index_filter (str | None): Index column filter.

    Returns:
        None

    Raises:
        None

    Example:
        >>> menu_sync_history("data", "data/historical", cap_filter="Large")

    Performance:
        Time Complexity: O(S * C)
        Space Complexity: O(N)

    Edge Cases Handled:
        - No master found exits with message.
        - Invalid inputs fall back to defaults.
    """
    print("\n--- Sync Historical Data ---")
    master_path = _find_latest_master(data_dir)
    symbols = _load_symbols(
        master_path, cap_filter=cap_filter, index_filter=index_filter
    )
    print(f"Symbols to sync: {len(symbols)}")

    tf = input(f"Timeframe [{DEFAULT_TIMEFRAME}]: ").strip() or DEFAULT_TIMEFRAME
    start = input(f"Start date [{DEFAULT_START_DATE}]: ").strip() or DEFAULT_START_DATE

    try:
        delay = float(
            input("Rate delay between requests (default 0.5s): ").strip() or "0.5"
        )
    except ValueError:
        delay = 0.5

    hs = HistoricalSync(
        data_dir=hist_dir,
        timeframe=tf,
        start_date=start,
        rate_delay=delay,
    )
    results = hs.sync(symbols)
    ok = sum(v for v in results.values())
    print(f"\n✅ Sync: {ok}/{len(symbols)} succeeded.")


def menu_sync_filtered(data_dir: str, hist_dir: str) -> None:
    """
    Interactive handler for syncing with user-specified filters.

    Logic:
        Step 1: Present filter options (cap, index, count limit).
        Step 2: Collect user choices.
        Step 3: Delegate to menu_sync_history with filters applied.

    Parameters:
        data_dir (str): Root data directory. | Writable path.
        hist_dir (str): Historical Parquet storage directory.

    Returns:
        None

    Raises:
        None

    Example:
        >>> menu_sync_filtered("data", "data/historical")

    Performance:
        Time Complexity: O(S * C)
        Space Complexity: O(N)

    Edge Cases Handled:
        - Invalid input uses None (no filter applied).
    """
    print("\n--- Sync Historical Data (Filtered) ---")
    print("Market Cap Filter options: Large, Mid, Small, Other, [Enter=All]")
    cap = input("Cap filter: ").strip() or None

    print("Index filter examples: is_nifty_50, is_nifty_500, [Enter=None]")
    idx = input("Index filter: ").strip() or None

    menu_sync_history(
        data_dir=data_dir,
        hist_dir=hist_dir,
        cap_filter=cap,
        index_filter=idx,
    )


def menu_screen(data_dir: str, hist_dir: str, processed_dir: str) -> None:
    """
    Interactive handler for running the technical screener.

    Logic:
        Step 1: Find latest Bhavcopy CSV in processed_dir.
        Step 2: Instantiate StockScreener and run screen_stocks.

    Parameters:
        data_dir (str): Root data directory.
        hist_dir (str): Historical Parquet directory (passed to screener).
        processed_dir (str): Directory containing processed Bhavcopy CSVs.

    Returns:
        None

    Raises:
        None

    Example:
        >>> menu_screen("data", "data/historical", "data/processed")

    Performance:
        Time Complexity: O(S * H)
        Space Complexity: O(S * H)

    Edge Cases Handled:
        - No CSV found prints error and returns.
    """
    print("\n============================================================")
    print("    RUNNING TECHNICAL SCREENER")
    print("============================================================")

    prompt = (
        "Do you want to fetch the latest historical data & "
        "update TA indicators first? [y/N]: "
    )
    update_choice = input(prompt).strip().lower()
    if update_choice == "y":
        menu_sync_filtered(data_dir, hist_dir)
        print("\n--- Continuing with Screener ---")

    csv_pattern = os.path.join(processed_dir, "*.csv")
    csv_files = sorted(glob.glob(csv_pattern), reverse=True)
    if not csv_files:
        print(f"❌ No Bhavcopy CSV found in '{processed_dir}'.")
        return

    top_csv = csv_files[0]
    print(f"  Using Reference: {os.path.basename(top_csv)}\n")

    now = datetime.now()
    screener = StockScreener(processed_dir=hist_dir)
    screener.screen_stocks(top_250_path=top_csv, date_obj=now)
    print(f"\n✅ Screening complete. Results saved in: {hist_dir}")

    date_str = now.strftime("%Y%m%d")
    final_csv = os.path.join(hist_dir, f"final_list_{date_str}.csv")
    swing_csv = os.path.join(hist_dir, f"swing_list_{date_str}.csv")
    super_csv = os.path.join(hist_dir, f"super_list_{date_str}.csv")

    while True:
        print("\n--- View Screener Results ---")
        print("  [1] Final List (Buy / Average Out)")
        print("  [2] Swing List (Start GTT)")
        print("  [3] Super List (Combined Signals)")
        print("  [4] View All")
        print("  [5] Exit Screener Menu")

        choice = input("\nSelect option [1-5]: ").strip()

        if choice == "5":
            break

        def display_csv(path: str, title: str) -> None:
            if not os.path.exists(path):
                print(f"❌ {title} not found at {path}")
                return
            df = pd.read_csv(path)
            print(f"\n=== {title} ===")
            if df.empty:
                print("No stocks met the criteria.")
            else:
                try:
                    print(df.to_markdown(index=False))
                except ImportError:
                    print(df.to_string(index=False))

        if choice in ("1", "4"):
            display_csv(final_csv, "Final Target List")
        if choice in ("2", "4"):
            display_csv(swing_csv, "Swing Trading List")
        if choice in ("3", "4"):
            display_csv(super_csv, "Super Output (The Holy Grail)")

        if choice not in ("1", "2", "3", "4", "5"):
            print("❌ Invalid option. Please select 1-5.")


def menu_status(hist_dir: str, data_dir: str) -> None:
    """
    Show sync status for all symbols in the master table.

    Logic:
        Step 1: Load master symbol list.
        Step 2: Call HistoricalSync.status() to collect Parquet stats.
        Step 3: Print a formatted summary table.

    Parameters:
        hist_dir (str): Historical Parquet root directory.
        data_dir (str): Master Parquet directory.

    Returns:
        None

    Raises:
        None

    Example:
        >>> menu_status("data/historical", "data")

    Performance:
        Time Complexity: O(S * N) [S symbols, N rows each]
        Space Complexity: O(S)

    Edge Cases Handled:
        - No master found prints a message and returns.
    """
    print("\n--- Sync Status ---")
    master_path = _find_latest_master(data_dir)
    if master_path is None:
        print("No master table found. Run 'Build Master' first.")
        return

    builder = NSEEquityMasterBuilder(output_dir=data_dir)
    symbols = builder.get_symbols(master_path)

    hs = HistoricalSync(data_dir=hist_dir)
    status_df = hs.status(symbols)

    synced = status_df[status_df["rows"] > 0]
    missing = status_df[status_df["rows"] == 0]

    print(f"\nTotal symbols in master: {len(status_df)}")
    print(f"Synced (have Parquet)  : {len(synced)}")
    print(f"Not yet synced         : {len(missing)}")

    if not synced.empty:
        print("\nTop 10 synced symbols:")
        print(
            synced.head(10)[["symbol", "rows", "first_date", "last_date"]].to_string(
                index=False
            )
        )

    if not missing.empty:
        print(f"\nFirst 10 unsynced: {missing['symbol'].head(10).tolist()}")


def menu_registry(data_dir: str, hist_dir: str) -> None:
    """
    Show the sync registry summary: pending, ok, and failed symbol counts.

    Logic:
        Step 1: Load SyncRegistry from data_dir.
        Step 2: Print status group counts.
        Step 3: Show top pending and failed symbols.

    Parameters:
        data_dir (str): Root data directory. | Writable path.
        hist_dir (str): Historical Parquet root (used for timeframe). | Writable path.

    Returns:
        None

    Raises:
        None

    Example:
        >>> menu_registry("data", "data/historical")

    Performance:
        Time Complexity: O(N)
        Space Complexity: O(N)

    Edge Cases Handled:
        - No registry file prints a helpful message.
    """
    print("\n--- Sync Registry ---")
    tf = input(f"Timeframe [{DEFAULT_TIMEFRAME}]: ").strip() or DEFAULT_TIMEFRAME
    reg = SyncRegistry(registry_dir=data_dir, timeframe=tf)
    n = reg.load()
    if n == 0:
        print("No registry found. Run a sync first.")
        return

    df = reg.summary()
    counts = df.groupby("status").size()
    print(f"\nTotal symbols in registry : {len(df)}")
    for status, cnt in counts.items():
        print(f"  {status:10s}: {cnt}")

    pending = df[df["needs_update"] & (df["status"] != "failed")]
    failed = df[df["status"] == "failed"]

    if not pending.empty:
        print("\nTop 10 pending (oldest first):")
        print(
            pending.head(10)[
                ["symbol", "status", "last_bar_date", "row_count"]
            ].to_string(index=False)
        )
    if not failed.empty:
        print(f"\nFailed symbols ({len(failed)}):")
        print(
            failed.head(10)[["symbol", "fail_count", "last_bar_date"]].to_string(
                index=False
            )
        )

    pending_queue = reg.pending_symbols()
    print(f"\nNext sync queue size: {len(pending_queue)} symbols")
    if pending_queue:
        print(f"Next 5 to sync: {pending_queue[:5]}")


def menu_ta_dashboard(hist_dir: str) -> None:
    """
    Display a beautiful, premium console dashboard for a single stock's TA.

    Parameters:
        hist_dir (str): Historical Parquet root directory.

    Returns:
        None
    """
    print("\n--- Advanced Technical Analysis Dashboard ---")
    symbol = input("  Enter NSE Symbol (e.g. TCS): ").strip().upper()
    if not symbol:
        return

    path = os.path.join(hist_dir, "1d", f"{symbol}.parquet")
    if not os.path.exists(path):
        print(f"❌ Historical data for '{symbol}' not found at: {path}")
        print("💡 Tip: Try syncing this symbol first using Option [2] or [3].")
        return

    try:
        df = pd.read_parquet(path)
        if df.empty:
            print(f"❌ Data file for '{symbol}' is empty.")
            return

        # Ensure tz-naive DatetimeIndex
        if df.index.tz is not None:
            df.index = df.index.tz_convert(None)
        else:
            df.index = pd.to_datetime(df.index)

        # Sort index to ensure last row is indeed latest date
        df = df.sort_index()

        # Ensure TA columns exist
        if "RSI_14" not in df.columns:
            print("  Pre-calculated technical columns not found. Computing...")
            df = add_ta_indicators(df)

        row = df.iloc[-1]
        date_str = df.index[-1].strftime("%Y-%m-%d")

        cmp = float(row.get("Close", 0.0))
        high = float(row.get("High", 0.0))
        low = float(row.get("Low", 0.0))
        volume = float(row.get("Volume", 0.0))

        # Calculate daily change %
        if len(df) >= 2:
            prev_cmp = float(df["Close"].iloc[-2])
            change_pct = ((cmp - prev_cmp) / prev_cmp) * 100.0 if prev_cmp > 0 else 0.0
        else:
            change_pct = 0.0

        # Retrieve TA indicators
        ema_20 = row.get("EMA_20")
        sma_50 = row.get("SMA_50")
        sma_200 = row.get("SMA_200")
        rsi = row.get("RSI_14")
        macd = row.get("MACD")
        macd_sig = row.get("MACD_SIGNAL")
        macd_hist = row.get("MACD_HIST")
        bb_up = row.get("BB_UPPER")
        bb_mid = row.get("BB_MIDDLE")
        bb_low = row.get("BB_LOWER")
        adx = row.get("ADX_14")
        atr = row.get("ATR_14")
        cci = row.get("CCI_14")

        # Trend helpers
        ema_20_str = f"{ema_20:,.2f}" if not pd.isna(ema_20) else "N/A"
        sma_50_str = f"{sma_50:,.2f}" if not pd.isna(sma_50) else "N/A"
        sma_200_str = f"{sma_200:,.2f}" if not pd.isna(sma_200) else "N/A"

        ema_comp = "ABOVE" if ema_20 and cmp > float(ema_20) else "BELOW"
        sma_50_comp = "ABOVE" if sma_50 and cmp > float(sma_50) else "BELOW"
        sma_200_comp = "ABOVE" if sma_200 and cmp > float(sma_200) else "BELOW"

        # RSI Helper
        if pd.isna(rsi):
            rsi_str, rsi_desc = "N/A", "N/A"
        else:
            rsi_val = float(rsi)
            rsi_str = f"{rsi_val:.2f}"
            if rsi_val >= 70.0:
                rsi_desc = "OVERBOUGHT (Caution)"
            elif rsi_val <= 30.0:
                rsi_desc = "OVERSOLD (Rebound candidate)"
            elif 50.0 <= rsi_val < 70.0:
                rsi_desc = "BULLISH (Strong)"
            elif 40.0 <= rsi_val < 50.0:
                rsi_desc = "NEUTRAL-BULLISH"
            else:
                rsi_desc = "BEARISH (Weak)"

        # MACD Helper
        if pd.isna(macd) or pd.isna(macd_sig) or pd.isna(macd_hist):
            macd_str = "N/A"
            macd_status = "N/A"
        else:
            macd_str = (
                f"Line: {macd:.2f} | Sig: {macd_sig:.2f} | " f"Hist: {macd_hist:.2f}"
            )
            macd_status = "BULLISH (Crossover)" if macd > macd_sig else "BEARISH"

        # BB position helper
        if pd.isna(bb_up) or pd.isna(bb_low) or pd.isna(bb_mid):
            bb_str = "N/A"
            bb_pos = "N/A"
        else:
            bb_str = f"U: {bb_up:,.2f} | M: {bb_mid:,.2f} | L: {bb_low:,.2f}"
            bb_range = float(bb_up) - float(bb_low)
            if bb_range > 0:
                percent_b = ((cmp - float(bb_low)) / bb_range) * 100.0
                bb_pos = f"{percent_b:.1f}% B-Band Channel"
            else:
                bb_pos = "N/A"

        # ADX helper
        if pd.isna(adx):
            adx_str, adx_desc = "N/A", "N/A"
        else:
            adx_val = float(adx)
            adx_str = f"{adx_val:.2f}"
            if adx_val > 25.0:
                adx_desc = "STRONG Trend"
            else:
                adx_desc = "WEAK / SIDEWAYS Trend"

        # ATR helper
        if pd.isna(atr):
            atr_str, atr_desc = "N/A", "N/A"
        else:
            atr_val = float(atr)
            atr_str = f"{atr_val:,.2f}"
            atr_pct = (atr_val / cmp) * 100.0 if cmp > 0 else 0.0
            atr_desc = f"{atr_pct:.2f}% volatility"

        # CCI helper
        if pd.isna(cci):
            cci_str, cci_desc = "N/A", "N/A"
        else:
            cci_val = float(cci)
            cci_str = f"{cci_val:.2f}"
            if cci_val >= 100.0:
                cci_desc = "OVERBOUGHT (Uptrend peak)"
            elif cci_val <= -100.0:
                cci_desc = "OVERSOLD (Downtrend trough)"
            else:
                cci_desc = "NEUTRAL Range"

        # Score & Rating
        ta_info = calculate_technical_score(row)
        score = ta_info["score"]
        rating = ta_info["rating"]

        # Color rating helper
        color_code = ""
        if "STRONG BUY" in rating:
            color_code = "🌟"
        elif "BUY" in rating:
            color_code = "✅"
        elif "NEUTRAL" in rating:
            color_code = "⚖️"
        elif "STRONG SELL" in rating:
            color_code = "⚠️"
        else:
            color_code = "❌"

        # Print the dashboard
        print("\n" + "=" * 80)
        print(f"      DASHBOARD: {symbol.upper()} ({color_code} {rating})")
        print("=" * 80)
        print(
            f"  Latest Date: {date_str:<12} Volume: {volume:,.0f} "
            f"({change_pct:+.2f}%)"
        )
        print(
            f"  CMP:         {cmp:<12,.2f} High:   {high:<12,.2f} " f"Low: {low:,.2f}"
        )
        print("-" * 80)
        print("  [TREND INDICATORS]")
        print(f"    EMA (20):  {ema_20_str:<12} (Price is {ema_comp} EMA 20)")
        print(f"    SMA (50):  {sma_50_str:<12} (Price is {sma_50_comp} SMA 50)")
        print(f"    SMA (200): {sma_200_str:<12} (Price is {sma_200_comp} SMA 200)")
        print("-" * 80)
        print("  [MOMENTUM & VOLATILITY]")
        print(f"    RSI (14):  {rsi_str:<12} -> {rsi_desc}")
        print(f"    MACD:      {macd_str:<12} -> {macd_status}")
        print(f"    CCI (14):  {cci_str:<12} -> {cci_desc}")
        print(f"    B-Bands:   {bb_str}")
        print(f"    BB Pos:    {bb_pos}")
        print(f"    ADX (14):  {adx_str:<12} -> {adx_desc}")
        print(f"    ATR (14):  {atr_str:<12} -> {atr_desc}")
        print("=" * 80)
        print(f"  TECHNICAL SCORE: {score}/100            " f"OVERALL RATING: {rating}")
        print("=" * 80 + "\n")

    except Exception as exc:
        print(f"❌ Error displaying dashboard for '{symbol}': {exc}")


def menu_recompute_ta(hist_dir: str) -> None:
    """
    Interactive handler to recompute all TA-Lib indicators for Parquet files.

    Parameters:
        hist_dir (str): Historical Parquet root directory.

    Returns:
        None
    """
    print("\n--- Recompute Technical Analysis Indicators ---")
    print("This will loop through all local Parquet files, calculate")
    print("advanced indicators using TA-Lib, and update the cache.")
    confirm = input("Proceed? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    sync_obj = HistoricalSync(data_dir=hist_dir)
    sync_obj.recompute_all_ta()


def interactive_menu(
    data_dir: str = DEFAULT_DATA_DIR,
    hist_dir: str = DEFAULT_HIST_DIR,
) -> None:
    """
    REPL-style interactive menu loop for the NSE pipeline.

    Logic:
        Step 1: Print banner and menu options.
        Step 2: Accept user choice.
        Step 3: Dispatch to correct handler.
        Step 4: Loop until user selects Exit.

    Parameters:
        data_dir (str): Root data/master directory. | Default "data".
        hist_dir (str): Historical Parquet root directory. | Default "data/historical".

    Returns:
        None

    Raises:
        None

    Example:
        >>> interactive_menu()

    Performance:
        Time Complexity: O(U) [U = number of user interactions]
        Space Complexity: O(1)

    Edge Cases Handled:
        - Invalid choices prompt retry.
        - KeyboardInterrupt exits cleanly.
    """
    processed_dir = os.path.join(data_dir, "processed")

    _print_banner()

    while True:
        _print_main_menu()
        try:
            choice = input("  Select option [1-9]: ").strip()
        except KeyboardInterrupt:
            print("\nBye!")
            break

        if choice == "1":
            menu_build_master(data_dir)
        elif choice == "2":
            menu_sync_history(data_dir, hist_dir)
        elif choice == "3":
            menu_sync_filtered(data_dir, hist_dir)
        elif choice == "4":
            menu_screen(data_dir, hist_dir, processed_dir)
        elif choice == "5":
            menu_status(hist_dir, data_dir)
        elif choice == "6":
            menu_registry(data_dir, hist_dir)
        elif choice == "7":
            menu_ta_dashboard(hist_dir)
        elif choice == "8":
            menu_recompute_ta(hist_dir)
        elif choice == "9":
            print("Bye!")
            break
        else:
            print(f"  Invalid choice: '{choice}'. Please enter 1-9.")


# ===========================================================================
# CLI argument parser
# ===========================================================================


def _build_parser() -> argparse.ArgumentParser:
    """
    Build the top-level argparse parser with all subcommands.

    Logic:
        Step 1: Create root parser with global options.
        Step 2: Add subparsers: build-master, sync-history, screen, menu.
        Step 3: Return configured parser.

    Parameters:
        None

    Returns:
        argparse.ArgumentParser: Fully configured parser.

    Raises:
        None

    Example:
        >>> parser = _build_parser()
        >>> args = parser.parse_args(["sync-history", "--limit", "50"])

    Performance:
        Time Complexity: O(1)
        Space Complexity: O(1)

    Edge Cases Handled:
        - Default subcommand is 'menu' when no args provided.
    """
    parser = argparse.ArgumentParser(
        prog="nse-pipeline",
        description=("NSE Data Pipeline: build master → sync history → screen stocks"),
    )
    parser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        dest="data_dir",
        help=f"Root data directory (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--hist-dir",
        default=DEFAULT_HIST_DIR,
        dest="hist_dir",
        help=f"Historical Parquet directory (default: {DEFAULT_HIST_DIR})",
    )

    sub = parser.add_subparsers(dest="command")

    # ---- build-master ----
    p_master = sub.add_parser(
        "build-master",
        help="Download Bhavcopy + index data and build the equity master table.",
    )
    p_master.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between index API calls (default: 1.0)",
    )
    p_master.set_defaults(func=cmd_build_master)

    # ---- sync-history ----
    p_sync = sub.add_parser(
        "sync-history",
        help="Sync per-symbol OHLCV Parquet files (full history + incremental).",
    )
    p_sync.add_argument(
        "--timeframe",
        default=DEFAULT_TIMEFRAME,
        help=f"Candle timeframe: 1d, 1w, 1mo (default: {DEFAULT_TIMEFRAME})",
    )
    p_sync.add_argument(
        "--start-date",
        default=DEFAULT_START_DATE,
        dest="start_date",
        help=f"Earliest date for history (default: {DEFAULT_START_DATE})",
    )
    p_sync.add_argument(
        "--cap-filter",
        default=None,
        dest="cap_filter",
        choices=["Large", "Mid", "Small", "Other"],
        help="Filter symbols by market cap category.",
    )
    p_sync.add_argument(
        "--index-filter",
        default=None,
        dest="index_filter",
        help="Filter by index column e.g. is_nifty_50",
    )
    p_sync.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of symbols to sync.",
    )
    p_sync.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
        help="Re-download already current symbols.",
    )
    p_sync.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds between API calls (default: 0.5)",
    )
    p_sync.add_argument(
        "--source",
        default="bhavcopy",
        choices=["bhavcopy", "master"],
        help=(
            "Symbol source: 'bhavcopy' (default, uses today's traded EQ list) "
            "or 'master' (full 2400+ symbol master table)."
        ),
    )
    p_sync.set_defaults(func=cmd_sync_history, resume=True)

    # ---- screen ----
    p_screen = sub.add_parser(
        "screen",
        help="Run technical screener on synced historical data.",
    )
    p_screen.add_argument(
        "--processed-dir",
        default=os.path.join(DEFAULT_DATA_DIR, "processed"),
        dest="processed_dir",
        help="Directory containing processed Bhavcopy CSVs.",
    )
    p_screen.add_argument(
        "--cap-filter",
        default=None,
        dest="cap_filter",
        choices=["Large", "Mid", "Small", "Other"],
        help="Filter symbols by market cap.",
    )
    p_screen.add_argument(
        "--index-filter",
        default=None,
        dest="index_filter",
        help="Filter by index column e.g. is_nifty_50",
    )
    p_screen.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum symbols to screen.",
    )
    p_screen.set_defaults(func=cmd_screen)

    # ---- menu (default) ----
    sub.add_parser(
        "menu",
        help="Launch the interactive menu (default when no subcommand given).",
    )

    return parser


def main() -> None:
    """
    CLI entry point: parse arguments and dispatch to subcommand or menu.

    Logic:
        Step 1: Build and parse argument parser.
        Step 2: If no subcommand given, launch interactive_menu.
        Step 3: Otherwise call the registered subcommand function.

    Parameters:
        None

    Returns:
        None

    Raises:
        SystemExit: On critical errors in subcommands.

    Example:
        >>> # CLI: uv run main.py build-master
        >>> # CLI: uv run main.py sync-history --cap-filter Large
        >>> # CLI: uv run main.py screen
        >>> # CLI: uv run main.py  (launches interactive menu)

    Performance:
        Time Complexity: O(1) [dispatch only]
        Space Complexity: O(1)

    Edge Cases Handled:
        - No subcommand defaults to interactive menu.
    """
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None or args.command == "menu":
        interactive_menu(
            data_dir=args.data_dir,
            hist_dir=args.hist_dir,
        )
    else:
        args.func(args)


if __name__ == "__main__":
    main()
