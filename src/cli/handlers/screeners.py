"""
Technical Screeners and Quantitative Scanner menu handlers.
"""

from __future__ import annotations

import glob
import os
from datetime import datetime

import pandas as pd
import structlog

from src.cli.formatters import (
    _confirm,
    _display_csv,
    _header,
    _pause,
    _rule,
    _subheader,
    bold,
    cyan,
    dim,
    err,
    ok,
    warn,
)
from src.cli.handlers.data_sync import menu_sync_filtered
from src.cli.renderers.screener_views import render_strategy_results_table
from src.cli.visual import VisualUI
from src.core.config import SCREENER_STRATEGIES, Config
from src.core.symbol_utils import get_delivery_history_from_bhavcopy
from src.nse_bhavcopy.ma_slope import analyze_stock_ma_slope
from src.scanners.etf_screener import run_liquid_etf_screener
from src.scanners.minervini_screener import run_minervini_cli
from src.scanners.momentum_squeeze import run_squeeze_cli
from src.scanners.unified_scanner import compile_signals_to_dataframe, run_unified_scanner
from src.screener import StockScreener

logger = structlog.get_logger("nse_pipeline.screeners")
_UI = VisualUI()


def _get_delivery_history(processed_dir: str, symbol: str) -> pd.DataFrame | None:
    """Thin wrapper around src.core.symbol_utils.get_delivery_history_from_bhavcopy."""
    return get_delivery_history_from_bhavcopy(processed_dir, symbol)


def _display_strategy_results(csv_path: str, name: str, description: str) -> None:
    """Display a single strategy's results."""
    if os.path.exists(csv_path):
        _display_csv(csv_path, name, description)
    else:
        print(warn(f"No results generated for {name} today."))


def _screener_results_menu(hist_dir: str, date_str: str) -> None:
    """Sub-menu for browsing screener output files."""
    final_csv = os.path.join(hist_dir, f"final_list_{date_str}.csv")
    swing_csv = os.path.join(hist_dir, f"swing_target_{date_str}.csv")
    if not os.path.exists(swing_csv):
        swing_csv = os.path.join(hist_dir, f"swing_list_{date_str}.csv")
    super_csv = os.path.join(hist_dir, f"super_list_{date_str}.csv")

    while True:
        print()
        print(_rule("─"))
        print(f"  {bold('Screener Results')}  {dim(f'({date_str})')}")
        print(_rule("─"))
        print(f"   {cyan('1')}  Final List   {dim('Bull Run + CAR Buy/Average Out — pure breakout candidates')}")
        print(f"   {cyan('2')}  Swing List   {dim('Start GTT signals — 20D low bounce setups with GTT entry')}")
        print(f"   {cyan('3')}  Super List   {dim('Combined Holy Grail — Bull + CAR + GTT bounce at once')}")

        for idx, strategy in enumerate(SCREENER_STRATEGIES, start=4):
            csv_path = os.path.join(hist_dir, f"{strategy['file_prefix']}_{date_str}.csv")
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
            _display_csv(final_csv, "Final Target List", "Intraday & short-term breakout candidates with strong momentum.")
        elif choice == "2":
            _display_csv(swing_csv, "Swing Trading List", "Positional setups nearing GTT trigger levels for mid-term holding.")
        elif choice == "3":
            _display_csv(super_csv, "Super Output (The Holy Grail)", "Highest conviction setups passing multiple extreme filters.")
        elif choice == "99":
            dfs = []
            for strategy in SCREENER_STRATEGIES:
                csv_path = os.path.join(hist_dir, f"{strategy['file_prefix']}_{date_str}.csv")
                if os.path.exists(csv_path):
                    df_strat = pd.read_csv(csv_path)
                    if not df_strat.empty:
                        df_strat.insert(1, "Strategy", strategy["name"])
                        dfs.append(df_strat)
            if dfs:
                combined_df = pd.concat(dfs, ignore_index=True)
                out_path = os.path.join(hist_dir, f"all_strategies_{date_str}.csv")
                combined_df.to_csv(out_path, index=False)
                _display_csv(out_path, "All Strategies Combined", "All matching signals across individual quantitative models.")
            else:
                print(warn("No individual strategy results found to combine."))
        elif choice.isdigit():
            idx = int(choice) - 4
            if 0 <= idx < len(SCREENER_STRATEGIES):
                strategy = SCREENER_STRATEGIES[idx]
                csv_path = os.path.join(hist_dir, f"{strategy['file_prefix']}_{date_str}.csv")
                _display_strategy_results(csv_path, strategy["name"], strategy["description"])
            else:
                print(warn("Invalid selection."))
        else:
            print(warn("Invalid selection."))


