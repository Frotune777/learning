"""
File: src/cli/actions.py
Purpose: Non-interactive CLI subcommand handlers for the NSE data pipeline.

Dependencies:
External:
- pandas>=2.2.3: DataFrame utilities and Parquet reading
- rich>=13.9.4: Terminal tables and formatting
Internal:
- src.storage.equity_master: [NSEEquityMasterBuilder]
- src.storage.historical_sync: [HistoricalSync]
- src.storage.smc_db: [SMCDatabase]
- src.screener: [StockScreener]
- src.engine.smc: [calculate_smc]
- src.engine.smc_decision: [generate_smc_call, TradingCall]
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
- cmd_train_ml: Subcommand to train ML models.
- cmd_run_optimizer: Subcommand to run strategy optimizer.
- cmd_smc_scan: Subcommand to run Smart Money Concepts (SMC) scanner and persist calls.
- cmd_smc_calls: Subcommand to view and filter stored SMC trading calls.

Last Modified: 2026-10-15
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

from src.cli.formatters import (
    cyan,
    dim,
    err,
    green,
    ok,
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

    ok_count = sum(bool(v) for v in results.values())
    failed = [s for s, v in results.items() if not v]
    print(f"\n✔  Sync complete: {ok_count}/{len(symbols)} symbols succeeded.")
    if failed:
        print(f"!   Failed ({len(failed)}): {', '.join(failed[:20])}")


def cmd_screen(args: argparse.Namespace) -> None:
    """
    Execute the 'screen' CLI subcommand.
    """
    LOGGER.info("=== PHASE 3: STOCK SCREENING ===")

    processed_dir = args.processed_dir or os.path.join(args.data_dir, "processed")
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
    """
    from src.storage.bhavcopy_incremental import BhavcopyIncrementalSync

    LOGGER.info("=== BHAVCOPY INCREMENTAL SYNC ===")

    raw_dir: str = os.path.join(args.data_dir, "raw")
    limit = getattr(args, "limit", None)
    days_back: int = getattr(args, "days", 10)
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

    ok_count = sum(bool(v) for v in results.values())
    needs_refresh = [s for s, v in results.items() if not v]
    print(f"\n✔  Bhavcopy sync: {ok_count}/{len(symbols)} symbols updated.")
    if needs_refresh:
        print(
            f"!   {len(needs_refresh)} symbol(s) need full refresh "
            f"(run sync-history for these): "
            f"{', '.join(needs_refresh[:20])}"
        )


