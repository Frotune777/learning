"""
File: src/cli/menus.py
Purpose: Interactive REPL menu handlers for the NSE data pipeline CLI.
Last Modified: 2026-05-31
"""

import argparse
import glob
import logging
import os
import structlog
from collections.abc import Callable
from datetime import datetime

import pandas as pd
from tqdm import tqdm

from src.cli.actions import (
    cmd_ml_anomaly,
)
from src.cli.formatters import (
    _ask,
    _ask_float,
    _confirm,
    _display_csv,
    _header,
    _pause,
    _print_banner,
    _rule,
    _subheader,
    bold,
    cyan,
    dim,
    err,
    green,
    ok,
    red,
    tip,
    warn,
    white,
    yellow,
)
from src.cli.visual import VisualUI
from src.cli.reporter import ScreenerReporter
from src.core.config import SCREENER_STRATEGIES, Config, UserPrefs
from src.core.decorators import dry_run_capable
from src.core.symbol_utils import (
    combine_strings,
    find_latest_master,
    get_delivery_history_from_bhavcopy,
    load_symbols,
)
from src.core.utils import get_fyers_fetcher, get_nse_utils
from src.nse_bhavcopy.correlation import run_correlation_cli
from src.nse_bhavcopy.heatmap import run_heatmap_cli
from src.nse_bhavcopy.ma_slope import analyze_stock_ma_slope
from src.nse_bhavcopy.sector_rotation import run_sector_rotation_cli
from src.nse_bhavcopy.ta_indicators import add_ta_indicators, calculate_technical_score
from src.scanners.etf_screener import run_liquid_etf_screener
from src.scanners.minervini_screener import run_minervini_cli
from src.scanners.momentum_squeeze import run_squeeze_cli
from src.scanners.pair_scanner import run_pair_scanner_cli
from src.scrapers.mmi_scraper import run_mmi_cli
from src.screener import StockScreener
from src.storage.downloader import BhavcopyDownloader
from src.storage.equity_master import NSEEquityMasterBuilder
from src.storage.historical_sync import HistoricalSync
from src.storage.sync_registry import SyncRegistry

logger = structlog.get_logger("nse_pipeline")

# ---------------------------------------------------------------------------
# Screener Strategy Configuration — imported from src.core.config
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

# _find_latest_master, _load_symbols, _get_delivery_history, combine_strings
# are imported from src.core.symbol_utils at the top of this file.


def _find_latest_master(data_dir: str) -> str | None:
    """Thin wrapper around src.core.symbol_utils.find_latest_master."""
    return find_latest_master(data_dir)


