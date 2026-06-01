"""
File: src/cli/actions.py
Purpose: Non-interactive CLI subcommand handlers for the NSE data pipeline.

Dependencies:
External:
- pandas>=2.2.3: DataFrame utilities and Parquet reading
Internal:
- src.storage.equity_master: [NSEEquityMasterBuilder]
- src.storage.historical_sync: [HistoricalSync]
- src.screener: [StockScreener]
- src.core.symbol_utils: [find_latest_master, load_symbols, load_symbols_from_bhavcopy,
                           load_symbols_strict, get_delivery_history_from_bhavcopy]

Key Components:
Functions:
- cmd_build_master: Subcommand to build/refresh the equity master table.
- cmd_sync_history: Subcommand to sync historical Parquet files.
- cmd_screen: Subcommand to run the technical screener.
- cmd_backtest: Subcommand to run ML backtest for a symbol.
- cmd_bhavcopy_sync: Subcommand for fast incremental OHLCV update.
- cmd_fo_ban: Subcommand to display F&O ban list.
- cmd_fyers_login: Subcommand to print Fyers login URL.
- cmd_fyers_token: Subcommand to exchange Fyers auth code.
- cmd_ml_anomaly: Subcommand to run ML data anomaly detection.

Last Modified: 2026-05-31
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import sys
from datetime import datetime

import pandas as pd

from src.cli.formatters import (
    cyan,
    dim,
    err,
    green,
    tip,
)
from src.core.config import Config
from src.core.symbol_utils import (
    find_latest_master,
    get_delivery_history_from_bhavcopy,
    load_symbols_from_bhavcopy,
    load_symbols_strict,
)
from src.screener import StockScreener
from src.storage.equity_master import NSEEquityMasterBuilder
from src.storage.historical_sync import HistoricalSync

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
LOGGER: logging.Logger = logging.getLogger("nse_pipeline")


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
    master_path = find_latest_master(args.data_dir)
    cap_filter = getattr(args, "cap_filter", None)
    index_filter = getattr(args, "index_filter", None)
    limit = getattr(args, "limit", None)

    if source == "bhavcopy":
        symbols = load_symbols_from_bhavcopy(
            raw_dir=raw_dir,
            cap_filter=cap_filter,
            index_filter=index_filter,
            master_path=master_path,
            limit=limit,
        )
    else:
        symbols = load_symbols_strict(
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
        df_delivery = get_delivery_history_from_bhavcopy(processed_dir, symbol)

        from rich.console import Console
        from rich.table import Table

        from src.ml.ml_classifier import MLClassifier
        from src.nse_bhavcopy.backtester import NSEEventBacktester

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

    symbols = load_symbols_from_bhavcopy(
        raw_dir=raw_dir,
        master_path=None,
        limit=limit,
    )

    syncer = BhavcopyIncrementalSync(
        data_dir=args.hist_dir,
        timeframe=getattr(args, "timeframe", Config.DEFAULT_TIMEFRAME),
        raw_dir=raw_dir,
        rate_delay=delay,
    )
    results = syncer.run(symbols, days_back=days_back)

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


def cmd_ml_anomaly(args: argparse.Namespace) -> None:
    """
    Run the ML anomaly detector on a specific symbol to find data quality issues or smart money footprints.

    Parameters:
        args (argparse.Namespace): Parsed command-line arguments.
    """
    symbol = args.symbol.strip().upper()
    price_path = os.path.join(args.hist_dir, "1d", f"{symbol}.parquet")
    if not os.path.exists(price_path):
        LOGGER.error("Historical Parquet file not found at: %s", price_path)
        sys.exit(1)

    try:
        import pandas as pd

        df_prices = pd.read_parquet(price_path)

        from src.ml.anomaly_detector import AnomalyDetector

        detector = AnomalyDetector(contamination=0.02)

        # 1. Show Data Quality Issues Removed
        clean_df = detector.filter_data_quality(df_prices)

        if len(clean_df) < len(df_prices):
            bad_dates = df_prices.index.difference(clean_df.index)
            print(
                f"\n⚠️  Found {len(bad_dates)} severe data quality errors (zero volume, huge splits)."
            )
            from src.cli.formatters import _confirm, cyan, err, ok

            if _confirm(
                f"Auto-heal these {len(bad_dates)} dates using NSE Bhavcopy?",
                default=True,
            ):
                from src.storage.downloader import BhavcopyDownloader

                dl = BhavcopyDownloader()
                healed_count = 0
                for bd in bad_dates:
                    try:
                        print(f"  Fetching Bhavcopy for {bd.strftime('%Y-%m-%d')}...")
                        raw_bytes = dl.download_raw_bhavcopy(bd)
                        df_bhav = dl.parse_bhavcopy_ohlcv(raw_bytes, bd)
                        row = df_bhav[df_bhav["Symbol"] == symbol]
                        if not row.empty:
                            df_prices.loc[bd, "Volume"] = row["Volume"].values[0]
                            if "Turnover" in row.columns:
                                df_prices.loc[bd, "Turnover"] = row["Turnover"].values[
                                    0
                                ]
                            healed_count += 1
                        else:
                            print(
                                f"  {cyan(symbol)} not found in Bhavcopy for {bd.strftime('%Y-%m-%d')}"
                            )
                    except Exception as e:
                        print(
                            f"  {err('Failed to heal')} {bd.strftime('%Y-%m-%d')}: {e}"
                        )

                if healed_count > 0:
                    # Save healed df back to parquet
                    df_prices.to_parquet(price_path)
                    print(
                        f"\n{ok('Healed')} {healed_count} rows and updated {price_path}!"
                    )
                    # Re-run filter_data_quality on the healed data
                    clean_df = detector.filter_data_quality(df_prices)

        # 2. Run ML Anomaly Detection on Clean Data
        if len(clean_df) < 25:
            print(f"Not enough data to run Isolation Forest on {symbol}.")
            return

        anomalies = detector.detect_anomalies(clean_df)

        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(
            title=f"🚨 ML Anomalies Detected for {symbol}", style="bold magenta"
        )
        table.add_column("Date", style="cyan")
        table.add_column("Close", justify="right", style="green")
        table.add_column("Daily Ret", justify="right")
        table.add_column("Vol Z-Score", justify="right")
        table.add_column("HL Spread", justify="right")
        table.add_column("Anomaly Score", justify="right", style="red")

        for idx, row in anomalies.tail(15).iterrows():
            dret = f"{row['Daily_Return']*100:.2f}%"
            volz = f"{row['Vol_ZScore']:.2f}"
            hl = f"{row['HL_Spread_Pct']*100:.2f}%"
            score = f"{row['Anomaly_Score']:.3f}"
            dt_str = idx.strftime("%Y-%m-%d")
            table.add_row(dt_str, f"{row['Close']:.2f}", dret, volz, hl, score)

        print("")
        console.print(table)
        print(
            "\nNote: Negative anomaly scores indicate statistically significant outlier days."
        )

    except Exception as exc:
        LOGGER.error("ML Anomaly detection failed: %s", exc)
        sys.exit(1)
