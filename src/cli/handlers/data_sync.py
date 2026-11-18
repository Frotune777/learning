"""
Data Sync, Lake Management, Bhavcopy, and Data Quality menu handlers.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import structlog
from tqdm import tqdm

from src.cli.formatters import (
    _ask,
    _ask_float,
    _confirm,
    _header,
    _pause,
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
    yellow,
)
from src.cli.renderers.system_views import render_dq_audit_panel
from src.cli.visual import VisualUI
from src.core.config import Config, UserPrefs
from src.core.symbol_utils import find_latest_master, load_symbols
from src.core.utils import get_fyers_fetcher
from src.storage.downloader import BhavcopyDownloader
from src.storage.equity_master import NSEEquityMasterBuilder
from src.storage.historical_sync import HistoricalSync
from src.storage.sync_registry import SyncRegistry

logger = structlog.get_logger("nse_pipeline.data_sync")
_UI = VisualUI()


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


def menu_build_master(data_dir: str) -> None:
    """Interactive handler for building the equity master table."""
    _header("Build Equity Master", "Downloads sec_list.csv + all index constituents")
    print(tip("This replaces any previously cached master Parquet."))

    if not _confirm("Start build?"):
        print(warn("Cancelled."))
        return

    delay = _ask_float("API delay between index calls (seconds)", 1.0)

    builder = NSEEquityMasterBuilder(
        output_dir=data_dir,
        cache_dir=os.path.join(data_dir, "cache"),
    )
    try:
        path = builder.build_and_save(delay=delay)
        print(ok(f"Master saved  →  {path}"))
        logger.info("master_built", path=path, delay=delay)
    except RuntimeError as exc:
        print(err(f"Build failed: {exc}"))
        logger.error("master_build_failed", error=str(exc))

    _pause()


def _pre_flight_check() -> str:
    """Execute connection and auth pre-flight checks before syncing history."""
    import time
    import requests
    from src.core.data_sources import get_data_source_manager
    from src.nse_bhavcopy.fyers_fetcher import FyersAuthError, exchange_auth_code

    print(f"\n  {bold('[PRE-FLIGHT CHECK]')}")

    # 1. Ping yfinance
    yf_ok = False
    yf_ms = 0
    t0 = time.perf_counter()
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/RELIANCE.NS?interval=1d&range=1d",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=3.0,
        )
        if r.status_code == 200:
            yf_ok = True
            yf_ms = int((time.perf_counter() - t0) * 1000)
    except Exception:
        pass

    if yf_ok:
        print(f"  {green('✓')} {bold('yfinance:')}  {green(f'OK (Latency {yf_ms}ms)')}")
    else:
        print(f"  {red('✗')} {bold('yfinance:')}  {red('FAILED (Unreachable)')}")

    # 2. Check Fyers
    fyers_status = "OK"
    fyers_msg = ""
    fyers = get_fyers_fetcher()
    if not fyers.access_token:
        fyers_status = "NO_TOKEN"
        fyers_msg = "Token Expired / Missing"
    else:
        t0 = time.perf_counter()
        try:
            q = fyers.get_quotes(["NSE:NIFTY50-INDEX"])
            if q:
                fyers_ms = int((time.perf_counter() - t0) * 1000)
                fyers_msg = f"OK (Latency {fyers_ms}ms)"
            else:
                fyers_status = "EMPTY"
                fyers_msg = "Zero quotes returned"
        except FyersAuthError:
            fyers_status = "AUTH_FAIL"
            fyers_msg = "Token Rejected (401)"
        except Exception as e:
            fyers_status = "ERROR"
            fyers_msg = f"Failed ({e})"

    if fyers_status == "OK":
        print(f"  {green('✓')} {bold('Fyers API:')}  {green(fyers_msg)}")
    elif fyers_status in ("NO_TOKEN", "AUTH_FAIL"):
        print(f"  {yellow('!')} {bold('Fyers API:')}  {yellow(fyers_msg)}")
        print(f"    {dim('To authenticate Fyers:')}")
        try:
            print(f"    1. Visit: {cyan(fyers.login_url())}")
            print(f"    2. Log in, copy the redirect URL from your browser address bar.")
            auth_code_input = input(f"    3. Paste full redirect URL or auth_code (or press Enter to skip): ").strip()
            if auth_code_input:
                token = exchange_auth_code(auth_code_input)
                if token:
                    print(f"    {green('✓ Token generated and saved successfully!')}")
                    fyers_status = "OK"
                else:
                    print(f"    {red('✗ Failed to generate token from provided code/URL.')}")
        except Exception as auth_err:
            print(f"    {dim('Tip:')} Configure Fyers credentials using option [14] (Data Sources). ({auth_err})")
    else:
        print(f"  {red('✗')} {bold('Fyers API:')}  {red(fyers_msg)}")

    # 3. Decision Prompt
    if not yf_ok and fyers_status != "OK":
        print(f"\n  {red('CRITICAL: Both primary (yfinance) and secondary (Fyers) sources are unavailable!')}")
        c = input(f"  Continue anyway using third-tier fallback (nse_charts)? [y/N]: ").strip().lower()
        if c not in ("y", "yes"):
            print(f"  {dim('Historical sync aborted.')}")
            return "abort"
    elif not yf_ok and fyers_status == "OK":
        print(f"\n  {yellow('Notice: yfinance is down. Sync will use Tier 2 (Fyers API) as primary.')}")
    elif yf_ok and fyers_status != "OK":
        print(f"\n  {dim('Notice: Fyers is unauthenticated. Sync will use Tier 1 (yfinance) bulk downloads.')}")

    return "continue"


def menu_sync_history(
    data_dir: str,
    hist_dir: str,
    cap_filter: str | None = None,
    index_filter: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    """Interactive handler for syncing historical Parquet data."""
    if _pre_flight_check() == "abort":
        return

    master_path = _find_latest_master(data_dir)
    symbols = _load_symbols(
        master_path, cap_filter=cap_filter, index_filter=index_filter, limit=limit
    )

    if not symbols:
        print(err("No symbols found. Run 'Build Master' first."))
        _pause()
        return

    print(f"\n  {dim('Symbols loaded:')}  {bold(str(len(symbols)))}", end="")
    if cap_filter:
        print(f"  {dim('cap=')} {cap_filter}", end="")
    if index_filter:
        print(f"  {dim('index=')} {index_filter}", end="")
    print()

    from src.storage.sync_ledger import SyncLedger
    ledger = SyncLedger()
    stale = ledger.get_stale_symbols(symbols)

    if not stale:
        summary = ledger.get_summary()
        latest = summary.get("latest_date") or "today"
        print(f"\n  {ok(f'All {len(symbols)} symbols are already current through {bold(latest)}.')}")
        print(f"  {dim('Zero network requests needed. Local Parquet data lake is 100% up to date.')}")
        if not _confirm("Force re-download all symbols anyway?", default=False):
            _pause()
            return
    else:
        print(f"  ⚡ {cyan(str(len(stale)))} of {len(symbols)} symbols need updates ({len(symbols) - len(stale)} already current).")

    tf = _ask("Timeframe  (1d / 1w / 1mo)", Config.DEFAULT_TIMEFRAME)

    start = _ask("Start date (YYYY-MM-DD)", Config.DEFAULT_START_DATE)
    delay = _ask_float("Rate delay between requests (seconds)", 0.5)

    if dry_run:
        print(ok(f"Dry run: Would sync {len(symbols)} symbols with {tf} timeframe"))
        _pause()
        return

    hs = HistoricalSync(
        data_dir=hist_dir, timeframe=tf, start_date=start, rate_delay=delay
    )

    with tqdm(total=len(symbols), desc="Syncing symbols") as pbar:
        results = hs.sync_batch(symbols, pbar=pbar)

    ok_count = sum(v for v in results.values())
    failed = [s for s, v in results.items() if not v]

    print(ok(f"Sync complete  {ok_count}/{len(symbols)} succeeded"))
    if failed:
        limit_count = Config.DISPLAY_LIMITS["symbol_preview"]
        print(warn(
            f"{len(failed)} failed: {', '.join(failed[:limit_count])}"
            + (" …" if len(failed) > limit_count else "")
        ))

    logger.info("sync_completed", succeeded=ok_count, failed=len(failed))
    _pause()


def menu_sync_filtered(data_dir: str, hist_dir: str) -> None:
    """Interactive handler for syncing with user-specified filters."""
    _header("Sync Historical Data — Filtered")

    prefs = UserPrefs()

    print(f"  {dim('Market cap:')}  Large · Mid · Small · Other · {dim('Enter = All')}")
    cap = input("  Cap filter: ").strip() or None
    if cap and cap not in ("Large", "Mid", "Small", "Other"):
        print(warn(f"Unknown cap '{cap}' — no cap filter applied."))
        cap = None

    print(
        f"  {dim('Index examples:')}  is_nifty_50 · is_nifty_500 · "
        f"{dim('Enter = None')}"
    )
    idx = input("  Index filter: ").strip() or None

    limit_str = input("  Max symbols (Enter = all): ").strip()
    limit = int(limit_str) if limit_str else None

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


def menu_status(hist_dir: str, data_dir: str) -> None:
    """Show sync status for all symbols in the master table."""
    _header("Parquet Sync Status")

    master_path = _find_latest_master(data_dir)
    if master_path is None:
        print(err("No master table found."))
        print(tip("Run option [1] to build the master first."))
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
        print(warn("No registry found."))
        print(tip("Run a sync (option [2] or [3]) to create one."))
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
    _header(
        "Data Quality Gate & System Audit",
        "Scan local Parquet files for gaps, stale feeds, NaN indicators, and auto-heal",
    )

    master_path = _find_latest_master(data_dir)
    if not master_path:
        print(err("No Equity Master found. Please run Option [1] first."))
        _pause()
        return

    builder = NSEEquityMasterBuilder(output_dir=data_dir)
    symbols = builder.get_symbols(master_path)
    if not symbols:
        print(err("No symbols loaded from Equity Master."))
        _pause()
        return

    print(f"\n  {dim('Scanning')} {bold(str(len(symbols)))} {dim('symbols in master Equity list...')}")

    hs = HistoricalSync(data_dir=hist_dir)
    status_df = hs.status(symbols)

    total_symbols = len(status_df)
    missing = status_df[status_df["rows"] == 0]
    low_coverage = status_df[(status_df["rows"] > 0) & (status_df["coverage_pct"] < 95.0)]
    stale_data = status_df[(status_df["rows"] > 0) & (status_df["days_stale"] > 3)]
    nan_indicators = status_df[(status_df["rows"] > 0) & (status_df["has_indicator_nan"] == True)]
    healthy = status_df[
        (status_df["rows"] > 0)
        & (status_df["coverage_pct"] >= 95.0)
        & (status_df["days_stale"] <= 3)
        & (status_df["has_indicator_nan"] == False)
    ]

    failed_symbols = hs._load_failed_symbols()

    # 1H Intraday lake count
    h1_dir = os.path.join(hist_dir, "1h")
    h1_count = len([f for f in os.listdir(h1_dir) if f.endswith(".parquet")]) if os.path.isdir(h1_dir) else 0

    render_dq_audit_panel(
        total_symbols=total_symbols,
        healthy_count=len(healthy),
        low_coverage_count=len(low_coverage),
        stale_count=len(stale_data),
        nan_indicators_count=len(nan_indicators),
        missing_count=len(missing),
        failed_blacklist_count=len(failed_symbols),
    )
    print(f"  {bold('Intraday 1H Lake:')} {cyan(str(h1_count))} symbols available in data/historical/1h/\n")

    if not missing.empty:
        print(f"\n  {red('● Missing Parquets')} ({len(missing)}):")
        preview = missing["symbol"].head(10).tolist()
        print(f"    {dim(', '.join(preview))}{' ...' if len(missing) > 10 else ''}")

    if not stale_data.empty:
        print(f"\n  {yellow('● Stale Data Symbols')} ({len(stale_data)}):")
        preview = [f"{r['symbol']} ({r['days_stale']}d stale)" for _, r in stale_data.head(5).iterrows()]
        print(f"    {dim(', '.join(preview))}{' ...' if len(stale_data) > 5 else ''}")

    if not nan_indicators.empty:
        print(f"\n  {yellow('● Symbols with NaN Indicator Tail')} ({len(nan_indicators)}):")
        preview = nan_indicators["symbol"].head(8).tolist()
        print(f"    {dim(', '.join(preview))}{' ...' if len(nan_indicators) > 8 else ''}")

    if not low_coverage.empty:
        print(f"\n  {yellow('● Low Coverage Equities')} ({len(low_coverage)}):")
        preview = [f"{r['symbol']} ({r['coverage_pct']:.1f}%)" for _, r in low_coverage.head(5).iterrows()]
        print(f"    {dim(', '.join(preview))}{' ...' if len(low_coverage) > 5 else ''}")

    to_heal = sorted(
        list(
            set(missing["symbol"].tolist())
            | set(low_coverage["symbol"].tolist())
            | set(stale_data["symbol"].tolist())
        )
    )

    print(f"\n  {dim('Interactive Healer Menu:')}")
    print(f"    {bold('H')}. Auto-Heal Data Gaps & Stale Data (Sync {len(to_heal)} symbols)")
    print(f"    {bold('T')}. Quick-Repair All TA Indicators ({len(nan_indicators)} symbols with NaNs)")
    print(f"    {bold('F')}. Clear Failed Sync Blacklist ({len(failed_symbols)} symbols)")
    print(f"    {bold('R')}. Run Smart Data Repairer (Deep repair for gaps, duplicates, ordering)")
    print(f"    {bold('Q')}. Quit to Main Menu")

    choice = input(f"\n  {dim('>')} ").strip().upper()

    if choice == "H":
        if not to_heal:
            print(ok("No missing or stale symbols need syncing!"))
            _pause()
            return
        if not _confirm(f"Start targeted sync/refresh of {len(to_heal)} symbols?"):
            print(warn("Cancelled."))
            _pause()
            return

        print(ok("Initializing Auto-Healer pipeline..."))
        hs.sync(to_heal, resume=False)
        print(ok("Auto-healing process completed!"))
    elif choice == "T":
        if nan_indicators.empty:
            print(ok("All available Parquets already have complete, non-NaN indicators!"))
            _pause()
            return
        print(ok(f"Recalculating technical indicators for {len(nan_indicators)} symbols..."))
        fixed_count = 0
        from src.nse_bhavcopy.ta_indicators import add_ta_indicators
        for sym in nan_indicators["symbol"].tolist():
            try:
                p = os.path.join(hist_dir, "1d", f"{sym}.parquet")
                if os.path.exists(p):
                    df_sym = pd.read_parquet(p)
                    base_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df_sym.columns]
                    if len(base_cols) >= 4 and len(df_sym) >= 15:
                        df_fixed = add_ta_indicators(df_sym[base_cols])
                        df_fixed.to_parquet(p)
                        fixed_count += 1
            except Exception as e:
                logger.warning("Failed TA repair for %s: %s", sym, e)
        print(ok(f"Quick-Repaired {fixed_count} symbols! All TA indicators are now non-NaN."))
    elif choice == "R":
        print(ok("Initializing Smart Data Repairer..."))
        from src.analysis.SmartDataRepairer import SmartDataRepairer
        repairer = SmartDataRepairer()
        repairer.repair_all(hist_dir, timeframe="1d")
        print(ok("Smart Data Repairer completed!"))
    elif choice == "F":
        path = os.path.join(hist_dir, "failed_symbols.csv")
        if os.path.exists(path):
            try:
                os.remove(path)
                print(ok("Successfully cleared failed_symbols.csv blacklist!"))
            except Exception as e:
                print(err(f"Failed to clear blacklist: {e}"))
        else:
            print(warn("No blacklist file found."))
    else:
        print(warn("Quit healing."))

    _pause()


def menu_recompute_ta(hist_dir: str) -> None:
    """Batch recompute TA indicators on all Parquet files."""
    _header("Recompute TA Indicators", "Calculates RSI, MACD, Bollinger, EMAs for all files")
    files = [f for f in os.listdir(hist_dir) if f.endswith(".parquet")]
    if not files and os.path.isdir(os.path.join(hist_dir, "1d")):
        files = [f for f in os.listdir(os.path.join(hist_dir, "1d")) if f.endswith(".parquet")]

    if not files:
        print(err("No Parquet files found in historical data directory."))
        _pause()
        return

    if not _confirm(f"Recompute TA indicators for {len(files)} files?"):
        print(warn("Cancelled."))
        _pause()
        return

    hs = HistoricalSync(data_dir=hist_dir)
    hs.recompute_all_indicators()
    print(ok("Indicator recomputation complete."))
    _pause()


def menu_bhavcopy_sync(data_dir: str, hist_dir: str) -> None:
    """Interactive handler for Bhavcopy incremental OHLCV sync."""
    from src.storage.bhavcopy_incremental import BhavcopyIncrementalSync

    _header(
        "Bhavcopy Incremental Sync",
        "Downloads 1 ZIP per missing trading day — far faster than per-symbol API",
    )
    print(tip("Only updates symbols that already have a local Parquet (incremental path)."))
    print(tip("New symbols with no history still need 'Sync Historical' first."))

    raw_dir = os.path.join(data_dir, "raw")
    defaults = Config.SYNC_DEFAULTS

    days_back_str = _ask("Days back to check for missing data", str(defaults["default_days_back"]))
    try:
        days_back = int(days_back_str)
    except ValueError:
        print(warn(f"Invalid number — using {defaults['default_days_back']}."))
        days_back = defaults["default_days_back"]

    delay = _ask_float("Delay between ZIP downloads (seconds)", defaults["rate_delay"])

    zip_path = os.path.join(
        raw_dir,
        sorted([f for f in os.listdir(raw_dir) if f.endswith(".zip")])[-1]
        if os.path.isdir(raw_dir) and any(f.endswith(".zip") for f in os.listdir(raw_dir))
        else "",
    )
    if not zip_path or not os.path.exists(zip_path):
        print(err("No Bhavcopy ZIP found in data/raw. Run 'Build Master' first."))
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
        print(err("Could not extract symbols from Bhavcopy ZIP."))
        _pause()
        return

    print(f"\n  {dim('Symbols loaded:')}  {bold(str(len(symbols)))}")
    if not _confirm(f"Start Bhavcopy sync for {len(symbols)} symbols?"):
        print(warn("Cancelled."))
        _pause()
        return

    syncer = BhavcopyIncrementalSync(
        data_dir=hist_dir,
        timeframe=Config.DEFAULT_TIMEFRAME,
        raw_dir=raw_dir,
        rate_delay=delay,
    )

    results = syncer.run(symbols, days_back=days_back)
    ok_count = sum(v for v in results.values())
    needs_refresh = [s for s, v in results.items() if not v]
    print(ok(f"Sync complete  {ok_count}/{len(symbols)} symbols updated."))
    if needs_refresh:
        limit = Config.DISPLAY_LIMITS["symbol_preview"]
        print(warn(
            f"{len(needs_refresh)} need full refresh (run Sync Historical): "
            + ", ".join(needs_refresh[:limit])
            + (" …" if len(needs_refresh) > limit else "")
        ))

    logger.info("bhavcopy_sync_completed", succeeded=ok_count, failed=len(needs_refresh))
    _pause()


def menu_fyers_token() -> None:
    """Interactive handler to configure data sources and Fyers broker session."""
    from src.core.data_sources import DATA_SOURCES, DataSourceManager
    from src.nse_bhavcopy.fyers_fetcher import exchange_auth_code

    _header(
        "Data Sources & Broker Gateway",
        "Select active data providers for Historical & Live data, or configure Fyers broker token.",
    )

    dsm = DataSourceManager()
    summary = dsm.get_status_summary()

    fyers_fetcher = get_fyers_fetcher()
    fyers_auth = summary["fyers"]["authenticated"]
    token_expiry = summary["fyers"]["token_expiry"]

    print(f"  {bold('Active Historical Source:')} {cyan(DATA_SOURCES[dsm.active_historical_source].name)}")
    print(f"  {bold('Active Live Source:')}       {cyan(DATA_SOURCES[dsm.active_live_source].name)}")
    print(f"  {bold('Fyers Session:')}            {green('AUTHENTICATED') if fyers_auth else red('NOT AUTHENTICATED')}")
    if token_expiry:
        print(f"  {dim('Token Expiry:')}             {dim(token_expiry)}")
    print()

    print("  [1] Switch Historical Data Provider")
    print("  [2] Switch Live Data Provider")
    print("  [3] Set Fyers Access Token (Manual entry)")
    print("  [4] Interactive Fyers Login (Generate new token)")
    print("  [5] Validate & Test Active Connections")
    print("  [0] Return to Main Menu\n")

    choice = input(f"  {dim('Select option')} [0-5]: ").strip()
    if choice == "1":
        print("\n  Available Historical Providers:")
        providers = list(DATA_SOURCES.items())
        for idx, (k, v) in enumerate(providers, 1):
            mark = "●" if k == dsm.active_historical_source else "○"
            print(f"   {idx}. {mark} {v.name} ({v.type})")
        pick = input(f"\n  Choose historical provider [1-{len(providers)}]: ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(providers):
            chosen_key = providers[int(pick) - 1][0]
            dsm.active_historical_source = chosen_key
            print(ok(f"Historical provider set to: {bold(DATA_SOURCES[chosen_key].name)}"))
    elif choice == "2":
        live_keys = [k for k, v in DATA_SOURCES.items() if v.supports_live]
        for idx, k in enumerate(live_keys, 1):
            mark = "●" if k == dsm.active_live_source else "○"
            print(f"   {idx}. {mark} {DATA_SOURCES[k].name}")
        pick = input(f"\n  Choose live provider [1-{len(live_keys)}]: ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(live_keys):
            dsm.active_live_source = live_keys[int(pick) - 1]
            print(ok(f"Live market data source set to: {DATA_SOURCES[dsm.active_live_source].name}"))
    elif choice == "3":
        tok = input("  Enter Fyers Access Token: ").strip()
        if tok:
            fyers_fetcher.save_token(tok)
            print(ok("Fyers access token updated successfully."))
    elif choice == "4":
        print(f"\n  {dim('Visit this login URL in your browser:')}")
        try:
            print(f"  {cyan(fyers_fetcher.login_url())}\n")
        except Exception as auth_err:
            print(f"  {warn(f'Could not generate login URL: {auth_err}')}\n")
        auth_in = input("  Paste full redirect URL or auth_code: ").strip()
        if auth_in:
            token = exchange_auth_code(auth_in)
            if token:
                print(ok("Fyers token generated and saved!"))
            else:
                print(err("Failed to exchange auth code for token."))
    elif choice == "5":
        diag = dsm.diagnose_all()
        for k, v in diag.items():
            st_color = green if v["status"] == "OK" else red
            print(f"  {k:<16} {st_color(v['status']):<8} {dim(str(v.get('details', '')))}")

    _pause()


def menu_query_engine(hist_dir: str, data_dir: str) -> None:
    """Interactive SQL prompt for querying local Parquet data lake with DuckDB."""
    from src.nse_bhavcopy.query_engine import DuckDBQueryEngine

    hist_1d = os.path.join(hist_dir, "1d") if os.path.isdir(os.path.join(hist_dir, "1d")) else hist_dir
    engine = DuckDBQueryEngine(hist_1d)
    print(f"\n{cyan('=== DUCKDB SQL ENGINE ===')}")
    print("Type your SQL queries. Available views: 'market_data' and 'prices'.")
    print("Example: SELECT symbol, close, volume FROM market_data WHERE close > 500 LIMIT 5;")
    print("Type 'exit' or 'quit' to return to menu.\n")
    while True:
        try:
            query = input(f"{cyan('SQL> ')}").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if query.lower() in ("exit", "quit"):
            break
        if not query:
            continue
        try:
            df = engine.query(query)
            if df is not None and not df.empty:
                print(df.to_string())
            else:
                print("No results or empty DataFrame returned.")
        except Exception as e:
            print(err(f"Query error: {e}"))
    _pause()


def menu_toggle_data_mode() -> None:
    """Toggle between offline (stored data lake) and live market mode."""
    import src.core.config as config

    prefs = UserPrefs()
    current = getattr(config, "DATA_MODE", "offline")
    new_mode = "live" if current == "offline" else "offline"
    config.DATA_MODE = new_mode
    config.OFFLINE = (new_mode == "offline")
    config.Config.OFFLINE = (new_mode == "offline")
    prefs.set_last("data_mode", new_mode)
    print(f"\n  {ok(f'Data Mode switched to: {bold(new_mode.upper())}')}")
    if new_mode == "offline":
        print(f"  {dim('All screeners and strategies execute against local Parquet data lake.')}")
    else:
        print(f"  {yellow('Live mode active: Real-time queries and network calls are enabled.')}")
    _pause()


def menu_data_source_settings() -> None:
    """Interactive settings to configure download sources and execution mode."""
    from src.core.data_sources import DATA_SOURCES, DataSourceManager
    import src.core.config as config

    dsm = DataSourceManager()
    summary = dsm.get_status_summary()

    _UI.render_header(
        "DATA SOURCE & DOWNLOAD SETTINGS",
        "Select primary download provider for history sync, toggle data mode, and manage broker tokens.",
    )

    current_src_key = dsm.active_historical_source
    current_src_name = DATA_SOURCES.get(current_src_key, DATA_SOURCES["tiered"]).name
    print(f"  {bold('Current Data Mode:')}          {yellow('📁 Stored Data (Offline)') if config.OFFLINE else green('🔴 Live Data')}")
    print(f"  {bold('Active Download Provider:')}  {cyan(current_src_name)}")
    print(f"  {bold('Active Live Provider:')}      {cyan(DATA_SOURCES.get(dsm.active_live_source, DATA_SOURCES['yfinance']).name)}")
    print(f"  {bold('Fyers Broker Session:')}      {green('AUTHENTICATED') if summary['fyers']['authenticated'] else red('NO ACTIVE TOKEN')}\n")

    print("  [1] Choose Download Source for Historical Data Sync")
    print("      (Auto-Cascade / Yahoo Finance / jugaad-data NSE / Fyers / NSE Charts)")
    print("  [2] Switch Active Live Market Data Provider")
    print("  [3] Toggle Data Mode (Offline Parquet vs Live Mode)")
    print("  [4] Configure Fyers API Broker Token")
    print("  [5] Sync 1H Intraday Data for Train 920/130 & Turnover")
    print("  [0] Return to Main Menu\n")

    choice = input(f"  {dim('Select option')} [0-5]: ").strip()
    if choice == "1":
        print("\n  Available Download Providers for Historical Data:")
        providers = [
            ("tiered", "Auto-Cascade (1st YFinance -> 2nd Fyers -> 3rd jugaad-data NSE) [Recommended]"),
            ("yfinance", "Yahoo Finance (yfinance) [Fast bulk downloads, OHLCV]"),
            ("bhavcopy", "Official NSE Bhavcopy (via jugaad-data) [With Delivery % & Turnover]"),
            ("fyers", "Fyers API v3 (Broker Direct) [Requires Fyers token]"),
            ("nse_charts", "NSE Website Chart API [Direct public scraper]"),
        ]
        for idx, (k, label) in enumerate(providers, 1):
            mark = "●" if k == current_src_key else "○"
            print(f"   {idx}. {mark} {label}")
        pick = input(f"\n  Choose download provider [1-{len(providers)}]: ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(providers):
            chosen_key = providers[int(pick) - 1][0]
            dsm.active_historical_source = chosen_key
            print(ok(f"Primary download provider set to: {bold(DATA_SOURCES.get(chosen_key, DATA_SOURCES['tiered']).name)}"))
    elif choice == "2":
        live_keys = [k for k, v in DATA_SOURCES.items() if v.supports_live]
        for idx, k in enumerate(live_keys, 1):
            mark = "●" if k == dsm.active_live_source else "○"
            print(f"   {idx}. {mark} {DATA_SOURCES[k].name}")
        pick = input(f"\n  Choose live provider [1-{len(live_keys)}]: ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(live_keys):
            dsm.active_live_source = live_keys[int(pick) - 1]
            print(ok(f"Live market data source set to: {DATA_SOURCES[dsm.active_live_source].name}"))
    elif choice == "3":
        menu_toggle_data_mode()
        return
    elif choice == "4":
        menu_fyers_token()
        return
    elif choice == "5":
        hist_base = dsm.prefs.get_last("hist_dir", Config.DEFAULT_HIST_DIR)
        data_base = dsm.prefs.get_last("data_dir", Config.DEFAULT_DATA_DIR)
        menu_sync_intraday_1h(data_base, hist_base)
        return
    _pause()


def menu_sync_intraday_1h(data_dir: str, hist_dir: str) -> None:
    """Synchronize 1H intraday candles for liquid / watchlisted stocks (Train No. 920/130)."""
    _header("Sync 1H Intraday Data", "Ingest 60-minute candles for Train No. 920/130 & Turnover")
    master_path = _find_latest_master(data_dir)
    default_symbols = _load_symbols(master_path, index_filter="is_nifty_500", limit=500)
    if not default_symbols:
        default_symbols = _load_symbols(master_path, limit=200)

    print(f"  Target Universe: NIFTY 500 / Liquid Equities ({len(default_symbols)} candidates)")
    count_in = input(f"  Enter symbol count to sync [default {min(len(default_symbols), 200)}]: ").strip()
    limit = int(count_in) if count_in.isdigit() else min(len(default_symbols), 200)
    targets = default_symbols[:limit]

    period = input("  Lookback period [default: 60d, max: 730d]: ").strip() or "60d"

    if not _confirm(f"Start 1H intraday sync for {len(targets)} symbols (period={period})?"):
        print(warn("Cancelled."))
        _pause()
        return

    hs = HistoricalSync(data_dir=hist_dir, timeframe="1h")
    with tqdm(total=len(targets), desc="Syncing 1H Bars") as pbar:
        results = hs.sync_intraday_1h(targets, period=period, pbar=pbar)

    ok_count = sum(1 for v in results.values() if v)
    print(ok(f"1H Sync Complete: {ok_count}/{len(targets)} symbols updated in data/historical/1h/"))
    _pause()
