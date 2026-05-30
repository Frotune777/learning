"""
File: main.py
Purpose: Unified CLI and interactive menu for the NSE data pipeline.

Dependencies:
External:
- pandas>=2.2.3: DataFrame utilities and Parquet reading
Internal:
- src.storage.equity_master: [NSEEquityMasterBuilder]
- src.storage.historical_sync: [HistoricalSync]
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
from collections.abc import Callable
from datetime import datetime

import pandas as pd

from src.nse_bhavcopy.correlation import run_correlation_cli
from src.storage.downloader import BhavcopyDownloader
from src.storage.equity_master import NSEEquityMasterBuilder
from src.scanners.etf_screener import run_liquid_etf_screener
from src.nse_bhavcopy.heatmap import run_heatmap_cli
from src.storage.historical_sync import (
    HistoricalSync,
)
from src.nse_bhavcopy.ma_slope import analyze_stock_ma_slope
from src.scanners.minervini_screener import run_minervini_cli
from src.scrapers.mmi_scraper import run_mmi_cli
from src.scanners.momentum_squeeze import run_squeeze_cli
from src.scanners.pair_scanner import run_pair_scanner_cli
from src.nse_bhavcopy.screener import StockScreener
from src.nse_bhavcopy.sector_rotation import run_sector_rotation_cli
from src.storage.sync_registry import SyncRegistry
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

# ---------------------------------------------------------------------------
# ANSI colour helpers  (gracefully degrade on Windows / dumb terminals)
# ---------------------------------------------------------------------------
_USE_COLOR = sys.stdout.isatty()


from src.cli.formatters import _c, dim, bold, green, yellow, red, cyan, white, blue, _rule, _header, _subheader, ok, warn, err, tip, _pause, _confirm, _ask, _ask_float
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


def _get_delivery_history(processed_dir: str, symbol: str) -> pd.DataFrame | None:
    """
    Aggregate delivery percentage history from processed Bhavcopy files.

    Parameters:
        processed_dir (str): Directory containing top_250_*.csv files. |
            Must exist.
        symbol (str): Ticker symbol. | Case-insensitive.

    Returns:
        pd.DataFrame | None: Delivery history DataFrame with Date and DELIV_PCT,
            or None.

    Raises:
        None

    Complexity:
        Time: O(F * N) where F is files count and N is rows per file.
        Space: O(F)

    Example:
        >>> df = _get_delivery_history("data/processed", "TCS")
    """
    import glob
    import re

    rows = []
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
# Subcommand handlers (non-interactive / CLI mode)
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
        print(f"\n✔  Master table saved: {path}")
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

    ok_count = sum(v for v in results.values())
    failed = [s for s, v in results.items() if not v]
    print(f"\n✔  Sync complete: {ok_count}/{len(symbols)} symbols succeeded.")
    if failed:
        print(f"!   Failed ({len(failed)}): {', '.join(failed[:20])}")


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

    processed_dir: str = args.processed_dir
    csv_pattern = os.path.join(processed_dir, "*.csv")
    csv_files = sorted(glob.glob(csv_pattern), reverse=True)
    if not csv_files:
        LOGGER.error(
            "No processed Bhavcopy CSV found in '%s'. Run 'sync-history' first.",
            processed_dir,
        )
        sys.exit(1)

    top_csv: str = csv_files[0]
    LOGGER.info("Using Bhavcopy: %s", top_csv)

    screener = StockScreener(processed_dir=args.hist_dir)
    screener.screen_stocks(top_250_path=top_csv, date_obj=datetime.now())
    print(f"\n✔  Screening complete. Results saved to: {args.hist_dir}")


def cmd_backtest(args: argparse.Namespace) -> None:
    """
    Run machine learning direction classifier and event backtest for a symbol.

    Parameters:
        args (argparse.Namespace): Parsed command-line arguments.

    Returns:
        None

    Raises:
        SystemExit: If input parquet is not found.
    """
    symbol = args.symbol.strip().upper()
    price_path = os.path.join(args.hist_dir, "1d", f"{symbol}.parquet")
    if not os.path.exists(price_path):
        LOGGER.error("Historical Parquet file not found at: %s", price_path)
        sys.exit(1)

    try:
        df_prices = pd.read_parquet(price_path)
        if df_prices.empty or len(df_prices) < 20:
            LOGGER.error("Insufficient history for %s.", symbol)
            sys.exit(1)

        processed_dir = os.path.join(args.data_dir, "processed")
        df_delivery = _get_delivery_history(processed_dir, symbol)

        from rich.console import Console
        from rich.table import Table

        from src.nse_bhavcopy.backtester import NSEEventBacktester
        from src.ml.ml_classifier import MLClassifier

        clf = MLClassifier(n_estimators=args.n_estimators, max_depth=args.max_depth)
        X, y = clf.prepare_features(df_prices, df_delivery)
        if len(X) < 10:
            LOGGER.error("Not enough feature rows generated to run backtest.")
            sys.exit(1)

        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        clf.train(X_train, y_train)
        preds = clf.predict(X_test)

        from sklearn.metrics import accuracy_score, precision_score, recall_score

        acc = float(accuracy_score(y_test, preds))
        prec = float(precision_score(y_test, preds, zero_division=0))
        rec = float(recall_score(y_test, preds, zero_division=0))

        signals_test = pd.Series(preds, index=X_test.index)
        test_prices = df_prices.loc[X_test.index]
        ev_bt = NSEEventBacktester(init_cash=100000.0)
        bt_res = ev_bt.run(test_prices, signals_test)

        console = Console()
        table = Table(
            title=f"ML Backtest Results: {symbol}",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Metric", justify="left")
        table.add_column("Value", justify="right")
        table.add_row("Classifier Accuracy", f"{acc * 100:.2f}%")
        table.add_row("Classifier Precision", f"{prec * 100:.2f}%")
        table.add_row("Classifier Recall", f"{rec * 100:.2f}%")
        table.add_row("Initial Portfolio Cash", "INR 100,000.00")
        table.add_row("Final Portfolio Value", f"INR {bt_res['final_value']:,.2f}")
        table.add_row("Simulated Strategy Return", f"{bt_res['total_return_pct']:.2f}%")
        table.add_row("Max Drawdown", f"{bt_res['max_drawdown_pct']:.2f}%")
        table.add_row("Total Executed Trades", str(bt_res["total_trades"]))
        console.print()
        console.print(table)

    except Exception as exc:
        LOGGER.error("Failed to run ML backtest: %s", exc)
        sys.exit(1)


def cmd_bhavcopy_sync(args: argparse.Namespace) -> None:
    """
    Execute the 'bhavcopy-sync' CLI subcommand.

    Downloads missing Bhavcopy ZIPs (1 per trading day) and appends OHLCV
    rows directly into per-symbol Parquets — far faster than per-symbol API.

    Logic:
        Step 1: Load symbol list from Bhavcopy ZIP or master table.
        Step 2: Instantiate BhavcopyIncrementalSync.
        Step 3: Call run() which detects missing days, downloads ZIPs, appends.
        Step 4: Print summary; symbols needing full refresh are flagged.

    Parameters:
        args (argparse.Namespace): Parsed CLI args with hist_dir, data_dir,
            days, limit, no_ta, delay.

    Returns:
        None

    Raises:
        SystemExit: If no symbol source is found.

    Example:
        >>> cmd_bhavcopy_sync(args)

    Performance:
        Time Complexity: O(D * N + S * N) [D days, S symbols, N rows/ZIP]
        Space Complexity: O(D * N)

    Edge Cases Handled:
        - Symbols needing full refresh reported separately in output.
        - NSE holidays produce harmless 404s which are silently skipped.
    """
    from src.storage.bhavcopy_incremental import BhavcopyIncrementalSync

    LOGGER.info("=== BHAVCOPY INCREMENTAL SYNC ===")

    raw_dir: str = os.path.join(args.data_dir, "raw")
    limit = getattr(args, "limit", None)
    days_back: int = getattr(args, "days", 10)
    no_ta: bool = getattr(args, "no_ta", False)
    delay: float = getattr(args, "delay", 1.0)

    symbols = _load_symbols_from_bhavcopy(
        raw_dir=raw_dir,
        master_path=None,
        limit=limit,
    )

    syncer = BhavcopyIncrementalSync(
        data_dir=args.hist_dir,
        timeframe=getattr(args, "timeframe", DEFAULT_TIMEFRAME),
        raw_dir=raw_dir,
        rate_delay=delay,
        recompute_ta=not no_ta,
    )
    results = syncer.run(symbols, days_back=days_back, recompute_ta=not no_ta)

    ok_count = sum(v for v in results.values())
    needs_refresh = [s for s, v in results.items() if not v]
    print(f"\n\u2714  Bhavcopy sync: {ok_count}/{len(symbols)} symbols updated.")
    if needs_refresh:
        print(
            f"!   {len(needs_refresh)} symbol(s) need full refresh "
            f"(run sync-history for these): "
            f"{', '.join(needs_refresh[:20])}"
        )


def cmd_fo_ban(args: argparse.Namespace) -> None:
    """
    Fetch and display the current NSE F&O ban securities.

    Parameters:
        args (argparse.Namespace): Parsed command-line arguments.

    Returns:
        None

    Raises:
        SystemExit: If F&O ban list query fails.
    """
    try:
        from src.scrapers.fo_ban import FOBanManager

        manager = FOBanManager(cache_dir=args.data_dir)
        ban_list = manager.fetch_fo_ban_list()
        if ban_list:
            print(f"\n✔  Found {len(ban_list)} securities in F&O ban:")
            for sym in sorted(ban_list):
                print(f"  · {sym}")
        else:
            print("\n✔  No securities are currently in the F&O ban period.")
    except Exception as exc:
        LOGGER.error("Failed to query F&O ban list: %s", exc)
        sys.exit(1)


def cmd_fyers_login(args: argparse.Namespace) -> None:
    """
    Print the Fyers login URL for the user to obtain an auth code.

    Parameters:
        args (argparse.Namespace): Parsed CLI args with redirect_uri.

    Returns:
        None

    Raises:
        SystemExit: If FYERS_API_KEY not configured.

    Example:
        >>> cmd_fyers_login(args)
    """
    from src.nse_bhavcopy.fyers_fetcher import FyersFetcher

    fetcher = FyersFetcher()
    try:
        redirect = getattr(args, "redirect_uri", None) or os.getenv(
            "FYERS_REDIRECT_URI",
            "https://trade.fyers.in/api-login/redirect-uri/index.html",
        )
        url = fetcher.login_url(redirect_uri=redirect)
        print("\n  Open this URL in your browser to get the auth code:\n")
        print(f"  {cyan(url)}\n")
        print(f"  {dim('After login, copy the ?code= param from the redirect URL.')}")
        print(f"  {dim('Then run:  uv run main.py fyers-token --code <auth_code>')}")
    except RuntimeError as exc:
        err(str(exc))
        tip("Set FYERS_API_KEY or BROKER_API_KEY environment variable first.")
        sys.exit(1)


def cmd_fyers_token(args: argparse.Namespace) -> None:
    """
    Exchange a Fyers auth code for an access token and cache it locally.

    Parameters:
        args (argparse.Namespace): Parsed CLI args with code.

    Returns:
        None

    Raises:
        SystemExit: If exchange fails or credentials missing.

    Example:
        >>> cmd_fyers_token(args)
    """
    from src.nse_bhavcopy.fyers_fetcher import FyersFetcher, exchange_auth_code

    api_key = os.getenv("FYERS_API_KEY") or os.getenv("BROKER_API_KEY")
    api_secret = os.getenv("FYERS_API_SECRET") or os.getenv("BROKER_API_SECRET")

    if not api_key or not api_secret:
        err(
            "FYERS_API_KEY and FYERS_API_SECRET "
            "(or BROKER_API_KEY / BROKER_API_SECRET) must be set as env vars."
        )
        sys.exit(1)

    code = getattr(args, "code", "")
    if not code:
        err("--code is required. Run 'fyers-login' first.")
        sys.exit(1)

    token = exchange_auth_code(code, api_key, api_secret)
    if not token:
        err("Token exchange failed. Check your auth code and credentials.")
        sys.exit(1)

    fetcher = FyersFetcher()
    fetcher.set_token(token)
    print(f"\n{green('✔')}  Fyers access token saved to {fetcher.token_cache}")
    print(f"   {dim('Token is valid for one trading day.')}")
    print(f"   {dim('Run this command each morning before using the pipeline.')}")
