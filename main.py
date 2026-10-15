"""
File: main.py
Purpose: Unified CLI entry point for the NSE data pipeline.
"""

import argparse
import logging
import os
import sys

from src.cli.actions import (
    cmd_backtest,
    cmd_bhavcopy_sync,
    cmd_build_master,
    cmd_fo_ban,
    cmd_fyers_login,
    cmd_fyers_token,
    cmd_ml_anomaly,
    cmd_run_optimizer,
    cmd_screen,
    cmd_smc_calls,
    cmd_smc_scan,
    cmd_sync_history,
    cmd_train_ml,
)
from src.cli.formatters import red
from src.cli.menus import interactive_menu
from src.core.config import Config, setup_logging

setup_logging()
logger = logging.getLogger("nse_pipeline")


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="nse-pipeline",
        description="NSE Data Pipeline: build master → sync history → screen stocks",
        epilog=(
            "Use 'menu' command for interactive mode (default).\n"
            "Global flags (--data-dir, --hist-dir, --dry-run) must appear BEFORE\n"
            "the subcommand. Example:\n"
            "  python main.py --data-dir /tmp/foo fo-ban\n"
            "  python main.py --data-dir /tmp/foo smc-calls"
        ),
    )
    parser.add_argument(
        "--data-dir",
        default=Config.DEFAULT_DATA_DIR,
        dest="data_dir",
        help=f"Root data directory (default: {Config.DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--hist-dir",
        default=Config.DEFAULT_HIST_DIR,
        dest="hist_dir",
        help=f"Historical Parquet directory (default: {Config.DEFAULT_HIST_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate operations without making changes",
    )

    sub = parser.add_subparsers(dest="command")

    # build-master
    p_master = sub.add_parser("build-master", help="Build equity master table.")
    p_master.add_argument(
        "--delay", type=float, default=1.0, help="Seconds between index API calls"
    )
    p_master.set_defaults(func=cmd_build_master)

    # sync-history
    p_sync = sub.add_parser("sync-history", help="Sync per-symbol OHLCV Parquet files.")
    p_sync.add_argument("--timeframe", default=Config.DEFAULT_TIMEFRAME)
    p_sync.add_argument("--start-date", default=Config.DEFAULT_START_DATE)
    p_sync.add_argument("--cap-filter", choices=["Large", "Mid", "Small", "Other"])
    p_sync.add_argument("--index-filter")
    p_sync.add_argument("--limit", type=int)
    p_sync.add_argument("--delay", type=float, default=0.5)
    p_sync.add_argument("--source", default="bhavcopy", choices=["bhavcopy", "master"])
    p_sync.set_defaults(func=cmd_sync_history)

    # screen
    p_screen = sub.add_parser("screen", help="Run technical screener.")
    p_screen.add_argument(
        "--processed-dir", default=os.path.join(Config.DEFAULT_DATA_DIR, "processed")
    )
    p_screen.add_argument("--cap-filter", choices=["Large", "Mid", "Small", "Other"])
    p_screen.add_argument("--index-filter")
    p_screen.add_argument("--limit", type=int)
    p_screen.set_defaults(func=cmd_screen)

    # backtest
    p_backtest = sub.add_parser("backtest", help="Run ML backtest.")
    p_backtest.add_argument("--symbol", required=True)
    p_backtest.add_argument("--n-estimators", type=int, default=100)
    p_backtest.add_argument("--max-depth", type=int, default=5)
    p_backtest.set_defaults(func=cmd_backtest)

    # ml-anomaly
    p_anomaly = sub.add_parser(
        "ml-anomaly", help="Run ML anomaly detection for data quality."
    )
    p_anomaly.add_argument("--symbol", required=True)
    p_anomaly.set_defaults(func=cmd_ml_anomaly)

    # fo-ban
    sub.add_parser("fo-ban", help="Fetch F&O ban list.").set_defaults(func=cmd_fo_ban)

    # bhavcopy-sync
    p_bsync = sub.add_parser("bhavcopy-sync", help="Fast incremental OHLCV update.")
    p_bsync.add_argument("--days", type=int, default=10)
    p_bsync.add_argument("--timeframe", default=Config.DEFAULT_TIMEFRAME)
    p_bsync.add_argument("--limit", type=int)
    p_bsync.add_argument("--no-ta", action="store_true", dest="no_ta")
    p_bsync.add_argument("--delay", type=float, default=1.0)
    p_bsync.set_defaults(func=cmd_bhavcopy_sync)

    # fyers-login
    sub.add_parser("fyers-login", help="Get Fyers login URL.").set_defaults(
        func=cmd_fyers_login
    )

    # fyers-token
    p_ft = sub.add_parser("fyers-token", help="Exchange auth code for token.")
    p_ft.add_argument("--code", required=True)
    p_ft.set_defaults(func=cmd_fyers_token)

    # train-ml
    sub.add_parser("train-ml", help="Train ML models interactively.").set_defaults(
        func=cmd_train_ml
    )

    # optimize
    sub.add_parser("optimize", help="Run strategy optimizer interactively.").set_defaults(
        func=cmd_run_optimizer
    )

    # smc-scan
    p_smc_scan = sub.add_parser(
        "smc-scan", help="Run Smart Money Concepts (SMC) scanner across historical data."
    )
    p_smc_scan.add_argument("--limit", type=int, help="Limit number of symbols to scan")
    p_smc_scan.add_argument("--symbol", type=str, help="Scan a single specific symbol (e.g. RELIANCE)")
    p_smc_scan.set_defaults(func=cmd_smc_scan)

    # smc-calls
    p_smc_calls = sub.add_parser(
        "smc-calls", help="View logged SMC trading calls from local SQLite database."
    )
    p_smc_calls.add_argument(
        "--status",
        choices=["PENDING", "ACTIVE", "TRIGGERED", "CANCELLED", "TARGET_HIT", "STOPPED"],
        help="Filter calls by execution status",
    )
    p_smc_calls.set_defaults(func=cmd_smc_calls)

    # menu (default)
    sub.add_parser("menu", help="Launch interactive menu.").set_defaults(
        func=lambda args: interactive_menu(args.data_dir, args.hist_dir)
    )

    return parser


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point for the CLI application."""
    parser = _build_parser()
    args = parser.parse_args()

    # Default to menu if no command provided
    if not hasattr(args, "command") or args.command is None:
        interactive_menu(args.data_dir, args.hist_dir)
        return

    # Set dry-run mode if specified
    if hasattr(args, "dry_run") and args.dry_run:
        logger.info("dry_run_mode_enabled")

    # Execute command
    if hasattr(args, "func"):
        try:
            args.func(args)
        except Exception as e:
            logger.error("command_failed: command=%s error=%s", args.command, str(e))
            print(f"\n  {red('Error:')} {e!s}\n")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()