def menu_screen(data_dir: str, hist_dir: str, processed_dir: str) -> None:
    """Interactive handler for running the technical screener."""
    _UI.render_header(
        "TECHNICAL SCREENER",
        "Scans synced Parquet data for technical setups · Bull Run + CAR + Swing + 13 Strategies",
    )

    if _confirm("Fetch latest history + update TA indicators first?"):
        menu_sync_filtered(data_dir, hist_dir)
        _subheader("Continuing with Screener")

    csv_pattern = os.path.join(processed_dir, "top_*.csv")
    csv_files = [f for f in sorted(glob.glob(csv_pattern), reverse=True) if "analyzed" not in os.path.basename(f)]

    now = datetime.now()
    today_str = now.strftime("%Y%m%d")
    today_top_csv = os.path.join(processed_dir, f"top_250_{today_str}.csv")

    if os.path.exists(today_top_csv):
        top_csv = today_top_csv
    elif csv_files and (now - datetime.fromtimestamp(os.path.getmtime(csv_files[0]))).days <= 3:
        top_csv = csv_files[0]
    else:
        print(f"\n  {cyan('Building fresh Top 250 universe from offline Parquet data...')}")
        try:
            import pyarrow.parquet as pq
            from pathlib import Path

            lake_dir = Path(hist_dir) / "1d" if os.path.isdir(os.path.join(hist_dir, "1d")) else Path(hist_dir)
            lake_files = list(lake_dir.glob("*.parquet"))
            records = []
            for f in lake_files:
                try:
                    t = pq.read_table(f, columns=["Close", "Volume"])
                    if len(t) > 0:
                        c = t["Close"][-1].as_py() or 0.0
                        v = t["Volume"][-1].as_py() or 0.0
                        records.append({"SYMBOL": f.stem, "TURNOVER": float(c * v), "CLOSE": float(c)})
                except Exception:
                    pass
            if records:
                df_top = pd.DataFrame(records).sort_values(by="TURNOVER", ascending=False).head(250)
                os.makedirs(processed_dir, exist_ok=True)
                df_top.to_csv(today_top_csv, index=False)
                top_csv = today_top_csv
            elif csv_files:
                top_csv = csv_files[0]
            else:
                print(err(f"No processed Bhavcopy CSV or Parquet data found in '{processed_dir}'."))
                _pause()
                return
        except Exception as exc:
            print(err(f"Failed to generate dynamic universe: {exc}"))
            _pause()
            return

    print(f"\n  {dim('Reference Bhavcopy:')} {bold(os.path.basename(top_csv))}")

    now = datetime.now()
    screener = StockScreener(processed_dir=processed_dir)
    auto_save = _confirm("Automatically save all 5+ analyzed & filtered CSVs to disk?")
    print()

    screener.screen_stocks(
        top_250_path=top_csv,
        date_obj=now,
        save_to_disk=auto_save,
    )

    print(ok("Screening complete"))
    if auto_save:
        print(ok(f"All standard reports exported to {processed_dir}"))
    else:
        print(tip("Results computed in-memory (no files written yet)"))
    logger.info("screening_completed", date=now.strftime("%Y-%m-%d"))

    df_analyzed = getattr(screener, "df_analyzed", None)
    out_date_str = now.strftime("%Y%m%d")
    if df_analyzed is None:
        analyzed_csv = os.path.join(processed_dir, f"top_250_analyzed_{out_date_str}.csv")
        if os.path.exists(analyzed_csv):
            df_analyzed = pd.read_csv(analyzed_csv)

    if df_analyzed is not None and not df_analyzed.empty:
        render_strategy_results_table(
            df_analyzed,
            title=f"ANALYSIS RESULTS — {now.strftime('%Y-%m-%d')}",
            max_rows=25,
        )
        _screener_results_menu(processed_dir, out_date_str)
    else:
        print(err("No analysis results to display."))
        _pause()


def menu_liquid_etf() -> None:
    """Run the Liquid ETF Screener and display the results."""
    _header("Liquid ETF Screener")
    print("  Fetching ETF list from NSE and calculating sector liquidity...\n")

    res = run_liquid_etf_screener()
    if not res:
        print(warn("Failed to retrieve or parse ETF data. (Check network or try in live market)"))
        _pause()
        return

    if isinstance(res, list):
        records = []
        for s in res:
            rec = {
                "ETF": s.symbol,
                "Underlying": s.meta.get("underlying", ""),
                "Category": s.meta.get("category", ""),
                "CMP": s.meta.get("cmp", 0.0),
                "Volume": s.meta.get("volume", 0),
                "Turnover": s.meta.get("weight", 0.0),
            }
            records.append(rec)
        df = pd.DataFrame(records)
    elif isinstance(res, pd.DataFrame):
        df = res
    else:
        df = pd.DataFrame()

    if df.empty:
        print(warn("No liquid ETF signals found."))
        _pause()
        return

    out_dir = "data/screener_output"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "top_liquid_etfs.csv")
    df.to_csv(out_path, index=False)

    _display_csv(out_path, "Top Liquid ETFs (By Sector)", "Highest Turnover ETFs per underlying index")
    print(f"\n  {dim(f'Saved to {out_path}')}")
    _pause()