def cmd_fo_ban(args: argparse.Namespace) -> None:
    """
    Fetch and display the current NSE F&O ban securities.
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
        print(err(str(exc)))
        print(tip("Set FYERS_API_KEY or BROKER_API_KEY environment variable first."))
        sys.exit(1)


def cmd_fyers_token(args: argparse.Namespace) -> None:
    """
    Exchange a Fyers auth code for an access token and cache it locally.
    """
    from src.nse_bhavcopy.fyers_fetcher import FyersFetcher, exchange_auth_code

    api_key = os.getenv("FYERS_API_KEY") or os.getenv("BROKER_API_KEY")
    api_secret = os.getenv("FYERS_API_SECRET") or os.getenv("BROKER_API_SECRET")

    if not api_key or not api_secret:
        print(
            err(
                "FYERS_API_KEY and FYERS_API_SECRET "
                "(or BROKER_API_KEY / BROKER_API_SECRET) must be set as env vars."
            )
        )
        sys.exit(1)

    code = getattr(args, "code", "")
    if not code:
        print(err("--code is required. Run 'fyers-login' first."))
        sys.exit(1)

    token = exchange_auth_code(code, api_key, api_secret)
    if not token:
        print(err("Token exchange failed. Check your auth code and credentials."))
        sys.exit(1)

    fetcher = FyersFetcher()
    fetcher.set_token(token)
    print(f"\n{green('✔')}  Fyers access token saved to {fetcher.token_cache}")
    print(f"   {dim('Token is valid for one trading day.')}")
    print(f"   {dim('Run this command each morning before using the pipeline.')}")


def cmd_ml_anomaly(args: argparse.Namespace) -> None:
    """
    Run the ML anomaly detector on a specific symbol to find data quality issues.
    """
    symbol = args.symbol.strip().upper()
    price_path = os.path.join(args.hist_dir, "1d", f"{symbol}.parquet")
    if not os.path.exists(price_path):
        LOGGER.error("Historical Parquet file not found at: %s", price_path)
        sys.exit(1)

    try:
        df_prices = pd.read_parquet(price_path)

        from src.ml.anomaly_detector import AnomalyDetector

        detector = AnomalyDetector(contamination=0.02)
        clean_df = detector.filter_data_quality(df_prices)

        if len(clean_df) < len(df_prices):
            bad_dates = df_prices.index.difference(clean_df.index)
            print(
                f"\n⚠️  Found {len(bad_dates)} severe data quality errors (zero volume, huge splits)."
            )
            from src.cli.formatters import _confirm

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
                                df_prices.loc[bd, "Turnover"] = row["Turnover"].values[0]
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
                    df_prices.to_parquet(price_path)
                    print(
                        f"\n{ok('Healed')} {healed_count} rows and updated {price_path}!"
                    )
                    clean_df = detector.filter_data_quality(df_prices)

        if len(clean_df) < 25:
            print(f"Not enough data to run Isolation Forest on {symbol}.")
            return

        anomalies = detector.detect_anomalies(clean_df)

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


def cmd_train_ml(args: argparse.Namespace) -> None:
    """
    Execute the 'train-ml' CLI subcommand to train ML models.
    """
    LOGGER.info("=== ML MODEL TRAINING ===")
    from src.engine.orchestrator import ScanOrchestrator

    orchestrator = ScanOrchestrator()
    orchestrator.train_ml_models()


def cmd_run_optimizer(args: argparse.Namespace) -> None:
    """
    Execute the 'optimize' CLI subcommand to run the strategy optimizer.
    """
    LOGGER.info("=== STRATEGY OPTIMIZER ===")
    from src.engine.orchestrator import ScanOrchestrator

    orchestrator = ScanOrchestrator()
    orchestrator.run_optimizer()


# ===========================================================================
# Smart Money Concepts (SMC) Handlers
# ===========================================================================


def cmd_smc_scan(args: argparse.Namespace) -> None:
    """
    Scan historical Parquet data using Smart Money Concepts (SMC) and persist trading calls.

    Logic:
        1. Locate historical daily Parquets.
        2. Execute SMC analysis (BOS, CHoCH, Order Blocks, FVGs, Premium/Discount).
        3. Evaluate institutional entry confirmation via generate_smc_call().
        4. Persist qualified setups to the local SQLite database.
        5. Output a structured Rich summary table.
    """
    LOGGER.info("=== SMART MONEY CONCEPTS (SMC) SCANNER ===")

    hist_dir = getattr(args, "hist_dir", None) or Config.DEFAULT_HIST_DIR
    target_dir = Path(hist_dir)
    if (target_dir / "1d").exists():
        target_dir = target_dir / "1d"

    if not target_dir.exists():
        print(err(f"Historical directory not found at: {target_dir}"))
        sys.exit(1)

    limit: int | None = getattr(args, "limit", None)
    symbol_filter: str | None = getattr(args, "symbol", None)
    data_dir = getattr(args, "data_dir", None) or Config.DEFAULT_DATA_DIR
    db_path = os.path.join(data_dir, "smc_calls.sqlite")

    from src.engine.smc import calculate_smc
    from src.engine.smc_decision import generate_smc_call
    from src.storage.smc_db import SMCDatabase

    db = SMCDatabase(db_path=db_path)

    if symbol_filter:
        files = [target_dir / f"{symbol_filter.strip().upper()}.parquet"]
    else:
        files = sorted(list(target_dir.glob("*.parquet")))

    if limit:
        files = files[:limit]

    print(f"\n🔎 Scanning {len(files)} symbol(s) in {cyan(str(target_dir))}...")

    generated_calls = []
    scanned_count = 0

    for fpath in files:
        if not fpath.exists():
            continue

        sym = fpath.stem.replace(".NS", "")
        try:
            df = pd.read_parquet(fpath)
            if df.empty or len(df) < 30:
                continue

            df.columns = [c.lower() for c in df.columns]
            if not all(k in df.columns for k in ("open", "high", "low", "close")):
                continue

            scanned_count += 1
            smc_res = calculate_smc(df, swing_length=20, internal_length=5)
            call = generate_smc_call(sym, smc_res, df)

            if call:
                call_id = db.create_call(call)
                generated_calls.append((call_id, call))
        except Exception as exc:
            LOGGER.debug("Skipping %s due to calculation error: %s", sym, exc)
            continue

    print(f"\n{ok('SMC Scan Finished')}: Scanned {scanned_count} securities.")

    if not generated_calls:
        print(f"ℹ️  No high-probability SMC setups triggered currently in {cyan(str(target_dir))}.\n")
        return

    console = Console()
    table = Table(
        title=f"🎯 SMC Actionable Trading Decisions ({len(generated_calls)} Generated)",
        header_style="bold cyan",
    )
    table.add_column("ID", justify="center", style="dim")
    table.add_column("Symbol", style="bold")
    table.add_column("Direction", justify="center")
    table.add_column("Setup Type", style="yellow")
    table.add_column("Entry", justify="right")
    table.add_column("Stop Loss", justify="right", style="red")
    table.add_column("Target 1", justify="right", style="green")
    table.add_column("R:R", justify="right", style="bold")
    table.add_column("Status", justify="center")

    for cid, call in generated_calls:
        dir_style = "[bold green]BUY[/bold green]" if call.direction == "BUY" else "[bold red]SELL[/bold red]"
        table.add_row(
            str(cid),
            call.symbol,
            dir_style,
            call.setup_type,
            f"{call.entry_price:,.2f}",
            f"{call.stop_loss:,.2f}",
            f"{call.target_1:,.2f}",
            f"{call.risk_reward:.2f}",
            f"[cyan]{call.status}[/cyan]",
        )

    console.print()
    console.print(table)
    print(f"\n{ok('Saved')}: All calls committed to SQLite DB at: {dim(db_path)}\n")


def cmd_smc_calls(args: argparse.Namespace) -> None:
    """
    List and filter Smart Money Concepts (SMC) calls saved in local SQLite database.
    """
    data_dir = getattr(args, "data_dir", None) or Config.DEFAULT_DATA_DIR
    db_path = os.path.join(data_dir, "smc_calls.sqlite")

    from src.storage.smc_db import SMCDatabase

    db = SMCDatabase(db_path=db_path)
    status_filter = getattr(args, "status", None)
    calls = db.get_calls(status=status_filter)

    if not calls:
        filter_str = f" with status '{status_filter}'" if status_filter else ""
        print(f"\nℹ️  No SMC trading calls found in local database{filter_str}.\n")
        return

    console = Console()
    table = Table(
        title=f"📋 Stored SMC Trading Calls ({len(calls)} Found)",
        header_style="bold cyan",
    )
    table.add_column("ID", justify="center", style="dim")
    table.add_column("Date", style="dim")
    table.add_column("Symbol", style="bold")
    table.add_column("Direction", justify="center")
    table.add_column("Setup", style="yellow")
    table.add_column("Entry", justify="right")
    table.add_column("SL", justify="right", style="red")
    table.add_column("TP 1", justify="right", style="green")
    table.add_column("TP 2", justify="right", style="green")
    table.add_column("R:R", justify="right", style="bold")
    table.add_column("Status", justify="center")

    for c in calls:
        dir_style = "[bold green]BUY[/bold green]" if c["direction"] == "BUY" else "[bold red]SELL[/bold red]"
        status_color = "green" if c["status"] == "TRIGGERED" else "cyan" if c["status"] == "PENDING" else "red"

        table.add_row(
            str(c["id"]),
            str(c["timestamp"])[:10],
            c["symbol"],
            dir_style,
            c["setup_type"],
            f"{c['entry_price']:,.2f}",
            f"{c['stop_loss']:,.2f}",
            f"{c['target_1']:,.2f}",
            f"{c['target_2']:,.2f}",
            f"{c['risk_reward']:.2f}",
            f"[{status_color}]{c['status']}[/{status_color}]",
        )

    console.print()
    console.print(table)
    print()


def cmd_repair_ta(args: argparse.Namespace) -> None:
    """Walk hist_dir/1d, detect Parquets whose last row has NaN RSI_14, and re-run add_ta_indicators in-place."""
    from pathlib import Path
    target_dir = getattr(args, "hist_dir", Config.DEFAULT_HIST_DIR)
    p1d = Path(target_dir) / "1d" if (Path(target_dir) / "1d").is_dir() else Path(target_dir)
    files = sorted(p1d.glob("*.parquet"))

    print(f"\nScanning {len(files)} Parquet files in {p1d} for stale/NaN TA indicators...")
    checked_count = len(files)
    repaired_count = 0
    from src.nse_bhavcopy.ta_indicators import add_ta_indicators

    for f in files:
        try:
            df = pd.read_parquet(f)
            if df.empty or len(df) < 15:
                continue
            if "RSI_14" not in df.columns or pd.isna(df["RSI_14"].iloc[-1]):
                base_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
                if len(base_cols) >= 4:
                    df_fixed = add_ta_indicators(df[base_cols])
                    df_fixed.to_parquet(f)
                    repaired_count += 1
        except Exception as e:
            LOGGER.warning("Failed TA repair for %s: %s", f.stem, e)

    print(f"\n  Checked: {checked_count} files | Repaired: {repaired_count} files.")
    print(ok(f"TA backfill complete. {repaired_count}/{checked_count} files updated in-place."))