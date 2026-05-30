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


import rich
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
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
def _print_banner() -> None:
    """Print the application banner."""
    print()
    print(_rule("═"))
    print()
    print(f"  {bold(white('NSE DATA PIPELINE'))}  {dim('v2026-05')}")
    print(f"  {dim('Equity Master  ·  Historical Sync  ·  Technical Screener')}")
    print()
    print(_rule("═"))
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
