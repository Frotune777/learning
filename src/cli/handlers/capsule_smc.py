"""
Capsule Academy 5-Star Multi-TF and Smart Money Concepts (SMC) menu handlers.
"""

from __future__ import annotations

import argparse
import glob
import os
from datetime import datetime

import pandas as pd
import structlog

from src.cli.formatters import _header, _pause, bold, cyan, dim, err, ok, tip, warn, yellow
from src.cli.renderers.capsule_views import render_capsule_table
from src.cli.renderers.screener_views import render_lux_regimes_table
from src.cli.visual import VisualUI

logger = structlog.get_logger("nse_pipeline.capsule_smc")
_UI = VisualUI()


def menu_capsule_5star(hist_dir: str, processed_dir: str) -> None:
    """Capsule Academy 5-Star Multi-Timeframe Screener (Farms, Sunflowers, Seeds)."""
    _UI.render_header(
        "CAPSULE ACADEMY: 5-STAR MULTI-TF SCREENER",
        "Monthly Farms (Star 1), Weekly Sunflowers (Star 2), Daily Seeds (Star 3) & Simple Turnover (Star 4)",
    )
    print(dim("  Based on Dr. Nayeem Ahmad Shariff's 5-Star Study & Capsule Framework.\n"))

    from src.scanners.capsule_screener import run_capsule_screener

    hist_1d = os.path.join(hist_dir, "1d") if os.path.isdir(os.path.join(hist_dir, "1d")) else hist_dir

    limit_ans = input("  Scan universe size (Enter count or press Enter for Top 250) [250]: ").strip()
    limit = int(limit_ans) if limit_ans.isdigit() else 250

    min_stars_ans = input("  Minimum Star threshold (1 to 5) [2]: ").strip()
    min_stars = int(min_stars_ans) if min_stars_ans.isdigit() else 2

    print(f"\n  {cyan(f'Scanning offline Parquet lake (analyzing up to {limit} stocks)...')}")
    df = run_capsule_screener(hist_1d, min_stars=min_stars, limit=limit)
    if df.empty:
        print(yellow("\n  No stocks matched the 5-Star criteria at this threshold."))
    else:
        render_capsule_table(df, title=f"CAPSULE ACADEMY 5-STAR LEADERBOARD (Top {len(df)} Setups)", mode="5star")
        today_str = datetime.now().strftime("%Y%m%d_%H%M")
        out_csv = os.path.join(processed_dir, f"capsule_5star_{today_str}.csv")
        os.makedirs(processed_dir, exist_ok=True)
        df.to_csv(out_csv, index=False)
        print(ok(f"\n  Results exported to {out_csv}"))
    _pause()


def menu_train_920130(hist_dir: str, processed_dir: str) -> None:
    """Capsule Academy Train No. 920/130 Momentum Scanner."""
    _UI.render_header(
        "TRAIN NO. 920/130 MOMENTUM SCANNER",
        "1H/15M 9/20 EMA Crossover above 200 EMA + Day CCI 30/7 + Multi-TF RSI Alignment",
    )
    print(dim("  Momentum Strategy: Rapid price movement (1 day to 1 week holding).\n"))

    from src.scanners.capsule_screener import run_capsule_screener

    hist_1d = os.path.join(hist_dir, "1d") if os.path.isdir(os.path.join(hist_dir, "1d")) else hist_dir

    limit_ans = input("  Scan universe size [250]: ").strip()
    limit = int(limit_ans) if limit_ans.isdigit() else 250

    print(f"\n  {cyan('Searching for Train No. 920/130 Boarding signals in offline data...')}")
    df = run_capsule_screener(hist_1d, only_train_920130=True, limit=limit)
    if df.empty:
        print(yellow("\n  No active Train No. 920/130 Boarding signals found in scanned stocks."))
    else:
        render_capsule_table(df, title=f"TRAIN NO. 920/130 BOARDING SIGNALS ({len(df)} Stocks)", mode="train")
        today_str = datetime.now().strftime("%Y%m%d_%H%M")
        out_csv = os.path.join(processed_dir, f"train_920130_{today_str}.csv")
        os.makedirs(processed_dir, exist_ok=True)
        df.to_csv(out_csv, index=False)
        print(ok(f"\n  Results exported to {out_csv}"))
        print(tip("  De-boarding (Exit) Rule: Book profits on 30m 9/20 CrossDown. Book loss only if 1hr 9/20 CrossDown or OB fails."))
    _pause()


def menu_capsule_turnover(hist_dir: str, processed_dir: str) -> None:
    """Capsule Academy Simple Turnover Surge Screener."""
    _UI.render_header(
        "SIMPLE TURNOVER & LIQUIDITY SURGE",
        "Volume * Price surge > 50-100% vs 20-day Average Turnover · Spread < 0.5% · Mcap > 500Cr",
    )

    from src.scanners.capsule_screener import run_capsule_screener

    hist_1d = os.path.join(hist_dir, "1d") if os.path.isdir(os.path.join(hist_dir, "1d")) else hist_dir

    limit_ans = input("  Scan universe size [250]: ").strip()
    limit = int(limit_ans) if limit_ans.isdigit() else 250

    print(f"\n  {cyan('Filtering stocks by Simple Turnover surge & institutional participation...')}")
    df = run_capsule_screener(hist_1d, only_turnover_surge=True, limit=limit)
    if df.empty:
        print(yellow("\n  No stocks matched the turnover surge threshold."))
    else:
        render_capsule_table(df, title=f"TURNOVER SURGE CANDIDATES ({len(df)} Stocks)", mode="turnover")
    _pause()


