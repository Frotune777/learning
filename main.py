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
from collections.abc import Callable
from datetime import datetime

import pandas as pd

from src.nse_bhavcopy.correlation import run_correlation_cli
from src.nse_bhavcopy.downloader import BhavcopyDownloader
from src.nse_bhavcopy.equity_master import NSEEquityMasterBuilder
from src.nse_bhavcopy.etf_screener import run_liquid_etf_screener
from src.nse_bhavcopy.heatmap import run_heatmap_cli
from src.nse_bhavcopy.historical_sync import (
    HistoricalSync,
)
from src.nse_bhavcopy.ma_slope import analyze_stock_ma_slope
from src.nse_bhavcopy.minervini_screener import run_minervini_cli
from src.nse_bhavcopy.mmi_scraper import run_mmi_cli
from src.nse_bhavcopy.momentum_squeeze import run_squeeze_cli
from src.nse_bhavcopy.pair_scanner import run_pair_scanner_cli
from src.nse_bhavcopy.screener import StockScreener
from src.nse_bhavcopy.sector_rotation import run_sector_rotation_cli
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

# ---------------------------------------------------------------------------
# ANSI colour helpers  (gracefully degrade on Windows / dumb terminals)
# ---------------------------------------------------------------------------
_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    """Wrap *text* in an ANSI escape *code* if the terminal supports it."""
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def dim(t: str) -> str:
    return _c("2", t)


def bold(t: str) -> str:
    return _c("1", t)


def green(t: str) -> str:
    return _c("32", t)


def yellow(t: str) -> str:
    return _c("33", t)


def red(t: str) -> str:
    return _c("31", t)


def cyan(t: str) -> str:
    return _c("36", t)


def white(t: str) -> str:
    return _c("97", t)


def blue(t: str) -> str:
    return _c("34", t)


# ---------------------------------------------------------------------------
# Shared UI primitives
# ---------------------------------------------------------------------------
_W = 68  # console width


def _rule(char: str = "─", width: int = _W) -> str:
    return dim(char * width)


def _header(title: str, subtitle: str = "") -> None:
    """Print a section header with an optional subtitle."""
    print()
    print(_rule("━"))
    print(f"  {bold(white(title))}")
    if subtitle:
        print(f"  {dim(subtitle)}")
    print(_rule("━"))


def _subheader(title: str) -> None:
    print()
    print(f"  {cyan('▸')} {bold(title)}")
    print(_rule("╌"))


def ok(msg: str) -> None:
    print(f"\n  {green('✔')}  {msg}")


def warn(msg: str) -> None:
    print(f"\n  {yellow('!')}  {msg}")


def err(msg: str) -> None:
    print(f"\n  {red('✘')}  {msg}")


def tip(msg: str) -> None:
    print(f"  {dim('→')}  {dim(msg)}")


def _pause() -> None:
    """Wait for the user to press Enter before returning to the main menu."""
    print()
    input(dim("  Press Enter to return to the menu… "))


def _confirm(prompt: str = "Proceed?") -> bool:
    """Ask a yes/no question; default is No."""
    answer = input(f"  {prompt} {dim('[y/N]')} ").strip().lower()
    return answer == "y"


def _ask(prompt: str, default: str) -> str:
    """Prompt with a default value shown inline."""
    raw = input(f"  {prompt} {dim(f'[{default}]')} ").strip()
    return raw or default


def _ask_float(prompt: str, default: float) -> float:
    raw = input(f"  {prompt} {dim(f'[{default}]')} ").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        warn(f"Invalid number — using {default}")
        return default


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
        from src.nse_bhavcopy.ml_classifier import MLClassifier

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
    from src.nse_bhavcopy.bhavcopy_incremental import BhavcopyIncrementalSync

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
        from src.nse_bhavcopy.fo_ban import FOBanManager

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


# ===========================================================================
# Interactive menu — UI helpers
# ===========================================================================


def _print_banner() -> None:
    """Print the application banner."""
    print()
    print(_rule("═"))
    print()
    print(f"  {bold(white('NSE DATA PIPELINE'))}  {dim('v2026-05')}")
    print(f"  {dim('Equity Master  ·  Historical Sync  ·  Technical Screener')}")
    print()
    print(_rule("═"))


def _print_main_menu() -> None:
    """Print the top-level menu with grouped sections."""
    print()
    print(f"  {dim('DATA')}")
    print(
        f"   {cyan('1')}  {bold('Build / Refresh Equity Master')}  "
        f"{dim('download sec_list + index data')}"
    )
    print(
        f"   {cyan('2')}  {bold('Sync Historical  ─ All Symbols')}  "
        f"{dim('all Bhavcopy EQ symbols')}"
    )
    print(
        f"   {cyan('3')}  {bold('Sync Historical  ─ Filtered')}    "
        f"{dim('by cap, index, or count')}"
    )
    print()
    print(f"  {dim('ANALYSIS')}")
    print(
        f"   {cyan('4')}  {bold('Run Technical Screener')}          "
        f"{dim('final / swing / super lists')}"
    )
    print(
        f"   {cyan('7')}  {bold('TA Dashboard  ─ Single Stock')}    "
        f"{dim('RSI, MACD, Bollinger, ADX…')}"
    )
    print(
        f"   {cyan('8')}  {bold('Recompute TA Indicators')}         "
        f"{dim('refresh all local Parquet files')}"
    )
    print()
    print(f"  {dim('STATUS')}")
    print(
        f"   {cyan('5')}  {bold('Parquet Sync Status')}             "
        f"{dim('rows, date ranges per symbol')}"
    )
    print(
        f"   {cyan('6')}  {bold('Sync Registry')}                   "
        f"{dim('pending / failed / ok breakdown')}"
    )
    print()
    print(f"  {dim('QUANTITATIVE')}")
    print(
        f"   {cyan('9')}  {bold('Liquid ETF Screener')}             "
        f"{dim('top liquid ETFs per sector')}"
    )
    print(
        f"  {cyan('10')}  {bold('Mark Minervini Template')}         "
        f"{dim('VCP, RS Rating & Trend Screen')}"
    )
    print(
        f"  {cyan('11')}  {bold('Sector Rotation Chart')}           "
        f"{dim('JdK RS-Ratio Quadrant Analysis')}"
    )
    print(
        f"  {cyan('12')}  {bold('Correlation Matrix')}              "
        f"{dim('Cross-asset return correlation')}"
    )
    print(
        f"  {cyan('13')}  {bold('Nifty Indices Heatmap')}           "
        f"{dim('Constituents performance')}"
    )
    print(
        f"  {cyan('14')}  {bold('Market Mood Index (MMI)')}         "
        f"{dim('Live sentiment scraper')}"
    )
    print(
        f"  {cyan('15')}  {bold('Moving Average Slope')}            "
        f"{dim('Trend angle analyzer')}"
    )
    print(
        f"  {cyan('16')}  {bold('Momentum Squeeze Indicator')}      "
        f"{dim('BB / KC coiled-spring detector')}"
    )
    print(
        f"  {cyan('17')}  {bold('Live NSE Data Hub')}               "
        f"{dim('Pre-market, price info, option chain…')}"
    )
    print(
        f"  {cyan('18')}  {bold('Cointegration Pair Scanner')}      "
        f"{dim('Engle-Granger pairs from local parquet universe')}"
    )
    print(
        f"  {cyan('19')}  {bold('ML Classifier Backtester')}       "
        f"{dim('Random Forest & Event Backtest on symbol')}"
    )
    print(
        f"  {cyan('20')}  {bold('View F&O Ban List')}               "
        f"{dim('Fetch current NSE F&O ban securities')}"
    )
    print(
        f"  {cyan('21')}  {bold('Bhavcopy Incremental Sync')}       "
        f"{dim('Batch OHLCV update — 1 ZIP/day instead of 1 800+ API calls')}"
    )
    print(
        f"  {cyan('22')}  {bold('Set Fyers API Token')}             "
        f"{dim('Configure Fyers access token for historical data')}"
    )
    print()
    print(f"   {dim('0')}  {dim('Exit')}")
    print()
    print(_rule())