def menu_minervini() -> None:
    """Run the Mark Minervini Trend Template Screener."""
    _header("Mark Minervini Trend Template Screener")
    print("  Loading 400 days of historical data from local parquets (F&O Universe)...")
    print("  Calculating RS Ratings, VCP, and Breakouts...\n")

    signals = run_minervini_cli()
    if not signals:
        print(warn("No stocks met the Trend Template criteria."))
        _pause()
        return

    records = []
    for sig in signals:
        rec = {"Symbol": sig.symbol}
        rec.update(sig.meta)
        records.append(rec)
    df = pd.DataFrame(records)

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


def menu_ma_slope(ticker: str | None = None) -> None:
    """Run the Moving Average Slope analyzer."""
    _header("Moving Average Slope Analyzer")

    if not ticker:
        print(f"  {dim('Example Tickers:')} RELIANCE, TCS, NIFTYBEES, INFY")
        ticker = input("  Enter Ticker (default: RELIANCE): ").strip() or "RELIANCE"

    print(f"\n  Analyzing MA slope for {ticker} over the last 30 days...\n")
    result = analyze_stock_ma_slope(ticker)

    if "error" in result:
        print(warn(result["error"]))
        _pause()
        return

    slope = result["slope"]
    trend = result["trend"]

    print(f"  {bold('Trend Analysis Results')}")
    print(f"  Stock: {ticker}")
    print(f"  20-Day MA Slope (30-day window): {slope:.4f}")

    color = "green" if slope > 0 else ("red" if slope < 0 else "white")
    print(f"  Trend Strength & Direction: [{color}]{trend}[/{color}]\n")
    _pause()


def menu_squeeze(ticker: str | None = None) -> None:
    """Run the Momentum Squeeze Indicator analysis."""
    _header("Momentum Squeeze Indicator")

    if not ticker:
        print(f"  {dim('Example Tickers:')} RELIANCE, TCS, NIFTYBEES, BANKBEES")
        ticker = input("  Enter Ticker (default: RELIANCE): ").strip() or "RELIANCE"

    period = input("  Lookback period [6mo/1y/2y] (default: 6mo): ").strip() or "6mo"
    print(f"\n  Computing squeeze for {ticker} | period={period}...\n")

    signals = run_squeeze_cli(symbol=ticker, period=period)
    if not signals:
        print(warn("No squeeze data returned. Check the symbol and period."))
        _pause()
        return

    records = [
        {"Symbol": s.symbol, "Strategy": s.strategy_name, "Action": s.action, "Conviction": s.conviction, "Timestamp": s.timestamp, **s.meta}
        for s in signals
    ]
    df = pd.DataFrame(records)

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


def menu_unified_scanner(data_dir: str, hist_dir: str) -> None:
    """Run the Unified Grouped Scanner."""
    _header("Unified Grouped Multi-Scanner")
    print("  Scanner groups available:")
    print("   1. Bull Trend       (Minervini Template + Darvas Box Breakout)")
    print("   2. Momentum         (Momentum Squeeze on key index and sectors)")
    print("   3. Mean Reversion   (RSI Oversold + Cointegration Pairs)")
    print("   4. Asset Allocation (Liquid Sector/Commodity ETFs)")
    print("   5. All              (Run all groups)")
    print()

    choice = input("  Select Group [1-5, default 5]: ").strip()
    mapping = {
        "1": "Bull Trend",
        "2": "Momentum",
        "3": "Mean Reversion",
        "4": "Asset Allocation",
        "5": "All",
        "": "All",
    }
    group_name = mapping.get(choice, "All")

    print(f"\n  Running '{group_name}' scanner group...\n")
    try:
        signals = run_unified_scanner(group_name, data_dir=data_dir, hist_dir=hist_dir)
        df = compile_signals_to_dataframe(signals)
    except Exception as exc:
        print(err(f"Unified scanner execution failed: {exc}"))
        logger.error("unified_scanner_failed", error=str(exc))
        _pause()
        return

    if df.empty:
        print(warn(f"No signals generated for group '{group_name}' today."))
        _pause()
        return

    out_dir = "data/screener_output"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "unified_signals.csv")
    df.to_csv(out_path, index=False)

    _display_csv(
        out_path,
        f"Unified Scanner Output — {group_name}",
        "Consolidated signals from all active quantitative scanners grouped by behavior.",
    )
    print(f"\n  {dim(f'Saved to {out_path}')}")
    _pause()


def menu_nifty_ki_dukan(hist_dir: str, data_dir: str) -> None:
    """Discount screener for Nifty 50/500 stocks (Mahesh Kaushik strategy)."""
    _header("Nifty Ki Dukan (Mahesh Kaushik Strategy)")
    try:
        from src.scanners.nifty_ki_dukan import run_nifty_ki_dukan

        df = run_nifty_ki_dukan(hist_dir, data_dir)
        if df is not None and not df.empty:
            print(df.to_string())
        else:
            print("No matching stocks found for Nifty Ki Dukan.")
    except Exception as e:
        print(err(f"Error running Nifty Ki Dukan: {e}"))
    _pause()