def menu_capsule_smc(hist_dir: str, processed_dir: str) -> None:
    """Capsule Academy Smart Money Concept Overlap & Wyckoff Spring Finder."""
    _UI.render_header(
        "CAPSULE SMC & ORDER BLOCK OVERLAP FINDER",
        "Overlapping Order Blocks (Farms: M+W, Sunflowers: W+D, Seeds: D+3H) + Wyckoff Spring + IFC",
    )

    from src.scanners.capsule_screener import run_capsule_screener

    hist_1d = os.path.join(hist_dir, "1d") if os.path.isdir(os.path.join(hist_dir, "1d")) else hist_dir

    limit_ans = input("  Scan universe size [250]: ").strip()
    limit = int(limit_ans) if limit_ans.isdigit() else 250

    print(f"\n  {cyan('Analyzing Order Block Overlaps & Liquidity Springs...')}")
    df = run_capsule_screener(hist_1d, limit=limit, min_stars=1)
    if not df.empty:
        smc_candidates = df[(df["SMC_Setup"] != "None") | (df["Spring"] == "✔") | (df["IFC"] == "✔")]
        if not smc_candidates.empty:
            render_capsule_table(smc_candidates, title=f"CAPSULE SMC INSTITUTIONAL SETUPS ({len(smc_candidates)} Stocks)", mode="smc")
        else:
            print(yellow("\n  No active overlapping OBs or Springs detected in this batch."))
    else:
        print(yellow("\n  No candidates found."))
    _pause()


def menu_smc_scan(data_dir: str, hist_dir: str) -> None:
    """Run SMC scanner and generate high R:R institutional calls."""
    _header("Smart Money Concepts (SMC) Institutional Scanner")
    from src.cli.actions import cmd_smc_scan

    sym_in = input("  Filter symbol [or press Enter for all available parquets]: ").strip()
    limit_in = input("  Max symbols to scan [default 50]: ").strip()
    limit_val = int(limit_in) if limit_in.isdigit() else 50
    args = argparse.Namespace(
        data_dir=data_dir,
        hist_dir=hist_dir,
        symbol=sym_in if sym_in else None,
        limit=limit_val,
    )
    cmd_smc_scan(args)
    _pause()


def menu_smc_calls(data_dir: str) -> None:
    """View stored SMC calls in SQLite database."""
    _header("SMC Institutional Calls Ledger")
    from src.cli.actions import cmd_smc_calls

    status_filter = input("  Filter status (ALL, PENDING, TRIGGERED, STOPPED, TARGET_HIT) [ALL]: ").strip().upper()
    args = argparse.Namespace(
        data_dir=data_dir,
        status=None if status_filter in ("", "ALL") else status_filter,
    )
    cmd_smc_calls(args)
    _pause()


def menu_lux_regimes(hist_dir: str) -> None:
    """Run Stan Weinstein Stage Classifier & LuxAlgo Regimes."""
    _header("LuxAlgo & Quantitative Regime Classifier")
    from src.engine.lux_weinstein import calculate_weinstein_stage

    search_dirs = [os.path.join(hist_dir, "1d"), hist_dir]
    files = []
    for d in search_dirs:
        if os.path.isdir(d):
            found = sorted(glob.glob(os.path.join(d, "*.parquet")))
            if found:
                files = found
                break

    if not files:
        print(err("No Parquet files found in hist_dir."))
        _pause()
        return

    sample = files[:40]
    print(f"  Evaluating 30-week Weinstein Macro Cycles across {len(sample)} symbols...\n")
    records = []

    for f in sample:
        sym = os.path.basename(f).replace(".parquet", "")
        try:
            df = pd.read_parquet(f)
            df.columns = [c.lower() for c in df.columns]
            if len(df) >= 60:
                res = calculate_weinstein_stage(df, ma_weeks=10, slope_weeks=2, is_daily=True)
                action = (
                    "[bold green]STAGE 2 BREAKOUT[/bold green]"
                    if res.is_breakout
                    else ("[bold red]STAGE 4 BREAKDOWN[/bold red]" if res.is_breakdown else "—")
                )
                records.append({
                    "symbol": sym,
                    "stage_name": res.stage_name,
                    "current_stage": res.current_stage,
                    "ma_value": res.ma_value,
                    "ma_slope_pct": res.ma_slope_pct,
                    "volume_ratio": res.volume_ratio,
                    "action": action,
                })
        except Exception:
            continue

    if records:
        render_lux_regimes_table(records)
    else:
        print(yellow("No eligible records found to classify."))
    _pause()