# ===========================================================================
# Interactive menu — action handlers
# ===========================================================================


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
    _header("Build Equity Master", "Downloads sec_list.csv + all index constituents")
    tip("This replaces any previously cached master Parquet.")

    if not _confirm("Start build?"):
        warn("Cancelled.")
        return

    delay = _ask_float("API delay between index calls (seconds)", 1.0)

    builder = NSEEquityMasterBuilder(
        output_dir=data_dir,
        cache_dir=os.path.join(data_dir, "cache"),
    )
    try:
        path = builder.build_and_save(delay=delay)
        ok(f"Master saved  →  {path}")
    except RuntimeError as exc:
        err(f"Build failed: {exc}")

    _pause()


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
    master_path = _find_latest_master(data_dir)
    symbols = _load_symbols(
        master_path, cap_filter=cap_filter, index_filter=index_filter
    )

    print(f"\n  {dim('Symbols loaded:')}  {bold(str(len(symbols)))}", end="")
    if cap_filter:
        print(f"  {dim('cap=')} {cap_filter}", end="")
    if index_filter:
        print(f"  {dim('index=')} {index_filter}", end="")
    print()

    tf = _ask("Timeframe  (1d / 1w / 1mo)", DEFAULT_TIMEFRAME)
    start = _ask("Start date (YYYY-MM-DD)", DEFAULT_START_DATE)
    delay = _ask_float("Rate delay between requests (seconds)", 0.5)

    hs = HistoricalSync(
        data_dir=hist_dir, timeframe=tf, start_date=start, rate_delay=delay
    )
    results = hs.sync(symbols)

    ok_count = sum(v for v in results.values())
    failed = [s for s, v in results.items() if not v]

    ok(f"Sync complete  {ok_count}/{len(symbols)} succeeded")
    if failed:
        warn(
            f"{len(failed)} failed: {', '.join(failed[:15])}"
            + (" …" if len(failed) > 15 else "")
        )

    _pause()


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
    _header("Sync Historical Data — Filtered")

    print(f"  {dim('Market cap:')}  Large · Mid · Small · Other · {dim('Enter = All')}")
    cap = input("  Cap filter: ").strip() or None
    if cap and cap not in ("Large", "Mid", "Small", "Other"):
        warn(f"Unknown cap '{cap}' — no cap filter applied.")
        cap = None

    print(
        f"  {dim('Index examples:')}  is_nifty_50 · is_nifty_500 · "
        f"{dim('Enter = None')}"
    )
    idx = input("  Index filter: ").strip() or None

    menu_sync_history(
        data_dir=data_dir, hist_dir=hist_dir, cap_filter=cap, index_filter=idx
    )


def _display_csv(path: str, title: str, desc: str | None = None) -> None:
    """
    Pretty-print a screener result CSV.

    Parameters:
        path  (str): Absolute path to the CSV file.
        title (str): Human-readable title for the table header.
        desc  (str): Optional string describing the logic and style.

    Returns:
        None
    """
    if not os.path.exists(path):
        err(f"{title} not found at {path}")
        return

    df = pd.read_csv(path)

    # Analytical view: Drop Volume and Qty if Total Traded Value is available
    if "Total Traded Value" in df.columns:
        if "Volume" in df.columns:
            df = df.drop(columns=["Volume"])
        if "Qty" in df.columns:
            df = df.drop(columns=["Qty"])

    _subheader(title)
    if desc:
        print(f"  {dim(desc)}\n")

    if df.empty:
        warn("No stocks met the criteria.")
        return

    from rich import box
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)

    # Add columns based on dtype
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            table.add_column(col, justify="right")
        else:
            table.add_column(col, justify="left")

    # Add rows with appropriate formatting
    for _, row in df.iterrows():
        row_vals = []
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                row_vals.append("")
            elif pd.api.types.is_numeric_dtype(df[col]):
                if any(
                    x in col for x in ["Volume", "Score", "Rows", "Rating", "Count"]
                ):
                    row_vals.append(f"{val:,.0f}")
                else:
                    row_vals.append(f"{val:,.2f}")
            else:
                row_vals.append(str(val))
        table.add_row(*row_vals)

    console.print(table)
    print(f"\n  {dim(f'{len(df)} row(s)')}")


