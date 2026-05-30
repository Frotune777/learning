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

import logging
import sys



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


from src.cli.menus import interactive_menu, _build_parser
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