def _load_symbols(
    master_path: str | None,
    cap_filter: str | None = None,
    index_filter: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """Thin wrapper around src.core.symbol_utils.load_symbols."""
    return load_symbols(master_path, cap_filter, index_filter, limit)


def _get_delivery_history(processed_dir: str, symbol: str) -> pd.DataFrame | None:
    """Thin wrapper around src.core.symbol_utils.get_delivery_history_from_bhavcopy."""
    return get_delivery_history_from_bhavcopy(processed_dir, symbol)


# ---------------------------------------------------------------------------
# Menu Display (Declarative Configuration)
# ---------------------------------------------------------------------------

MENU_SECTIONS = {
    "DATA": [
        (
            "1",
            "Build / Refresh Equity Master",
            "menu_build_master",
            "downloads sec_list + index data",
        ),
        (
            "2",
            "Sync Historical  ─ All Symbols",
            "menu_sync_history",
            "all Bhavcopy EQ symbols",
        ),
        (
            "3",
            "Sync Historical  ─ Filtered",
            "menu_sync_filtered",
            "by cap, index, or count",
        ),
    ],
    "ANALYSIS": [
        ("4", "Run Technical Screener", "menu_screen", "final / swing / super lists"),
        (
            "7",
            "TA Dashboard  ─ Single Stock",
            "menu_ta_dashboard",
            "RSI, MACD, Bollinger, ADX…",
        ),
        (
            "8",
            "Recompute TA Indicators",
            "menu_recompute_ta",
            "refresh all local Parquet files",
        ),
        (
            "24",
            "Strategy Inspector",
            "menu_strategy_inspector",
            "all 13 strategy signals for one stock",
        ),
        (
            "25",
            "Consensus Leaderboard",
            "menu_consensus_leaderboard",
            "top stocks ranked by multi-strategy agreement",
        ),
    ],
    "STATUS": [
        ("5", "Parquet Sync Status", "menu_status", "rows, date ranges per symbol"),
        ("6", "Sync Registry", "menu_registry", "pending / failed / ok breakdown"),
        (
            "26",
            "Data Quality & Auto-Healer",
            "menu_data_quality",
            "scan master symbols and fix data gaps",
        ),
    ],
    "QUANTITATIVE": [
        ("9", "Liquid ETF Screener", "menu_liquid_etf", "top liquid ETFs per sector"),
        (
            "10",
            "Mark Minervini Template",
            "menu_minervini",
            "VCP, RS Rating & Trend Screen",
        ),
        (
            "11",
            "Sector Rotation Chart",
            "menu_sector_rotation",
            "JdK RS-Ratio Quadrant Analysis",
        ),
        (
            "12",
            "Correlation Matrix",
            "menu_correlation",
            "Cross-asset return correlation",
        ),
        ("13", "Nifty Indices Heatmap", "menu_heatmap", "Constituents performance"),
        ("14", "Market Mood Index (MMI)", "menu_mmi", "Live sentiment scraper"),
        ("15", "Moving Average Slope", "menu_ma_slope", "Trend angle analyzer"),
        (
            "16",
            "Momentum Squeeze Indicator",
            "menu_squeeze",
            "BB / KC coiled-spring detector",
        ),
        (
            "17",
            "Live NSE Data Hub",
            "menu_nse_live",
            "Pre-market, price info, option chain…",
        ),
        (
            "18",
            "Cointegration Pair Scanner",
            "menu_pair_scanner",
            "Engle-Granger pairs from local parquet universe",
        ),
        (
            "19",
            "ML Classifier Backtester",
            "menu_backtest",
            "Random Forest & Event Backtest on symbol",
        ),
        (
            "20",
            "View F&O Ban List",
            "menu_fo_ban",
            "Fetch current NSE F&O ban securities",
        ),
        (
            "21",
            "Bhavcopy Incremental Sync",
            "menu_bhavcopy_sync",
            "Batch OHLCV update — 1 ZIP/day instead of 800+ API calls",
        ),
        (
            "22",
            "Set Fyers API Token",
            "menu_fyers_token",
            "Configure Fyers access token for historical data",
        ),
        (
            "23",
            "ML Data Anomaly Detector",
            "menu_ml_anomaly",
            "Identify bad ticks or smart money footprints",
        ),
    ],
}


# Singleton VisualUI and Reporter instances (shared by all menu functions)
_UI = VisualUI()
_REPORTER = ScreenerReporter()


def _print_main_menu() -> None:
    """Render the top-level menu using VisualUI for premium aesthetics."""
    sections_rich: dict[str, list[dict]] = {}
    for section_name, items in MENU_SECTIONS.items():
        opts = []
        for num, label, _, hint in items:
            opts.append({"id": num, "name": label, "emoji": "", "status": "Ready", "details": hint})
        sections_rich[section_name] = opts
    # Append Exit
    sections_rich["EXIT"] = [
        {"id": "0", "name": "Exit", "emoji": "❌", "status": "", "details": "Close application"}
    ]
    _UI.render_menu("NSE DATA PIPELINE — MAIN MENU", sections_rich)


# ---------------------------------------------------------------------------
# Interactive menu — action handlers
# ---------------------------------------------------------------------------


def menu_build_master(data_dir: str) -> None:
    """Interactive handler for building the equity master table."""
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
        logger.info("master_built", path=path, delay=delay)
    except RuntimeError as exc:
        err(f"Build failed: {exc}")
        logger.error("master_build_failed", error=str(exc))

    _pause()


@dry_run_capable
def menu_sync_history(
    data_dir: str,
    hist_dir: str,
    cap_filter: str | None = None,
    index_filter: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    """Interactive handler for syncing historical Parquet data."""
    master_path = _find_latest_master(data_dir)
    symbols = _load_symbols(
        master_path, cap_filter=cap_filter, index_filter=index_filter, limit=limit
    )

    if not symbols:
        err("No symbols found. Run 'Build Master' first.")
        _pause()
        return

    print(f"\n  {dim('Symbols loaded:')}  {bold(str(len(symbols)))}", end="")
    if cap_filter:
        print(f"  {dim('cap=')} {cap_filter}", end="")
    if index_filter:
        print(f"  {dim('index=')} {index_filter}", end="")
    print()

    tf = _ask("Timeframe  (1d / 1w / 1mo)", Config.DEFAULT_TIMEFRAME)
    start = _ask("Start date (YYYY-MM-DD)", Config.DEFAULT_START_DATE)
    delay = _ask_float("Rate delay between requests (seconds)", 0.5)

    if dry_run:
        ok(f"Dry run: Would sync {len(symbols)} symbols with {tf} timeframe")
        _pause()
        return

    hs = HistoricalSync(
        data_dir=hist_dir, timeframe=tf, start_date=start, rate_delay=delay
    )

    # Use tqdm for progress indication
    results = {}
    for symbol in tqdm(symbols, desc="Syncing symbols"):
        results[symbol] = hs.sync_one(symbol)

    ok_count = sum(v for v in results.values())
    failed = [s for s, v in results.items() if not v]

    ok(f"Sync complete  {ok_count}/{len(symbols)} succeeded")
    if failed:
        limit = Config.DISPLAY_LIMITS["symbol_preview"]
        warn(
            f"{len(failed)} failed: {', '.join(failed[:limit])}"
            + (" …" if len(failed) > limit else "")
        )

    logger.info("sync_completed", succeeded=ok_count, failed=len(failed))
    _pause()


def menu_sync_filtered(data_dir: str, hist_dir: str) -> None:
    """Interactive handler for syncing with user-specified filters."""
    _header("Sync Historical Data — Filtered")

    prefs = UserPrefs()

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

    limit_str = input("  Max symbols (Enter = all): ").strip()
    limit = int(limit_str) if limit_str else None

    # Remember preferences
    if cap:
        prefs.set_last("last_cap_filter", cap)
    if idx:
        prefs.set_last("last_index_filter", idx)

    menu_sync_history(
        data_dir=data_dir,
        hist_dir=hist_dir,
        cap_filter=cap,
        index_filter=idx,
        limit=limit,
    )


def _display_strategy_results(csv_path: str, name: str, description: str) -> None:
    """Display a single strategy's results."""
    if os.path.exists(csv_path):
        _display_csv(csv_path, name, description)
    else:
        warn(f"No results generated for {name} today.")


def _screener_results_menu(hist_dir: str, date_str: str) -> None:
    """Sub-menu for browsing screener output files."""
    final_csv = os.path.join(hist_dir, f"final_list_{date_str}.csv")
    swing_csv = os.path.join(hist_dir, f"swing_list_{date_str}.csv")
    super_csv = os.path.join(hist_dir, f"super_list_{date_str}.csv")

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

        # Display strategies from declarative config
        for idx, strategy in enumerate(SCREENER_STRATEGIES, start=4):
            csv_path = os.path.join(
                hist_dir, f"{strategy['file_prefix']}_{date_str}.csv"
            )
            if os.path.exists(csv_path):
                print(f"   {cyan(str(idx))}  {strategy['name']} {dim('Strategy')}")
            else:
                print(f"   {dim(str(idx))}  {dim(strategy['name'] + ' (No Results)')}")

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
            for strategy in SCREENER_STRATEGIES:
                csv_path = os.path.join(
                    hist_dir, f"{strategy['file_prefix']}_{date_str}.csv"
                )
                if os.path.exists(csv_path):
                    df_strat = pd.read_csv(csv_path)
                    if not df_strat.empty:
                        df_strat.insert(1, "Strategy", strategy["name"])
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
                        agg_dict[col] = combine_strings
                    elif col in ["Target", "Stop Loss"]:
                        agg_dict[col] = lambda x: combine_strings(
                            f"{float(v):.2f}" for v in x if pd.notna(v)
                        )

                grouped_df = combined_df.groupby("NSE Code").agg(agg_dict).reset_index()

                if "Total Traded Value" in grouped_df.columns:
                    grouped_df = grouped_df.sort_values(
                        by="Total Traded Value", ascending=False
                    )

                combined_path = os.path.join(
                    hist_dir, f"view_all_grouped_{date_str}.csv"
                )
                grouped_df.to_csv(combined_path, index=False)
                _display_csv(
                    combined_path,
                    "Grouped Advanced Strategies Output",
                    "Master view of all advanced strategy triggers today, intelligently grouped by stock.",  # noqa: E501
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
                if 4 <= c_idx < 4 + len(SCREENER_STRATEGIES):
                    strategy = SCREENER_STRATEGIES[c_idx - 4]
                    csv_path = os.path.join(
                        hist_dir, f"{strategy['file_prefix']}_{date_str}.csv"
                    )
                    _display_strategy_results(
                        csv_path, strategy["name"], strategy["description"]
                    )
                else:
                    warn(f"Invalid choice '{choice}'.")
            except ValueError:
                warn(f"Invalid choice '{choice}'.")

        _pause()


def menu_screen(data_dir: str, hist_dir: str, processed_dir: str) -> None:
    """Interactive handler for running the technical screener."""
    _UI.render_header(
        "TECHNICAL SCREENER",
        "Scans synced Parquet data for technical setups · Bull Run + CAR + Swing + 13 Strategies",
    )

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
    save_to_disk = _confirm("Automatically save all 5+ analyzed & filtered CSVs to disk?")

    screener.screen_stocks(top_250_path=top_csv, date_obj=now, save_to_disk=save_to_disk)

    ok("Screening complete")
    if save_to_disk:
        ok(f"All standard reports exported to {hist_dir}")
    else:
        info("Results computed in-memory (no files written yet)")
    logger.info("screening_completed", date=now.strftime("%Y-%m-%d"))

    # ---- Upgraded results display (replaces raw CSV viewer) ----
    df_analyzed = getattr(screener, "df_analyzed", None)
    if df_analyzed is None:
        analyzed_csv = os.path.join(
            hist_dir, f"top_250_analyzed_{now.strftime('%Y%m%d')}.csv"
        )
        if os.path.exists(analyzed_csv):
            df_analyzed = pd.read_csv(analyzed_csv)

    if df_analyzed is not None and not df_analyzed.empty:
        _REPORTER.print_summary_table(
            df_analyzed,
            title=f"ANALYSIS RESULTS — {now.strftime('%Y-%m-%d')}",
        )
    else:
        err("No analysis results to display.")
        _pause()


def menu_status(hist_dir: str, data_dir: str) -> None:
    """Show sync status for all symbols in the master table."""
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
        _subheader(f"Top {Config.DISPLAY_LIMITS['top_synced']} Synced Symbols")
        print(
            synced.head(Config.DISPLAY_LIMITS["top_synced"])[
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
        limit = Config.DISPLAY_LIMITS["symbol_preview"]
        _subheader(f"First {limit} Unsynced  ({len(missing)} total)")
        print("  " + "  ".join(missing["symbol"].head(limit).tolist()))

    _pause()


def menu_registry(data_dir: str, hist_dir: str) -> None:
    """Show the sync registry summary."""
    _header("Sync Registry", "Pending · OK · Failed breakdown")

    tf = _ask("Timeframe", Config.DEFAULT_TIMEFRAME)
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
        limit = Config.DISPLAY_LIMITS["symbol_preview"]
        _subheader(f"Failed Symbols  ({len(failed)} total)")
        print(
            failed.head(limit)[["symbol", "fail_count", "last_bar_date"]].to_string(
                index=False
            )
        )

    pending_queue = reg.pending_symbols()
    print(f"\n  {dim('Next sync queue:')} {bold(str(len(pending_queue)))} symbols")
    if pending_queue:
        limit = Config.DISPLAY_LIMITS["symbol_preview"] // 3
        print(f"  {dim('Next 5:')} {', '.join(pending_queue[:limit])}")

    _pause()


def menu_data_quality(hist_dir: str, data_dir: str) -> None:
    """Scan all master symbols for data quality and provide automated healing."""
    _header("Data Quality & Auto-Healer", "Scan for data gaps, low coverage, or missing parquets")

    master_path = _find_latest_master(data_dir)
    if master_path is None:
        err("No master table found.")
        tip("Run option [1] to build the master first.")
        _pause()
        return

    builder = NSEEquityMasterBuilder(output_dir=data_dir)
    symbols = builder.get_symbols(master_path)
    if not symbols:
        err("No symbols loaded from Equity Master.")
        _pause()
        return

    print(f"\n  {dim('Scanning')} {bold(str(len(symbols)))} {dim('symbols in master Equity list...')}")
    
    hs = HistoricalSync(data_dir=hist_dir)
    status_df = hs.status(symbols)

    total_symbols = len(status_df)
    missing = status_df[status_df["rows"] == 0]
    low_coverage = status_df[(status_df["rows"] > 0) & (status_df["coverage_pct"] < 95.0)]
    healthy = status_df[(status_df["rows"] > 0) & (status_df["coverage_pct"] >= 95.0)]

    # Load failed symbols
    failed_symbols = hs._load_failed_symbols()

    # Display System Quality Audit Panel
    from rich.panel import Panel
    from rich.table import Table
    from rich.console import Console
    console = Console()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row(dim("Total Equities in Master:"), bold(str(total_symbols)))
    table.add_row(green("Healthy Data (>=95% Coverage):"), bold(str(len(healthy))))
    table.add_row(yellow("Low Coverage (<95% Coverage):"), bold(str(len(low_coverage))))
    table.add_row(red("Missing Parquet Cache:"), bold(str(len(missing))))
    table.add_row(dim("Failed Sync Blacklist (failed_symbols.csv):"), bold(str(len(failed_symbols))))

    panel = Panel(
        table,
        title="[bold cyan]DATA QUALITY SYSTEM AUDIT[/bold cyan]",
        border_style="cyan",
        expand=False,
    )
    console.print(panel)

    # Show low quality symbols if any
    if not missing.empty:
        print(f"\n  {red('● Missing Parquets')} ({len(missing)}):")
        preview = missing["symbol"].head(10).tolist()
        print(f"    {dim(', '.join(preview))}{' ...' if len(missing) > 10 else ''}")

    if not low_coverage.empty:
        print(f"\n  {yellow('● Low Coverage Equities')} ({len(low_coverage)}):")
        preview = []
        for _, r in low_coverage.head(5).iterrows():
            preview.append(f"{r['symbol']} ({r['coverage_pct']:.1f}%)")
        print(f"    {dim(', '.join(preview))}{' ...' if len(low_coverage) > 5 else ''}")

    to_heal = sorted(list(set(missing["symbol"].tolist()) | set(low_coverage["symbol"].tolist())))

    if not to_heal:
        ok("All symbols have healthy historical Parquet data (>=95% coverage)!")
        _pause()
        return

    print(f"\n  {bold(yellow(f'Total Unhealthy / Missing symbols to heal: {len(to_heal)}'))}")

    # Give interactive options
    print(f"\n  {dim('Interactive Healer Menu:')}")
    print(f"    {bold('H')}. Auto-Heal Data Gaps (targeted overwrite sync of {len(to_heal)} symbols)")
    print(f"    {bold('F')}. Clear Failed Sync Blacklist ({len(failed_symbols)} symbols)")
    print(f"    {bold('Q')}. Quit to Main Menu")

    choice = input(f"\n  {dim('>')} ").strip().upper()

    if choice == "H":
        if not _confirm(f"Start targeted auto-healing of {len(to_heal)} symbols?"):
            warn("Cancelled.")
            _pause()
            return
        
        ok("Initializing Auto-Healer pipeline...")
        # Targeted Sync with resume=False to force refreshing/backfilling the parquets
        hs.sync(to_heal, resume=False)
        ok("Auto-healing process completed!")
    elif choice == "F":
        path = os.path.join(hist_dir, "failed_symbols.csv")
        if os.path.exists(path):
            try:
                os.remove(path)
                ok("Successfully cleared failed_symbols.csv blacklist!")
            except Exception as e:
                err(f"Failed to clear blacklist: {e}")
        else:
            warn("No blacklist file found.")
    else:
        warn("Quit healing.")

    _pause()


def menu_ta_dashboard(hist_dir: str, symbol: str | None = None) -> None:
    """Display a console dashboard for a single stock's TA indicators."""
    _header(
        "TA Dashboard — Single Stock",
        "RSI · MACD · Bollinger · ADX · ATR · CCI · Score",
    )

    if not symbol:
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

        # Extract indicators
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

        # Helper functions
        def _fmt(v: object) -> str:
            return f"{float(v):,.2f}" if v is not None and not pd.isna(v) else "N/A"

        def _cmp_str(price: float, ma: object) -> str:
            if ma is None or pd.isna(ma):
                return dim("N/A")
            return green("ABOVE") if price > float(ma) else red("BELOW")

        # RSI analysis
        rsi_thresholds = Config.TECH_THRESHOLDS
        if pd.isna(rsi):
            rsi_str, rsi_desc = "N/A", dim("N/A")
        else:
            rsi_val = float(rsi)
            rsi_str = f"{rsi_val:.2f}"
            if rsi_val >= rsi_thresholds["rsi_overbought"]:
                rsi_desc = red("OVERBOUGHT  (caution)")
            elif rsi_val <= rsi_thresholds["rsi_oversold"]:
                rsi_desc = green("OVERSOLD  (rebound candidate)")
            elif rsi_val >= 50:
                rsi_desc = green("BULLISH  (strong)")
            elif rsi_val >= 40:
                rsi_desc = yellow("NEUTRAL-BULLISH")
            else:
                rsi_desc = red("BEARISH  (weak)")

        # MACD analysis
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
        adx_threshold = rsi_thresholds["adx_trending"]
        if pd.isna(adx):
            adx_str, adx_desc = "N/A", dim("N/A")
        else:
            adx_val = float(adx)
            adx_str = f"{adx_val:.2f}"
            adx_desc = (
                green("STRONG trend")
                if adx_val > adx_threshold
                else yellow("WEAK / sideways")
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
        cci_upper = rsi_thresholds["cci_overbought"]
        cci_lower = rsi_thresholds["cci_oversold"]
        if pd.isna(cci):
            cci_str, cci_desc = "N/A", dim("N/A")
        else:
            cci_val = float(cci)
            cci_str = f"{cci_val:.2f}"
            if cci_val >= cci_upper:
                cci_desc = red("OVERBOUGHT  (uptrend peak)")
            elif cci_val <= cci_lower:
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

        # Output
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

        logger.info("ta_dashboard_viewed", symbol=symbol, score=score)

    except Exception as exc:
        err(f"Error loading '{symbol}': {exc}")
        logger.error("ta_dashboard_failed", symbol=symbol, error=str(exc))

    _pause()


def menu_recompute_ta(hist_dir: str) -> None:
    """Interactive handler to recompute all TA-Lib indicators for Parquet files."""
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
    logger.info("ta_recomputed")
    _pause()


def menu_liquid_etf() -> None:
    """Run the Liquid ETF Screener and display the results."""
    _header("Liquid ETF Screener")
    print("  Fetching ETF list from NSE and calculating sector liquidity...\n")

    df = run_liquid_etf_screener()

    if df.empty:
        warn("Failed to retrieve or parse ETF data.")
        _pause()
        return

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
    """Run the Mark Minervini Trend Template Screener."""
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
    """Run the JdK RS-Ratio Sector Rotation analysis."""
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
    """Run the Correlation Matrix analysis."""
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
    """Run the Nifty Indices Heatmap analysis."""
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
    """Run the Market Mood Index (MMI) Scraper."""
    _header("Market Mood Index (MMI)")
    run_mmi_cli()
    _pause()


def menu_ma_slope(ticker: str | None = None) -> None:
    """Run the Moving Average Slope analyzer."""
    _header("Moving Average Slope Analyzer")

    if not ticker:
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


def menu_squeeze(ticker: str | None = None) -> None:
    """Run the Momentum Squeeze Indicator analysis."""
    _header("Momentum Squeeze Indicator")

    if not ticker:
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
    """Run the Engle-Granger Cointegration Pair Scanner."""
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

    defaults = Config.SYNC_DEFAULTS

    try:
        limit_in = input(
            f"  Symbol scan limit (largest files first) [10-250, default {defaults['default_symbol_limit']}]: "  # noqa: E501
        ).strip()
        symbol_limit = int(limit_in) if limit_in else defaults["default_symbol_limit"]
        if symbol_limit < 2:
            symbol_limit = 2
    except ValueError:
        warn(f"Invalid number. Using default {defaults['default_symbol_limit']}.")
        symbol_limit = defaults["default_symbol_limit"]

    try:
        pval_in = input(
            f"  Max p-value threshold [0.001-0.20, default {defaults['max_pval_threshold']}]: "  # noqa: E501
        ).strip()
        max_pval = float(pval_in) if pval_in else defaults["max_pval_threshold"]
        if max_pval <= 0:
            max_pval = defaults["max_pval_threshold"]
    except ValueError:
        warn(f"Invalid float. Using default {defaults['max_pval_threshold']}.")
        max_pval = defaults["max_pval_threshold"]

    try:
        max_pairs_in = input(
            f"  Max pairs to return [1-100, default {defaults['max_pairs']}]: "
        ).strip()
        max_pairs = int(max_pairs_in) if max_pairs_in else defaults["max_pairs"]
        if max_pairs <= 0:
            max_pairs = defaults["max_pairs"]
    except ValueError:
        warn(f"Invalid number. Using default {defaults['max_pairs']}.")
        max_pairs = defaults["max_pairs"]

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
        logger.error("pair_scanner_failed", error=str(exc))
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
    """Interactive Live NSE Data Hub with cached API client."""
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

        # Use cached NseUtils instance
        print(f"\n  {dim('Connecting to NSE…')}")
        try:
            nse = get_nse_utils()
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

                    limit = Config.DISPLAY_LIMITS["heatmap_preview"]
                    for sym, row in df_pm.head(limit).iterrows():
                        tbl.add_row(
                            str(sym),
                            *[
                                f"{row[c]:,.2f}" if pd.notna(row[c]) else ""
                                for c in display_cols
                            ],
                        )
                    console.print(tbl)
                    print(f"\n  {dim(f'{len(df_pm)} total rows (showing {limit})')}")
            except Exception as exc:
                err(f"Pre-market query failed: {exc}")
                logger.error("premarket_failed", error=str(exc))

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
                    limit = Config.DISPLAY_LIMITS["symbol_preview"]
                    print(
                        "  "
                        + "  ".join(result[:limit])
                        + (" …" if len(result) > limit else "")
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
    """Interactive ML Classifier Backtester menu handler."""
    _header("ML Classifier Backtester")
    symbol = _ask("Enter Stock Symbol (e.g. TCS)", "TCS").strip().upper()

    defaults = Config.SYNC_DEFAULTS

    try:
        n_est_in = input(
            f"  Number of estimators [default {defaults.get('n_estimators', 100)}]: "
        ).strip()
        n_estimators = int(n_est_in) if n_est_in else defaults.get("n_estimators", 100)
    except ValueError:
        warn(f"Invalid number. Using default {defaults.get('n_estimators', 100)}.")
        n_estimators = defaults.get("n_estimators", 100)

    try:
        max_depth_in = input(
            f"  Max depth [default {defaults.get('max_depth', 5)}]: "
        ).strip()
        max_depth = int(max_depth_in) if max_depth_in else defaults.get("max_depth", 5)
    except ValueError:
        warn(f"Invalid number. Using default {defaults.get('max_depth', 5)}.")
        max_depth = defaults.get("max_depth", 5)

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

        print(f"  Scanning for delivery percentage data in {data_dir}/processed...")
        df_delivery = _get_delivery_history(os.path.join(data_dir, "processed"), symbol)
        if df_delivery is not None and not df_delivery.empty:
            ok(f"Aggregated {len(df_delivery)} records of delivery percentage data.")
        else:
            warn("No delivery percentage data found. Defaulting to 0.0.")

        print(
            f"  Training Random Forest (n_estimators={n_estimators}, "
            f"max_depth={max_depth})..."
        )
        from rich.console import Console
        from rich.table import Table

        from src.ml.ml_classifier import MLClassifier
        from src.nse_bhavcopy.backtester import NSEEventBacktester

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

        logger.info("backtest_completed", symbol=symbol, accuracy=acc)

    except Exception as exc:
        err(f"Backtest execution failed: {exc}")
        logger.error("backtest_failed", symbol=symbol, error=str(exc))

    _pause()


def menu_fo_ban(data_dir: str) -> None:
    """Interactive F&O Ban list query."""
    _header("NSE F&O Ban Securities")
    try:
        from src.scrapers.fo_ban import FOBanManager

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
        logger.error("fo_ban_failed", error=str(exc))

    _pause()


def menu_bhavcopy_sync(data_dir: str, hist_dir: str) -> None:
    """Interactive handler for Bhavcopy incremental OHLCV sync."""
    from src.storage.bhavcopy_incremental import BhavcopyIncrementalSync

    _header(
        "Bhavcopy Incremental Sync",
        "Downloads 1 ZIP per missing trading day — far faster than per-symbol API",
    )
    tip("Only updates symbols that already have a local Parquet (incremental path).")
    tip("New symbols with no history still need 'Sync Historical' first.")

    raw_dir = os.path.join(data_dir, "raw")
    defaults = Config.SYNC_DEFAULTS

    days_back_str = _ask(
        "Days back to check for missing data", str(defaults["default_days_back"])
    )
    try:
        days_back = int(days_back_str)
    except ValueError:
        warn(f"Invalid number — using {defaults['default_days_back']}.")
        days_back = defaults["default_days_back"]

    recompute = _confirm("Recompute TA indicators after sync? (recommended)")
    delay = _ask_float("Delay between ZIP downloads (seconds)", defaults["rate_delay"])

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
        timeframe=Config.DEFAULT_TIMEFRAME,
        raw_dir=raw_dir,
        rate_delay=delay,
        recompute_ta=recompute,
    )

    # Use tqdm for progress
    results = {}
    for symbol in tqdm(symbols, desc="Syncing Bhavcopy data"):
        results[symbol] = syncer.sync_one(
            symbol, days_back=days_back, recompute_ta=recompute
        )

    ok_count = sum(v for v in results.values())
    needs_refresh = [s for s, v in results.items() if not v]
    ok(f"Sync complete  {ok_count}/{len(symbols)} symbols updated.")
    if needs_refresh:
        limit = Config.DISPLAY_LIMITS["symbol_preview"]
        warn(
            f"{len(needs_refresh)} need full refresh (run Sync Historical): "
            + ", ".join(needs_refresh[:limit])
            + (" …" if len(needs_refresh) > limit else "")
        )

    logger.info(
        "bhavcopy_sync_completed", succeeded=ok_count, failed=len(needs_refresh)
    )
    _pause()


def menu_fyers_token() -> None:
    """Interactive handler to set the Fyers API access token."""
    from src.nse_bhavcopy.fyers_fetcher import exchange_auth_code

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

    fetcher = get_fyers_fetcher()
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
        logger.info("fyers_token_set")
        tip("This token is valid for the rest of the trading day.")
    else:
        err("Failed to exchange code for token. Check credentials.")

    _pause()


def menu_ml_anomaly(hist_dir: str, data_dir: str) -> None:
    """Interactive ML Anomaly Detection menu handler."""

    _header("ML Data Anomaly Detector")
    print(dim("  (Identifies extreme splits, bad volume, or smart money action)\n"))

    symbol = _ask("Enter NSE Symbol (e.g. RELIANCE, TCS)", "SUZLON").strip()
    if not symbol:
        symbol = "SUZLON"

    args = argparse.Namespace(symbol=symbol, hist_dir=hist_dir, data_dir=data_dir)
    print(_rule())

    try:
        cmd_ml_anomaly(args)
    except Exception as exc:
        err(f"ML Anomaly detection failed: {exc}")
    finally:
        _pause()


# ---------------------------------------------------------------------------
# NEW MENU HANDLERS (24 & 25) — Strategy Inspector + Consensus Leaderboard
# ---------------------------------------------------------------------------


def menu_strategy_inspector(hist_dir: str) -> None:
    """
    Show all 13 strategy signals for a single stock using the ScreenerReporter.
    Reads the latest analyzed CSV from hist_dir.
    """
    _UI.render_header(
        "STRATEGY INSPECTOR",
        "All 13 strategy signals for a single stock · color-coded · with narrative",
    )

    # Find latest analyzed file
    analyzed_files = sorted(
        glob.glob(os.path.join(hist_dir, "top_250_analyzed_*.csv")), reverse=True
    )
    if not analyzed_files:
        err("No analyzed CSV found. Run the Technical Screener (option 4) first.")
        _pause()
        return

    latest = analyzed_files[0]
    df = pd.read_csv(latest)
    df = _REPORTER._ensure_consensus(df)
    print(f"\n  {dim('Dataset:')} {os.path.basename(latest)}  {dim(f'({len(df)} stocks)')}")  # noqa: E501
    print()

    symbol = input(f"  {dim('Enter NSE Symbol')} (e.g. TCS): ").strip().upper()
    if not symbol:
        warn("No symbol entered.")
        _pause()
        return

    _REPORTER.print_strategy_inspector(symbol, df)

    # Narrative
    row_match = df[df["SYMBOL"].astype(str).str.upper() == symbol]
    if not row_match.empty:
        row = row_match.iloc[0]
        narrative = _REPORTER.generate_narrative(row)
        print()
        print(f"  {cyan('▸')} {bold('AI Narrative:')}")  # noqa: E501
        print(f"  {dim(narrative)}")

    _pause()


def menu_consensus_leaderboard(hist_dir: str) -> None:
    """
    Display stocks ranked by CONSENSUS_SCORE from the latest analyzed CSV.
    """
    _UI.render_header(
        "CONSENSUS LEADERBOARD",
        "Top stocks ranked by multi-strategy agreement score",
    )

    analyzed_files = sorted(
        glob.glob(os.path.join(hist_dir, "top_250_analyzed_*.csv")), reverse=True
    )
    if not analyzed_files:
        err("No analyzed CSV found. Run the Technical Screener (option 4) first.")
        _pause()
        return

    latest = analyzed_files[0]
    df = pd.read_csv(latest)
    print(f"\n  {dim('Dataset:')} {os.path.basename(latest)}  {dim(f'({len(df)} stocks)')}")

    top_str = input(f"  {dim('How many top stocks to show')} [20]: ").strip()
    top_n = int(top_str) if top_str.isdigit() else 20

    _REPORTER.print_consensus_leaderboard(df, top_n=top_n)
    _pause()


# ---------------------------------------------------------------------------
# REPL loop
# ---------------------------------------------------------------------------


def interactive_menu(
    data_dir: str = Config.DEFAULT_DATA_DIR,
    hist_dir: str = Config.DEFAULT_HIST_DIR,
) -> None:
    """REPL-style interactive menu loop for the NSE pipeline."""
    processed_dir = os.path.join(data_dir, "processed")

    # Premium header via VisualUI (replaces plain _print_banner)
    _UI.render_header(
        "NSE DATA PIPELINE",
        f"Equity Master · Historical Sync · 13-Strategy Screener · ML Analysis  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    )

    # Action dispatch mapping
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
        "23": lambda: menu_ml_anomaly(hist_dir, data_dir),
        "24": lambda: menu_strategy_inspector(hist_dir),
        "25": lambda: menu_consensus_leaderboard(hist_dir),
        "26": lambda: menu_data_quality(hist_dir, data_dir),
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
            logger.info("menu_exit")
            break

        handler = _DISPATCH.get(choice)
        if handler:
            handler()
        else:
            warn(f"'{choice}' is not a valid option — enter 0-26.")