def _screener_results_menu(hist_dir: str, date_str: str) -> None:
    """
    Sub-menu for browsing screener output files.

    Parameters:
        hist_dir (str): Directory that contains the result CSVs.
        date_str (str): Date string used to locate today's output files.

    Returns:
        None
    """
    final_csv = os.path.join(hist_dir, f"final_list_{date_str}.csv")
    swing_csv = os.path.join(hist_dir, f"swing_list_{date_str}.csv")
    super_csv = os.path.join(hist_dir, f"super_list_{date_str}.csv")

    strategies = [
        (
            "Nifty Shop (Single Leg)",
            os.path.join(hist_dir, f"strategy_nifty_shop_{date_str}.csv"),
            (
                "RSI laddering strategy for mean reversion. Level 1 (RSI < 35),"
                " Level 2 (< 30), Level 3 (< 25). Targets 6.28% profit."
            ),
        ),
        (
            "Buy Low Sell High",
            os.path.join(hist_dir, f"strategy_buy_low_{date_str}.csv"),
            (
                "Demand level accumulation. Triggers when CMP is within 2.0%"
                " of the 200-Day Low."
            ),
        ),
        (
            "Turtle Trading",
            os.path.join(hist_dir, f"strategy_turtle_{date_str}.csv"),
            (
                "Explosive momentum breakout. Triggers a 'Buy' only when CMP"
                " forcefully crosses the previous 55-Day High."
            ),
        ),
        (
            "RDX Indicator",
            os.path.join(hist_dir, f"strategy_rdx_{date_str}.csv"),
            (
                "Strict momentum screener. Requires ADX > 25, bullish DI"
                " crossover, and RSI > 60."
            ),
        ),
        (
            "100 SMA Breakout",
            os.path.join(hist_dir, f"strategy_100sma_breakout_{date_str}.csv"),
            (
                "Institutional 6-month base breakout. Triggers crossing 100 SMA"
                " while trading > 20% above 6-month lows."
            ),
        ),
        (
            "ETF Shop Method",
            os.path.join(hist_dir, f"strategy_etf_shop_{date_str}.csv"),
            (
                "Index fund retracement variant. Triggers a 'Buy' if the ETF"
                " falls more than 2.0% below its 20 DMA."
            ),
        ),
        (
            "Super BO Stocks",
            os.path.join(hist_dir, f"strategy_super_bo_{date_str}.csv"),
            (
                "Recovery strategy. Stocks rising from downtrends facing 200 SMA"
                " resistance while above 50, 100, 150 SMAs."
            ),
        ),
        (
            "DMADMA (Reverse)",
            os.path.join(hist_dir, f"strategy_dmadma_reverse_{date_str}.csv"),
            (
                "Bull market continuation. Triggers on a 150 SMA breakout while"
                " the stock remains above the 200 SMA."
            ),
        ),
        (
            "DMADMA (No SL)",
            os.path.join(hist_dir, f"strategy_dmadma_no_sl_{date_str}.csv"),
            (
                "Pure momentum following — no stop loss. Golden cross analog"
                " where the 50 SMA rises above the 200 SMA."
            ),
        ),
    ]

    while True:
        print()
        print(_rule("─"))
        print(f"  {bold('Screener Results')}  {dim(f'({date_str})')}")
        print(_rule("─"))
        print(
            f"   {cyan('1')}  Final List   "
            f"{dim('Bull Run + CAR Buy/Average Out — pure breakout candidates')}"
        )
        print(
            f"   {cyan('2')}  Swing List   "
            f"{dim('Start GTT signals — 20D low bounce setups with GTT entry')}"
        )
        print(
            f"   {cyan('3')}  Super List   "
            f"{dim('Combined Holy Grail — Bull + CAR + GTT bounce at once')}"
        )

        idx = 4
        for name, path, desc in strategies:
            if os.path.exists(path):
                print(f"   {cyan(str(idx))}  {name} {dim('Strategy')}")
            else:
                print(f"   {dim(str(idx))}  {dim(name + ' (No Results)')}")
            idx += 1

        print(f"   {cyan('99')} View All")
        print(f"   {dim('0')}  {dim('Back to main menu')}")
        print()

        choice = input(f"  {dim('Select')}: ").strip()

        if choice == "0":
            break
        elif choice == "1":
            _display_csv(
                final_csv,
                "Final Target List",
                "Intraday & short-term breakout candidates with strong momentum.",
            )
        elif choice == "2":
            _display_csv(
                swing_csv,
                "Swing Trading List",
                "Positional setups nearing GTT trigger levels for mid-term holding.",
            )
        elif choice == "3":
            _display_csv(
                super_csv,
                "Super Output (The Holy Grail)",
                "Highest conviction setups passing multiple extreme filters.",
            )
        elif choice == "99":
            dfs = []
            for name, path, desc in strategies:
                if os.path.exists(path):
                    df_strat = pd.read_csv(path)
                    if not df_strat.empty:
                        df_strat.insert(1, "Strategy", name)
                        dfs.append(df_strat)

            if dfs:
                combined_df = pd.concat(dfs, ignore_index=True)

                agg_dict = {}
                for col in combined_df.columns:
                    if col == "NSE Code":
                        continue
                    elif col in [
                        "Total Traded Value",
                        "CMP",
                        "Change %",
                        "Return Z-Score",
                        "Vol Spike (x)",
                        "RSI",
                        "Tech Score",
                        "Diff %",
                    ]:
                        agg_dict[col] = "first"
                    elif col in ["Strategy", "Action"]:
                        agg_dict[col] = lambda x: " | ".join(  # type: ignore[assignment]
                            x.dropna().astype(str).unique()
                        )
                    elif col in ["Target", "Stop Loss"]:
                        agg_dict[col] = lambda x: " | ".join(  # type: ignore[assignment]
                            str(round(float(v), 2))
                            for v in x.dropna().unique()
                            if pd.notna(v)
                        )

                grouped_df = combined_df.groupby("NSE Code").agg(agg_dict).reset_index()

                if "Total Traded Value" in grouped_df.columns:
                    grouped_df = grouped_df.sort_values(
                        by="Total Traded Value", ascending=False
                    )

                # Consolidate column layout for view all
                combined_path = os.path.join(
                    hist_dir, f"view_all_grouped_{date_str}.csv"
                )
                grouped_df.to_csv(combined_path, index=False)
                desc_text = (
                    "Master view of all advanced strategy triggers today,"
                    " intelligently grouped by stock."
                )
                _display_csv(
                    combined_path, "Grouped Advanced Strategies Output", desc_text
                )

                export_path = f"Exported_Grouped_Strategies_{date_str}.csv"
                grouped_df.to_csv(export_path, index=False)
                print(
                    f"\n  {bold('Exported:')} CSV successfully saved to "
                    f"{cyan(export_path)} in the project root."
                )
            else:
                warn("No strategy results found for today.")
        else:
            try:
                c_idx = int(choice)
                if 4 <= c_idx < 4 + len(strategies):
                    strat_name, strat_path, strat_desc = strategies[c_idx - 4]
                    if os.path.exists(strat_path):
                        _display_csv(strat_path, strat_name, strat_desc)
                    else:
                        warn(f"No results generated for {strat_name} today.")
                else:
                    warn(f"Invalid choice '{choice}'.")
            except ValueError:
                warn(f"Invalid choice '{choice}'.")

        _pause()


def menu_screen(data_dir: str, hist_dir: str, processed_dir: str) -> None:
    """
    Interactive handler for running the technical screener.

    Logic:
        Step 1: Find latest Bhavcopy CSV in processed_dir.
        Step 2: Optionally refresh historical data first.
        Step 3: Instantiate StockScreener and run screen_stocks.
        Step 4: Open screener results sub-menu.

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
    _header("Technical Screener", "Scans synced Parquet data for technical setups")

    if _confirm("Fetch latest history + update TA indicators first?"):
        menu_sync_filtered(data_dir, hist_dir)
        _subheader("Continuing with Screener")

    csv_pattern = os.path.join(processed_dir, "*.csv")
    csv_files = sorted(glob.glob(csv_pattern), reverse=True)
    if not csv_files:
        err(f"No processed Bhavcopy CSV found in '{processed_dir}'.")
        tip("Run option [2] or [3] to sync data first.")
        _pause()
        return

    top_csv = csv_files[0]
    print(f"\n  {dim('Reference Bhavcopy:')} {os.path.basename(top_csv)}")

    now = datetime.now()
    screener = StockScreener(processed_dir=hist_dir)
    screener.screen_stocks(top_250_path=top_csv, date_obj=now)

    ok(f"Screening complete  →  results in {hist_dir}")

    _screener_results_menu(hist_dir, now.strftime("%Y%m%d"))


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
    _header("Parquet Sync Status")

    master_path = _find_latest_master(data_dir)
    if master_path is None:
        err("No master table found.")
        tip("Run option [1] to build the master first.")
        _pause()
        return

    builder = NSEEquityMasterBuilder(output_dir=data_dir)
    symbols = builder.get_symbols(master_path)
    hs = HistoricalSync(data_dir=hist_dir)
    status_df = hs.status(symbols)

    synced = status_df[status_df["rows"] > 0]
    missing = status_df[status_df["rows"] == 0]

    print(f"\n  {'Total in master':<28} {bold(str(len(status_df)))}")
    print(f"  {green('Synced (have Parquet)'):<28} {bold(str(len(synced)))}")
    print(f"  {yellow('Not yet synced'):<28} {bold(str(len(missing)))}")

    if not synced.empty:
        _subheader("Top 10 Synced Symbols")
        print(
            synced.head(10)[
                [
                    "symbol",
                    "rows",
                    "expected_rows",
                    "coverage_pct",
                    "first_date",
                    "last_date",
                ]
            ].to_string(index=False)
        )

    if not missing.empty:
        _subheader(f"First 10 Unsynced  ({len(missing)} total)")
        print("  " + "  ".join(missing["symbol"].head(10).tolist()))

    _pause()


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
    _header("Sync Registry", "Pending · OK · Failed breakdown")

    tf = _ask("Timeframe", DEFAULT_TIMEFRAME)
    reg = SyncRegistry(registry_dir=hist_dir, timeframe=tf)
    n = reg.load()

    if n == 0:
        warn("No registry found.")
        tip("Run a sync (option [2] or [3]) to create one.")
        _pause()
        return

    df = reg.summary()
    counts = df.groupby("status").size()

    print(f"\n  {'Total in registry':<26} {bold(str(len(df)))}")
    for status, cnt in counts.items():
        colour = green if status == "ok" else (red if status == "failed" else yellow)
        print(f"  {colour(f'{status:<26}')} {bold(str(cnt))}")

    pending = df[df["needs_update"] & (df["status"] != "failed")]
    failed = df[df["status"] == "failed"]

    if not pending.empty:
        _subheader("Top 10 Pending (oldest first)")
        print(
            pending.head(10)[
                ["symbol", "status", "last_bar_date", "row_count"]
            ].to_string(index=False)
        )

    if not failed.empty:
        _subheader(f"Failed Symbols  ({len(failed)} total)")
        print(
            failed.head(10)[["symbol", "fail_count", "last_bar_date"]].to_string(
                index=False
            )
        )

    pending_queue = reg.pending_symbols()
    print(f"\n  {dim('Next sync queue:')} {bold(str(len(pending_queue)))} symbols")
    if pending_queue:
        print(f"  {dim('Next 5:')} {', '.join(pending_queue[:5])}")

    _pause()


def menu_ta_dashboard(hist_dir: str) -> None:
    """
    Display a console dashboard for a single stock's TA indicators.

    Parameters:
        hist_dir (str): Historical Parquet root directory.

    Returns:
        None
    """
    _header(
        "TA Dashboard — Single Stock",
        "RSI · MACD · Bollinger · ADX · ATR · CCI · Score",
    )

    symbol = input(f"  {dim('NSE Symbol')} (e.g. TCS): ").strip().upper()
    if not symbol:
        return

    path = os.path.join(hist_dir, "1d", f"{symbol}.parquet")
    if not os.path.exists(path):
        err(f"Historical data for '{symbol}' not found at: {path}")
        tip("Sync this symbol first using option [2] or [3].")
        _pause()
        return

    try:
        df = pd.read_parquet(path)
        if df.empty:
            err(f"Data file for '{symbol}' is empty.")
            _pause()
            return

        if df.index.tz is not None:
            df.index = df.index.tz_convert(None)
        else:
            df.index = pd.to_datetime(df.index)

        df = df.sort_index()

        if "RSI_14" not in df.columns:
            print(f"  {dim('Pre-calculated TA columns not found — computing…')}")
            df = add_ta_indicators(df)

        row = df.iloc[-1]
        date_str = df.index[-1].strftime("%Y-%m-%d")

        cmp = float(row.get("Close", 0.0))
        high = float(row.get("High", 0.0))
        low = float(row.get("Low", 0.0))
        volume = float(row.get("Volume", 0.0))

        change_pct = 0.0
        if len(df) >= 2:
            prev = float(df["Close"].iloc[-2])
            if prev > 0:
                change_pct = ((cmp - prev) / prev) * 100.0

        ema_20 = row.get("EMA_20")
        sma_50 = row.get("SMA_50")
        sma_200 = row.get("SMA_200")
        rsi = row.get("RSI_14")
        macd = row.get("MACD")
        macd_sig = row.get("MACD_SIGNAL")
        macd_hist_val = row.get("MACD_HIST")
        bb_up = row.get("BB_UPPER")
        bb_mid = row.get("BB_MIDDLE")
        bb_low_ = row.get("BB_LOWER")
        adx = row.get("ADX_14")
        atr = row.get("ATR_14")
        cci = row.get("CCI_14")

        def _fmt(v: object) -> str:
            return f"{float(v):,.2f}" if v is not None and not pd.isna(v) else "N/A"  # type: ignore[arg-type]

        def _cmp_str(price: float, ma: object) -> str:
            if ma is None or pd.isna(ma):
                return dim("N/A")
            return green("ABOVE") if price > float(ma) else red("BELOW")  # type: ignore[arg-type]

        # RSI
        if pd.isna(rsi):
            rsi_str, rsi_desc = "N/A", dim("N/A")
        else:
            rsi_val = float(rsi)
            rsi_str = f"{rsi_val:.2f}"
            if rsi_val >= 70:
                rsi_desc = red("OVERBOUGHT  (caution)")
            elif rsi_val <= 30:
                rsi_desc = green("OVERSOLD  (rebound candidate)")
            elif rsi_val >= 50:
                rsi_desc = green("BULLISH  (strong)")
            elif rsi_val >= 40:
                rsi_desc = yellow("NEUTRAL-BULLISH")
            else:
                rsi_desc = red("BEARISH  (weak)")

        # MACD
        if any(pd.isna(v) for v in [macd, macd_sig, macd_hist_val]):
            macd_line = dim("N/A")
            macd_status = dim("N/A")
        else:
            macd_line = (
                f"Line {macd:.2f}  ·  Sig {macd_sig:.2f}"
                f"  ·  Hist {macd_hist_val:.2f}"
            )
            macd_status = (
                green("BULLISH (crossover)") if macd > macd_sig else red("BEARISH")
            )

        # Bollinger Bands
        if any(pd.isna(v) for v in [bb_up, bb_mid, bb_low_]):
            bb_line, bb_pos = dim("N/A"), dim("N/A")
        else:
            bb_line = f"U {bb_up:,.2f}  ·  M {bb_mid:,.2f}  ·  L {bb_low_:,.2f}"
            bb_range = float(bb_up) - float(bb_low_)
            bb_pos = (
                f"{((cmp - float(bb_low_)) / bb_range) * 100:.1f}% B-Band channel"
                if bb_range > 0
                else dim("N/A")
            )

        # ADX
        if pd.isna(adx):
            adx_str, adx_desc = "N/A", dim("N/A")
        else:
            adx_val = float(adx)
            adx_str = f"{adx_val:.2f}"
            adx_desc = (
                green("STRONG trend") if adx_val > 25 else yellow("WEAK / sideways")
            )

        # ATR
        if pd.isna(atr):
            atr_str, atr_desc = "N/A", dim("N/A")
        else:
            atr_val = float(atr)
            atr_str = f"{atr_val:,.2f}"
            atr_pct = (atr_val / cmp * 100) if cmp > 0 else 0.0
            atr_desc = dim(f"{atr_pct:.2f}% volatility")

        # CCI
        if pd.isna(cci):
            cci_str, cci_desc = "N/A", dim("N/A")
        else:
            cci_val = float(cci)
            cci_str = f"{cci_val:.2f}"
            if cci_val >= 100:
                cci_desc = red("OVERBOUGHT  (uptrend peak)")
            elif cci_val <= -100:
                cci_desc = green("OVERSOLD  (downtrend trough)")
            else:
                cci_desc = yellow("NEUTRAL range")

        # Score & rating
        ta_info = calculate_technical_score(row)
        score = ta_info["score"]
        rating = ta_info["rating"]

        badge = {
            "STRONG BUY": "🌟",
            "BUY": "✔",
            "NEUTRAL": "⚖",
            "STRONG SELL": "!",
            "SELL": "✘",
        }.get(
            next(
                (
                    k
                    for k in ["STRONG BUY", "BUY", "NEUTRAL", "STRONG SELL", "SELL"]
                    if k in rating
                ),
                "",
            ),
            "·",
        )
        rating_col = (
            green(rating)
            if "BUY" in rating
            else red(rating)
            if "SELL" in rating
            else yellow(rating)
        )
        chg_col = (
            green(f"+{change_pct:.2f}%")
            if change_pct >= 0
            else red(f"{change_pct:.2f}%")
        )

        # ── Output ────────────────────────────────────────────────────────
        print()
        print(_rule("═"))
        print(
            f"  {bold(white(symbol))}   {badge} {rating_col}"
            f"   {dim('score')} {bold(str(score))}/100"
        )
        print(_rule("─"))
        print(
            f"  {dim('Date')}     {date_str}    "
            f"{dim('Volume')}  {volume:,.0f}    {chg_col}"
        )
        print(
            f"  {dim('CMP')}      {bold(f'{cmp:,.2f}'):14}  "
            f"{dim('High')} {high:,.2f}  {dim('Low')} {low:,.2f}"
        )
        print(_rule("─"))
        print(f"  {bold('TREND')}")
        print(
            f"  {'EMA 20':<12} {_fmt(ema_20):<14} price {_cmp_str(cmp, ema_20)} EMA 20"
        )
        print(
            f"  {'SMA 50':<12} {_fmt(sma_50):<14} price {_cmp_str(cmp, sma_50)} SMA 50"
        )
        print(
            f"  {'SMA 200':<12} {_fmt(sma_200):<14} "
            f"price {_cmp_str(cmp, sma_200)} SMA 200"
        )
        print(_rule("─"))
        print(f"  {bold('MOMENTUM & VOLATILITY')}")
        print(f"  {'RSI 14':<12} {rsi_str:<14} {rsi_desc}")
        print(f"  {'MACD':<12} {macd_line}")
        print(f"  {'':<12} {'':14} {macd_status}")
        print(f"  {'CCI 14':<12} {cci_str:<14} {cci_desc}")
        print(f"  {'B-Bands':<12} {bb_line}")
        print(f"  {'':<12} {bb_pos}")
        print(f"  {'ADX 14':<12} {adx_str:<14} {adx_desc}")
        print(f"  {'ATR 14':<12} {atr_str:<14} {atr_desc}")
        print(_rule("═"))

    except Exception as exc:
        err(f"Error loading '{symbol}': {exc}")

    _pause()


def menu_recompute_ta(hist_dir: str) -> None:
    """
    Interactive handler to recompute all TA-Lib indicators for Parquet files.

    Parameters:
        hist_dir (str): Historical Parquet root directory.

    Returns:
        None
    """
    _header(
        "Recompute TA Indicators",
        "Loops all local Parquet files and rewrites TA columns",
    )
    tip("This may take several minutes for large datasets.")

    if not _confirm("Proceed?"):
        warn("Cancelled.")
        return

    sync_obj = HistoricalSync(data_dir=hist_dir)
    sync_obj.recompute_all_ta()
    ok("TA recompute complete.")
    _pause()


def menu_liquid_etf() -> None:
    """
    Run the Liquid ETF Screener and display the results in a table.
    """
    _header("Liquid ETF Screener")
    print("  Fetching ETF list from NSE and calculating sector liquidity...\n")

    df = run_liquid_etf_screener()

    if df.empty:
        warn("Failed to retrieve or parse ETF data.")
        _pause()
        return

    # Format and save
    out_dir = "data/screener_output"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "top_liquid_etfs.csv")
    df.to_csv(out_path, index=False)

    _display_csv(
        out_path,
        "Top Liquid ETFs (By Sector)",
        "Highest Turnover ETFs per underlying index",
    )
    print(f"\n  {dim(f'Saved to {out_path}')}")
    _pause()


def menu_minervini() -> None:
    """
    Run the Mark Minervini Trend Template Screener.
    """
    _header("Mark Minervini Trend Template Screener")
    print("  Fetching 400 days of historical data via yfinance (F&O Universe)...")
    print("  Calculating RS Ratings, VCP, and Breakouts...\n")

    df = run_minervini_cli()

    if df.empty:
        warn("No stocks met the Trend Template criteria.")
        _pause()
        return

    out_dir = "data/screener_output"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "minervini_candidates.csv")
    df.to_csv(out_path, index=False)

    _display_csv(
        out_path,
        "Minervini Trend Template Candidates",
        "Stocks exhibiting Stage 2 Uptrends, VCP, and High Relative Strength",
    )
    print(f"\n  {dim(f'Saved to {out_path}')}")
    _pause()


def menu_sector_rotation() -> None:
    """
    Run the JdK RS-Ratio Sector Rotation analysis.
    """
    _header("Sector Rotation Analysis (JdK RS-Ratio)")
    print("  Fetching 90 days of historical data for sectors and Nifty 50...")
    print("  Calculating RS-Ratio and Momentum...\n")

    df = run_sector_rotation_cli()

    if df.empty:
        warn("No sector data could be processed.")
        _pause()
        return

    out_dir = "data/screener_output"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "sector_rotation.csv")
    df.to_csv(out_path, index=False)

    _display_csv(
        out_path,
        "Sector Rotation (JdK RS-Ratio)",
        "Quadrants: Leading (Top-Right), Improving (Top-Left),"
        " Weakening (Bottom-Right), Lagging (Bottom-Left)",
    )
    print(f"\n  {dim(f'Saved to {out_path}')}")
    _pause()


def menu_correlation() -> None:
    """
    Run the Correlation Matrix analysis.
    """
    _header("Cross-Asset Correlation Matrix")
    print("  Fetching 1-year of historical returns for benchmarks...")

    df = run_correlation_cli()

    if df.empty:
        warn("No correlation data could be generated.")
        _pause()
        return

    out_dir = "data/screener_output"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "correlation_matrix.csv")
    df.to_csv(out_path, index=False)

    _display_csv(
        out_path,
        "Correlation Matrix (1 Year Returns)",
        "Close to 100% means strong positive correlation, negative means inverse.",
    )
    print(f"\n  {dim(f'Saved to {out_path}')}")
    _pause()


def menu_heatmap() -> None:
    """
    Run the Nifty Indices Heatmap analysis.
    """
    _header("Nifty Indices Heatmap")

    print(f"  {dim('Example Indices:')} NIFTY 50, NIFTY BANK, NIFTY IT, NIFTY PHARMA")
    index_name = input("  Enter Index Name (default: NIFTY 50): ").strip()
    if not index_name:
        index_name = "NIFTY 50"

    print(f"\n  Fetching realtime constituent data for {index_name}...\n")

    df = run_heatmap_cli(index_name)

    if df.empty:
        warn(f"No data could be generated for {index_name}.")
        _pause()
        return

    out_dir = "data/screener_output"
    os.makedirs(out_dir, exist_ok=True)

    safe_name = index_name.replace(" ", "_").lower()
    out_path = os.path.join(out_dir, f"{safe_name}_heatmap.csv")
    df.to_csv(out_path, index=False)

    _display_csv(
        out_path,
        f"Heatmap - {index_name}",
        "Sorted by Market Cap (Largest first). Green = Advancing, Red = Declining.",
    )
    print(f"\n  {dim(f'Saved to {out_path}')}")
    _pause()


def menu_mmi() -> None:
    """
    Run the Market Mood Index (MMI) Scraper.
    """
    _header("Market Mood Index (MMI)")
    run_mmi_cli()
    _pause()


def menu_ma_slope() -> None:
    """
    Run the Moving Average Slope analyzer.
    """
    _header("Moving Average Slope Analyzer")

    print(f"  {dim('Example Tickers:')} RELIANCE.NS, TCS.NS, AAPL, ^NSEI")
    ticker = input("  Enter Ticker (default: ^NSEI): ").strip()
    if not ticker:
        ticker = "^NSEI"

    print(f"\n  Analyzing MA slope for {ticker} over the last 30 days...\n")

    result = analyze_stock_ma_slope(ticker)

    if "error" in result:
        warn(result["error"])
        _pause()
        return

    slope = result["slope"]
    trend = result["trend"]

    print(f"  {bold('Trend Analysis Results')}")
    print(f"  Stock: {ticker}")
    print(f"  20-Day MA Slope (30-day window): {slope:.4f}")

    if slope > 0:
        color = "green"
    elif slope < 0:
        color = "red"
    else:
        color = "white"

    print(f"  Trend Strength & Direction: [{color}]{trend}[/{color}]\n")
    _pause()


def menu_squeeze() -> None:
    """
    Run the Momentum Squeeze Indicator analysis.

    Fetches price data for a user-chosen ticker and displays the last 10 candles
    of squeeze state and momentum direction.
    """
    _header("Momentum Squeeze Indicator")

    print(f"  {dim('Example Tickers:')} ^NSEI, RELIANCE.NS, BANKNIFTY.NS")
    ticker = input("  Enter Ticker (default: ^NSEI): ").strip() or "^NSEI"
    period = input("  Lookback period [6mo/1y/2y] (default: 6mo): ").strip() or "6mo"

    print(f"\n  Computing squeeze for {ticker} | period={period}...\n")

    df = run_squeeze_cli(symbol=ticker, period=period)

    if df.empty:
        warn("No squeeze data returned. Check the symbol and period.")
        _pause()
        return

    out_dir = "data/screener_output"
    os.makedirs(out_dir, exist_ok=True)
    safe = ticker.replace("^", "").replace(".", "_").lower()
    out_path = os.path.join(out_dir, f"squeeze_{safe}.csv")
    df.to_csv(out_path, index=False)

    _display_csv(
        out_path,
        f"Momentum Squeeze — {ticker}",
        "SqueezeOn=True → BB inside KC (coiled). Momentum>0 & lime = bullish impulse.",
    )
    print(f"\n  {dim(f'Saved to {out_path}')}")
    _pause()


def menu_pair_scanner(hist_dir: str) -> None:
    """
    Run the Engle-Granger Cointegration Pair Scanner.

    Parameters:
        hist_dir (str): Path to historical Parquet root directory.

    Returns:
        None: This function does not return any value.

    Raises:
        None: All internal exceptions are caught and handled.

    Complexity:
        Time: O(M^2 x W) where M is symbols scanned and W is lookback length.
        Space: O(M^2) for pairing combinations.

    Example:
        >>> menu_pair_scanner("data/historical")
    """
    _header("Cointegration Pair Scanner")

    daily_dir = os.path.join(hist_dir, "1d")
    if not os.path.isdir(daily_dir):
        warn(f"Daily directory '{daily_dir}' does not exist.")
        _pause()
        return

    parquet_files = [f for f in os.listdir(daily_dir) if f.endswith(".parquet")]
    if not parquet_files:
        warn(f"No parquet files found in '{daily_dir}'.")
        _pause()
        return

    print(f"  Total symbols available: {len(parquet_files)}")
    print(f"  {dim('Engle-Granger Cointegration Test (N*(N-1)/2 checks)')}")
    print()

    try:
        limit_in = input(
            "  Symbol scan limit (largest files first) [10-250, default 100]: "
        ).strip()
        symbol_limit = int(limit_in) if limit_in else 100
        if symbol_limit < 2:
            symbol_limit = 2
    except ValueError:
        warn("Invalid number. Using default 100.")
        symbol_limit = 100

    try:
        pval_in = input("  Max p-value threshold [0.001-0.20, default 0.05]: ").strip()
        max_pval = float(pval_in) if pval_in else 0.05
        if max_pval <= 0:
            max_pval = 0.05
    except ValueError:
        warn("Invalid float. Using default 0.05.")
        max_pval = 0.05

    try:
        max_pairs_in = input("  Max pairs to return [1-100, default 50]: ").strip()
        max_pairs = int(max_pairs_in) if max_pairs_in else 50
        if max_pairs <= 0:
            max_pairs = 50
    except ValueError:
        warn("Invalid number. Using default 50.")
        max_pairs = 50

    print(f"\n  Scanning top {symbol_limit} symbols with max p-val = {max_pval}...\n")

    try:
        df = run_pair_scanner_cli(
            daily_dir=daily_dir,
            max_pairs=max_pairs,
            max_pval=max_pval,
            symbol_limit=symbol_limit,
        )
    except Exception as exc:
        err(f"Pair scanning failed: {exc}")
        _pause()
        return

    if df.empty:
        warn("No cointegrated pairs found matching the criteria.")
        _pause()
        return

    out_dir = "data/screener_output"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "cointegrated_pairs.csv")
    df.to_csv(out_path, index=False)

    _display_csv(
        out_path,
        "Cointegrated Pairs Summary",
        "Spread Z-Score > 2.0 indicates potential arbitrage (SELL A / BUY B). "
        "< -2.0 is (BUY A / SELL B).",
    )
    print(f"\n  {dim(f'Saved to {out_path}')}")
    _pause()


def menu_nse_live() -> None:
    """
    Interactive Live NSE Data Hub powered by NseUtils.

    Exposes key on-demand live data endpoints (pre-market snapshot, live price,
    index constituents, FII/DII activity) via an interactive sub-menu. All
    network calls are isolated so a failure in one option does not affect others.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> menu_nse_live()
    """
    from src.nse_live.nse_utils import NseUtils

    _header(
        "Live NSE Data Hub",
        "Pre-market · Price Info · Index · FII/DII · Holidays",
    )
    tip("Each query makes a live request to NSE. Ensure internet is available.")

    sub_opts = [
        ("1", "Pre-Market Snapshot", "Live pre-market data (NIFTY 50, BANK, F&O…)"),
        ("2", "Live Price Info", "Real-time price, VWAP, circuits for a symbol"),
        ("3", "Index Constituents", "All stocks in a selected Nifty index"),
        ("4", "FII / DII Activity", "Today's institutional buying/selling"),
        ("5", "Trading Holidays", "NSE trading holiday calendar"),
        ("6", "Check Holiday Status", "Is a given date a trading holiday?"),
        ("0", "Back", ""),
    ]

    while True:
        print()
        print(_rule("─"))
        for num, label, hint in sub_opts:
            if num == "0":
                print(f"   {dim(num)}  {dim(label)}")
            elif hint:
                print(f"   {cyan(num)}  {bold(label)}  {dim(hint)}")
            else:
                print(f"   {cyan(num)}  {bold(label)}")
        print()

        sub = input(f"  {dim('Select')}: ").strip()

        if sub == "0":
            break

        # Initialise NseUtils fresh per query (re-cookies on each session)
        print(f"\n  {dim('Connecting to NSE…')}")
        try:
            nse = NseUtils()
        except Exception as exc:
            err(f"Failed to connect to NSE: {exc}")
            _pause()
            continue

        if sub == "1":
            _subheader("Pre-Market Snapshot")
            print(
                f"  {dim('Categories:')} "
                f"NIFTY 50 · Nifty Bank · Securities in F&O · Others · All"
            )
            cat = input("  Category [All]: ").strip() or "All"
            try:
                df_pm = nse.pre_market_info(category=cat)
                if df_pm.empty:
                    warn("No pre-market data returned.")
                else:
                    from rich import box
                    from rich.console import Console
                    from rich.table import Table

                    console = Console()
                    tbl = Table(
                        show_header=True,
                        header_style="bold cyan",
                        box=box.ROUNDED,
                    )
                    display_cols = [
                        c
                        for c in [
                            "lastPrice",
                            "change",
                            "pChange",
                            "totalTradedVolume",
                            "iep",
                        ]
                        if c in df_pm.columns
                    ]
                    tbl.add_column("Symbol", justify="left")
                    for c in display_cols:
                        tbl.add_column(c, justify="right")
                    for sym, row in df_pm.head(25).iterrows():
                        tbl.add_row(
                            str(sym),
                            *[
                                f"{row[c]:,.2f}" if pd.notna(row[c]) else ""
                                for c in display_cols
                            ],
                        )
                    console.print(tbl)
                    print(f"\n  {dim(f'{len(df_pm)} total rows (showing 25)')}")
            except Exception as exc:
                err(f"Pre-market query failed: {exc}")

        elif sub == "2":
            _subheader("Live Price Info")
            symbol = input("  NSE Symbol (e.g. RELIANCE): ").strip().upper()
            if not symbol:
                warn("No symbol entered.")
            else:
                try:
                    info = nse.price_info(symbol)
                    if not info:
                        warn(f"No data found for {symbol}.")
                    else:
                        print()
                        print(_rule("─"))
                        for k, v in info.items():
                            print(f"  {cyan(f'{k:<20}')} {bold(str(v))}")
                        print(_rule("─"))
                except Exception as exc:
                    err(f"Price info query failed: {exc}")

        elif sub == "3":
            _subheader("Index Constituents")
            print(
                f"  {dim('Examples:')} NIFTY 50 · NIFTY BANK · NIFTY IT · "
                f"NIFTY PHARMA"
            )
            index = input("  Index name [NIFTY 50]: ").strip() or "NIFTY 50"
            list_only = _confirm("Return symbol list only (vs full table)?")
            try:
                result = nse.get_index_details(index, list_only=list_only)
                if list_only and isinstance(result, list):
                    print(f"\n  {bold(str(len(result)))} symbols in {index}:")
                    print(
                        "  "
                        + "  ".join(result[:50])
                        + (" …" if len(result) > 50 else "")
                    )
                elif isinstance(result, pd.DataFrame) and not result.empty:
                    show_cols = [
                        c
                        for c in [
                            "lastPrice",
                            "change",
                            "pChange",
                            "totalTradedVolume",
                        ]
                        if c in result.columns
                    ]
                    print(result[show_cols].head(20).to_string())
                    print(f"\n  {dim(f'{len(result)} constituents (showing 20)')}")
                else:
                    warn("No data returned for that index.")
            except Exception as exc:
                err(f"Index query failed: {exc}")

        elif sub == "4":
            _subheader("FII / DII Activity (Today)")
            try:
                df_fii = nse.fii_dii_activity()
                if df_fii.empty:
                    warn("No FII/DII data returned.")
                else:
                    print(df_fii.to_string(index=False))
            except Exception as exc:
                err(f"FII/DII query failed: {exc}")

        elif sub == "5":
            _subheader("NSE Trading Holidays")
            try:
                holidays = nse.trading_holidays(list_only=True)
                print(f"\n  {bold(str(len(holidays)))} trading holidays:")
                for h in holidays:
                    print(f"  {dim('·')} {h}")
            except Exception as exc:
                err(f"Holidays query failed: {exc}")

        elif sub == "6":
            _subheader("Check Holiday Status")
            date_inp = (
                input("  Date in DD-MMM-YYYY (e.g. 02-Oct-2025) [today]: ").strip()
                or None
            )
            try:
                is_hol = nse.is_nse_trading_holiday(date_inp)
                if is_hol is None:
                    warn("Invalid date format provided.")
                elif is_hol:
                    warn(f"{date_inp or 'Today'} is a NSE TRADING HOLIDAY.")
                else:
                    ok(f"{date_inp or 'Today'} is a NORMAL TRADING DAY.")
            except Exception as exc:
                err(f"Holiday check failed: {exc}")

        else:
            warn(f"Invalid option '{sub}'.")

        _pause()


def menu_backtest(hist_dir: str, data_dir: str) -> None:
    """
    Interactive ML Classifier Backtester menu handler.

    Parameters:
        hist_dir (str): Path to historical Parquet root directory.
        data_dir (str): Path to root data directory.

    Returns:
        None

    Raises:
        None
    """
    _header("ML Classifier Backtester")
    symbol = _ask("Enter Stock Symbol (e.g. TCS)", "TCS").strip().upper()
    try:
        n_est_in = input("  Number of estimators [default 100]: ").strip()
        n_estimators = int(n_est_in) if n_est_in else 100
    except ValueError:
        warn("Invalid number. Using default 100.")
        n_estimators = 100

    try:
        max_depth_in = input("  Max depth [default 5]: ").strip()
        max_depth = int(max_depth_in) if max_depth_in else 5
    except ValueError:
        warn("Invalid number. Using default 5.")
        max_depth = 5

    price_path = os.path.join(hist_dir, "1d", f"{symbol}.parquet")
    if not os.path.exists(price_path):
        err(f"Historical Parquet file not found at: {price_path}")
        _pause()
        return

    try:
        print(f"\n  Loading price data for {symbol}...")
        df_prices = pd.read_parquet(price_path)
        if df_prices.empty or len(df_prices) < 20:
            err(f"Insufficient history for {symbol} ({len(df_prices)} bars).")
            _pause()
            return

        print(f"  Scanning for delivery percentage data in " f"{data_dir}/processed...")
        df_delivery = _get_delivery_history(os.path.join(data_dir, "processed"), symbol)
        if df_delivery is not None and not df_delivery.empty:
            ok(
                f"Aggregated {len(df_delivery)} records of "
                f"delivery percentage data."
            )
        else:
            warn("No delivery percentage data found. Defaulting to 0.0.")

        print(
            f"  Training Random Forest (n_estimators={n_estimators}, "
            f"max_depth={max_depth})..."
        )
        from rich.console import Console
        from rich.table import Table

        from src.nse_bhavcopy.backtester import NSEEventBacktester
        from src.nse_bhavcopy.ml_classifier import MLClassifier

        clf = MLClassifier(n_estimators=n_estimators, max_depth=max_depth)
        X, y = clf.prepare_features(df_prices, df_delivery)
        if len(X) < 10:
            err("Not enough feature rows generated to train/test.")
            _pause()
            return

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
        err(f"Backtest execution failed: {exc}")

    _pause()


def menu_fo_ban(data_dir: str) -> None:
    """
    Interactive F&O Ban list query.

    Parameters:
        data_dir (str): Path to root data directory.

    Returns:
        None

    Raises:
        None
    """
    _header("NSE F&O Ban Securities")
    try:
        from src.nse_bhavcopy.fo_ban import FOBanManager

        manager = FOBanManager(cache_dir=data_dir)
        ban_list = manager.fetch_fo_ban_list()
        if ban_list:
            ok(f"Found {len(ban_list)} securities in F&O ban:")
            for sym in sorted(ban_list):
                print(f"  {dim('·')} {bold(sym)}")
        else:
            ok("No securities are currently in the F&O ban period.")
    except Exception as exc:
        err(f"Failed to query F&O ban list: {exc}")

    _pause()


def menu_bhavcopy_sync(data_dir: str, hist_dir: str) -> None:
    """
    Interactive handler for Bhavcopy incremental OHLCV sync.

    Prompts user for days_back, TA recomputation flag, and delay between
    ZIP downloads, then calls BhavcopyIncrementalSync.run().

    Parameters:
        data_dir (str): Root data directory. | Writable path.
        hist_dir (str): Historical Parquet storage directory.

    Returns:
        None

    Raises:
        None

    Example:
        >>> menu_bhavcopy_sync("data", "data/historical")

    Performance:
        Time Complexity: O(D * N + S * N) [D days, S symbols, N rows/ZIP]
        Space Complexity: O(D * N)

    Edge Cases Handled:
        - No raw Bhavcopy ZIP found exits with informative error.
        - NSE holiday dates silently skipped.
    """
    from src.nse_bhavcopy.bhavcopy_incremental import BhavcopyIncrementalSync

    _header(
        "Bhavcopy Incremental Sync",
        "Downloads 1 ZIP per missing trading day — far faster than per-symbol API",
    )
    tip("Only updates symbols that already have a local Parquet (incremental path).")
    tip("New symbols with no history still need 'Sync Historical' first.")

    raw_dir = os.path.join(data_dir, "raw")

    days_back_str = _ask("Days back to check for missing data", "10")
    try:
        days_back = int(days_back_str)
    except ValueError:
        warn("Invalid number — using 10.")
        days_back = 10

    recompute = _confirm("Recompute TA indicators after sync? (recommended)")
    delay = _ask_float("Delay between ZIP downloads (seconds)", 1.0)

    zip_path = os.path.join(
        raw_dir,
        sorted([f for f in os.listdir(raw_dir) if f.endswith(".zip")])[-1]
        if os.path.isdir(raw_dir)
        and any(f.endswith(".zip") for f in os.listdir(raw_dir))
        else "",
    )
    if not zip_path or not os.path.exists(zip_path):
        err("No Bhavcopy ZIP found in data/raw. Run 'Build Master' first.")
        _pause()
        return

    with open(zip_path, "rb") as fh:
        raw_bytes = fh.read()

    dl = BhavcopyDownloader(
        raw_dir=raw_dir,
        processed_dir=os.path.join(data_dir, "processed"),
    )
    symbols = dl.get_eq_symbols(raw_bytes)
    if not symbols:
        err("Could not extract symbols from Bhavcopy ZIP.")
        _pause()
        return

    print(f"\n  {dim('Symbols loaded:')}  {bold(str(len(symbols)))}")
    if not _confirm(f"Start Bhavcopy sync for {len(symbols)} symbols?"):
        warn("Cancelled.")
        _pause()
        return

    syncer = BhavcopyIncrementalSync(
        data_dir=hist_dir,
        timeframe=DEFAULT_TIMEFRAME,
        raw_dir=raw_dir,
        rate_delay=delay,
        recompute_ta=recompute,
    )
    results = syncer.run(symbols, days_back=days_back, recompute_ta=recompute)

    ok_count = sum(v for v in results.values())
    needs_refresh = [s for s, v in results.items() if not v]
    ok(f"Sync complete  {ok_count}/{len(symbols)} symbols updated.")
    if needs_refresh:
        warn(
            f"{len(needs_refresh)} need full refresh (run Sync Historical): "
            + ", ".join(needs_refresh[:15])
            + (" …" if len(needs_refresh) > 15 else "")
        )

    _pause()

    _pause()


def menu_fyers_token() -> None:
    """
    Interactive handler to set the Fyers API access token.
    """
    from src.nse_bhavcopy.fyers_fetcher import FyersFetcher, exchange_auth_code

    _header(
        "Fyers API Token Setup",
        "Exchange an auth code for a daily access token.",
    )

    api_key = os.getenv("FYERS_API_KEY") or os.getenv("BROKER_API_KEY")
    api_secret = os.getenv("FYERS_API_SECRET") or os.getenv("BROKER_API_SECRET")

    if not api_key or not api_secret:
        err("FYERS_API_KEY/BROKER_API_KEY and Secret must be set in environment.")
        _pause()
        return

    fetcher = FyersFetcher()
    redirect = os.getenv(
        "FYERS_REDIRECT_URI", "https://trade.fyers.in/api-login/redirect-uri/index.html"
    )
    url = fetcher.login_url(redirect_uri=redirect)

    print(f"\n  {bold('Step 1:')} Open this URL to login:\n")
    print(f"  {cyan(url)}\n")
    print(
        f"  {bold('Step 2:')} After login, copy the '?code=' value from "
        "the redirect URL.\n"
    )

    code = _ask("Enter the auth code (or press Enter to cancel)", "")
    if not code:
        warn("Cancelled.")
        _pause()
        return

    token = exchange_auth_code(code, api_key, api_secret)
    if token:
        fetcher.set_token(token)
        ok(f"Token saved to {fetcher.token_cache}")
        tip("This token is valid for the rest of the trading day.")
    else:
        err("Failed to exchange code for token. Check credentials.")

    _pause()


# ===========================================================================
# REPL loop
# ===========================================================================


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
        - Invalid choices print a message and re-prompt.
        - KeyboardInterrupt exits cleanly.
    """
    processed_dir = os.path.join(data_dir, "processed")

    _print_banner()

    _DISPATCH: dict[str, Callable[[], None]] = {
        "1": lambda: menu_build_master(data_dir),
        "2": lambda: menu_sync_history(data_dir, hist_dir),
        "3": lambda: menu_sync_filtered(data_dir, hist_dir),
        "4": lambda: menu_screen(data_dir, hist_dir, processed_dir),
        "5": lambda: menu_status(hist_dir, data_dir),
        "6": lambda: menu_registry(data_dir, hist_dir),
        "7": lambda: menu_ta_dashboard(hist_dir),
        "8": lambda: menu_recompute_ta(hist_dir),
        "9": lambda: menu_liquid_etf(),
        "10": lambda: menu_minervini(),
        "11": lambda: menu_sector_rotation(),
        "12": lambda: menu_correlation(),
        "13": lambda: menu_heatmap(),
        "14": lambda: menu_mmi(),
        "15": lambda: menu_ma_slope(),
        "16": lambda: menu_squeeze(),
        "17": lambda: menu_nse_live(),
        "18": lambda: menu_pair_scanner(hist_dir),
        "19": lambda: menu_backtest(hist_dir, data_dir),
        "20": lambda: menu_fo_ban(data_dir),
        "21": lambda: menu_bhavcopy_sync(data_dir, hist_dir),
        "22": lambda: menu_fyers_token(),
    }

    while True:
        _print_main_menu()
        try:
            choice = input(f"  {dim('>')} ").strip()
        except KeyboardInterrupt:
            print(f"\n  {dim('Bye!')}\n")
            break

        if choice == "0" or choice.lower() == "exit":
            print(f"\n  {dim('Bye!')}\n")
            break

        handler = _DISPATCH.get(choice)
        if handler:
            handler()
        else:
            warn(f"'{choice}' is not a valid option — enter 0-21.")


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
        description="NSE Data Pipeline: build master → sync history → screen stocks",
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

    # ── build-master ──────────────────────────────────────────────────────
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

    # ── sync-history ──────────────────────────────────────────────────────
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
        "--limit", type=int, default=None, help="Maximum number of symbols to sync."
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

    # ── screen ────────────────────────────────────────────────────────────
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
        "--limit", type=int, default=None, help="Maximum symbols to screen."
    )
    p_screen.set_defaults(func=cmd_screen)

    # ── backtest ──────────────────────────────────────────────────────────
    p_backtest = sub.add_parser(
        "backtest",
        help="Run machine learning direction classifier and event backtest.",
    )
    p_backtest.add_argument(
        "--symbol",
        required=True,
        help="Ticker symbol to backtest (e.g. TCS)",
    )
    p_backtest.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        dest="n_estimators",
        help="Number of Random Forest estimators (default: 100)",
    )
    p_backtest.add_argument(
        "--max-depth",
        type=int,
        default=5,
        dest="max_depth",
        help="Maximum tree depth of the Random Forest classifier (default: 5)",
    )
    p_backtest.set_defaults(func=cmd_backtest)

    # ── fo-ban ────────────────────────────────────────────────────────────
    p_fo_ban = sub.add_parser(
        "fo-ban",
        help="Fetch and print the current active NSE F&O ban securities list.",
    )
    p_fo_ban.set_defaults(func=cmd_fo_ban)

    # ── bhavcopy-sync ─────────────────────────────────────────────────────
    p_bsync = sub.add_parser(
        "bhavcopy-sync",
        help=(
            "Fast incremental OHLCV update: downloads 1 Bhavcopy ZIP per "
            "missing trading day instead of per-symbol API calls."
        ),
    )
    p_bsync.add_argument(
        "--days",
        type=int,
        default=10,
        help="Max trading days back to look for missing data (default: 10).",
    )
    p_bsync.add_argument(
        "--timeframe",
        default=DEFAULT_TIMEFRAME,
        help=f"Candle timeframe (default: {DEFAULT_TIMEFRAME}; only 1d uses Bhavcopy).",
    )
    p_bsync.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of symbols updated (useful for testing).",
    )
    p_bsync.add_argument(
        "--no-ta",
        action="store_true",
        dest="no_ta",
        help="Skip TA indicator recomputation after appending (faster).",
    )
    p_bsync.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between Bhavcopy ZIP downloads (default: 1.0).",
    )
    p_bsync.set_defaults(func=cmd_bhavcopy_sync)

    # ── fyers-login ─────────────────────────────────────────────────────
    p_fl = sub.add_parser(
        "fyers-login",
        help="Print the Fyers login URL to get an authorization code.",
    )
    p_fl.add_argument(
        "--redirect-uri",
        default=None,
        dest="redirect_uri",
        help="Redirect URI registered in your Fyers app (default: https://trade.fyers.in/api-login/redirect-uri/index.html).",
    )
    p_fl.set_defaults(func=cmd_fyers_login)

    # ── fyers-token ────────────────────────────────────────────────────
    p_ft = sub.add_parser(
        "fyers-token",
        help="Exchange a Fyers auth code for an access token and cache it.",
    )
    p_ft.add_argument(
        "--code",
        required=True,
        help="Authorization code from the Fyers login redirect URL.",
    )
    p_ft.set_defaults(func=cmd_fyers_token)

    # ── menu (default) ────────────────────────────────────────────────────
    sub.add_parser("menu", help="Launch the interactive menu (default).")

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
        interactive_menu(data_dir=args.data_dir, hist_dir=args.hist_dir)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
