"""
File: src/cli/menus.py
Purpose: Modular facade and REPL interactive menu loop for Fortune ADSS CLI.
All domain menu handlers and presentation views are decomposed under:
  - src/cli/handlers/ (data_sync, screeners, capsule_smc, ml_analytics)
  - src/cli/renderers/ (capsule_views, screener_views, system_views)
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

import structlog

from src.cli.formatters import bold, cyan, dim, green, warn, yellow
from src.cli.handlers import (
    # Data Sync
    _find_latest_master,
    _load_symbols,
    _pre_flight_check,
    menu_bhavcopy_sync,
    menu_build_master,
    menu_data_quality,
    menu_data_source_settings,
    menu_fyers_token,
    menu_query_engine,
    menu_recompute_ta,
    menu_registry,
    menu_status,
    menu_sync_filtered,
    menu_sync_history,
    menu_sync_intraday_1h,
    menu_toggle_data_mode,
    # Screeners
    _display_strategy_results,
    _get_delivery_history,
    _screener_results_menu,
    menu_liquid_etf,
    menu_ma_slope,
    menu_minervini,
    menu_nifty_ki_dukan,
    menu_screen,
    menu_squeeze,
    menu_unified_scanner,
    # Capsule & SMC
    menu_capsule_5star,
    menu_capsule_smc,
    menu_capsule_turnover,
    menu_lux_regimes,
    menu_smc_calls,
    menu_smc_scan,
    menu_train_920130,
    # ML & Analytics
    menu_backtest,
    menu_configure_alerts,
    menu_consensus_leaderboard,
    menu_correlation,
    menu_fo_ban,
    menu_heatmap,
    menu_llm_dossier,
    menu_ml_anomaly,
    menu_mmi,
    menu_nse_live,
    menu_pair_scanner,
    menu_run_optimizer,
    menu_sector_rotation,
    menu_send_alerts,
    menu_strategy_inspector,
    menu_ta_dashboard,
    menu_train_ml,
)
from src.cli.renderers import (
    _render_capsule_table,
    render_backtest_table,
    render_capsule_table,
    render_consensus_leaderboard,
    render_dq_audit_panel,
    render_lux_regimes_table,
    render_nse_live_quote_table,
    render_option_chain_table,
    render_pre_flight_panel,
    render_strategy_inspector_card,
    render_strategy_results_table,
    render_unified_signals_table,
)
from src.cli.reporter import ScreenerReporter
from src.cli.visual import VisualUI
from src.core.config import Config

logger = structlog.get_logger("nse_pipeline.menu")
_UI = VisualUI()
_REPORTER = ScreenerReporter()

# ---------------------------------------------------------------------------
# Declarative Menu Sections Configuration: Logical Category-Grouped Codes
# ---------------------------------------------------------------------------

PRIMARY_MENU_SECTIONS = {
    "CATEGORY 10 — DATA & LAKE OPERATIONS": [
        ("11", "Sync 1D Historical Data", "menu_sync_history", "Daily OHLCV Parquet lake sync (all Bhavcopy EQ)"),
        ("12", "Sync 1H Intraday Data", "menu_sync_intraday_1h", "60-minute intraday bars for Train 920/130"),
        ("13", "Data Quality Gate & Auto-Healer", "menu_data_quality", "Scan master symbols and fix data gaps/NaNs"),
        ("14", "Configure Fyers API Token", "menu_fyers_token", "Configure Fyers access token for Tier-2 cascade"),
    ],
    "CATEGORY 20 — CAPSULE & SMC SCREENERS": [
        ("21", "Capsule 5-Star Multi-TF Screener", "menu_capsule_5star", "Farms (M), Sunflowers (W), Seeds (D) & Turnover"),
        ("22", "Train No. 920/130 Momentum Scanner", "menu_train_920130", "1H/15M 9/20 EMA + CCI 30/7 + Multi-TF RSI + OB"),
        ("23", "Simple Turnover Surge", "menu_capsule_turnover", "Turnover spike >= 50-100% + Spread < 0.5% + Mcap > 500Cr"),
        ("24", "Capsule SMC Overlap Finder", "menu_capsule_smc", "Overlapping OBs (M+W, W+D) + Spring + IFC Candle"),
        ("25", "Core Technical Screener", "menu_screen", "Stage 2, EMA alignments, Super/Final lists"),
        ("26", "Minervini Trend Template", "menu_minervini", "VCP, RS Rating & Trend Screen"),
    ],
    "CATEGORY 30 — INSPECTION, DOSSIERS & ALERTS": [
        ("31", "Single-Stock TA Dashboard", "menu_ta_dashboard", "RSI, MACD, Bollinger, ADX for one symbol"),
        ("32", "Export Symbol LLM Dossier", "menu_llm_dossier", "Deep Markdown dossier for AI/LLM analysis"),
        ("33", "Send Screener Alerts to Telegram", "menu_send_alerts", "Push today's screener CSVs to Telegram"),
    ],
    "CATEGORY 90 — ARCHIVED & EXPERIMENTAL TOOLS": [
        ("90", "Toggle Full Archive View", "toggle_archive", "Show/Hide 30 additional Quant, ML & Storage tools"),
    ],
}

ARCHIVE_MENU_SECTIONS = {
    "CATEGORY 40 — QUANTITATIVE & LIVE MARKET": [
        ("41", "Run Unified Multi-Scanner", "menu_unified_scanner", "Grouped multi-strategy market scanner"),
        ("42", "Momentum Squeeze Indicator", "menu_squeeze", "BB / KC coiled-spring detector"),
        ("43", "Moving Average Slope", "menu_ma_slope", "Trend angle analyzer"),
        ("44", "Liquid ETF Screener", "menu_liquid_etf", "Top liquid ETFs per sector"),
        ("45", "Nifty Ki Dukan", "menu_nifty_ki_dukan", "Discount screener for Nifty 50/500 stocks"),
        ("46", "SMC Live Scan & Calls", "menu_smc_scan", "Order Blocks, FVGs, Sweeps & R:R signals"),
        ("47", "SMC Signals Ledger", "menu_smc_calls", "Review saved institutional setups & calls"),
        ("48", "LuxAlgo Regime & Structure Hub", "menu_lux_regimes", "Weinstein Stages, iFVGs, VSA & NWE"),
        ("49", "Live NSE Data Hub", "menu_nse_live", "Pre-market, price info, option chain…"),
        ("50", "View F&O Ban List", "menu_fo_ban", "Fetch current NSE F&O ban securities"),
        ("51", "Market Mood Index (MMI)", "menu_mmi", "Live market sentiment scraper"),
        ("52", "Sector Rotation Chart", "menu_sector_rotation", "JdK RS-Ratio Quadrant Analysis"),
        ("53", "Cross-Asset Correlation Matrix", "menu_correlation", "Cross-asset return correlation"),
        ("54", "Nifty Indices Heatmap", "menu_heatmap", "Constituents performance heatmap"),
    ],
    "CATEGORY 50 — ML, BACKTESTING & ANALYTICS": [
        ("55", "Cointegration Pair Scanner", "menu_pair_scanner", "Engle-Granger pairs from local universe"),
        ("56", "ML Classifier Backtester", "menu_backtest", "Random Forest & Event Backtest on symbol"),
        ("57", "Train ML Models", "menu_train_ml", "Train classifiers using historical data"),
        ("58", "ML Data Anomaly Detector", "menu_ml_anomaly", "Identify bad ticks or smart money footprints"),
        ("59", "Run Strategy Optimizer", "menu_run_optimizer", "Optimize TA strategies with Optuna"),
        ("60", "Strategy Inspector", "menu_strategy_inspector", "All 13 strategy signals for one stock"),
        ("61", "Consensus Leaderboard", "menu_consensus_leaderboard", "Top stocks ranked by multi-strategy agreement"),
        ("62", "Configure Telegram Alerts", "menu_configure_alerts", "Set bot token & chat ID"),
    ],
    "CATEGORY 60 — STORAGE, SQL & ADVANCED DATA": [
        ("63", "Build / Refresh Equity Master", "menu_build_master", "Downloads sec_list + index data"),
        ("64", "Bhavcopy Incremental Sync", "menu_bhavcopy_sync", "Batch OHLCV update — 1 ZIP/day"),
        ("65", "Sync Historical ─ Filtered", "menu_sync_filtered", "By cap, index, or count"),
        ("66", "Recompute TA Indicators", "menu_recompute_ta", "Refresh all local Parquet files"),
        ("67", "Parquet Sync Status", "menu_status", "Rows, date ranges per symbol"),
        ("68", "Sync Registry", "menu_registry", "Pending / failed / ok breakdown"),
        ("69", "DuckDB SQL Engine", "menu_query_engine", "Interactive SQL prompt for Parquet data"),
        ("70", "Data Source & Download Settings", "menu_data_source_settings", "Download provider & cascade rules"),
        ("71", "Toggle Data Mode", "menu_toggle_data_mode", "Switch between Stored (Offline) and Live"),
    ],
}

# Default MENU_SECTIONS for backwards compatibility
MENU_SECTIONS = PRIMARY_MENU_SECTIONS

# Legacy option aliases mapping old numbers ('1' through '43') to new category codes
LEGACY_MENU_ALIASES: dict[str, str] = {
    "1": "63",   # Build Master
    "2": "11",   # Sync Historical All
    "3": "65",   # Sync Filtered
    "4": "25",   # Run Screener
    "5": "67",   # Sync Status
    "6": "68",   # Sync Registry
    "7": "31",   # TA Dashboard
    "8": "66",   # Recompute TA
    "9": "44",   # Liquid ETF
    "10": "26",  # Minervini
    "11": "52",  # Sector Rotation (Legacy 11)
    "12": "53",  # Correlation Matrix (Legacy 12)
    "13": "54",  # Heatmap (Legacy 13)
    "14": "51",  # MMI (Legacy 14)
    "15": "43",  # MA Slope
    "16": "42",  # Momentum Squeeze
    "17": "49",  # Live NSE Data
    "18": "55",  # Pair Scanner
    "19": "56",  # ML Classifier Backtester
    "20": "50",  # FO Ban List
    "21": "64",  # Bhavcopy Incremental Sync (Legacy 21)
    "22": "14",  # Fyers Token (Legacy 22)
    "23": "58",  # ML Data Anomaly
    "24": "60",  # Strategy Inspector
    "25": "61",  # Consensus Leaderboard (Legacy 25)
    "26": "13",  # Data Quality (Legacy 26)
    "27": "62",  # Configure Alerts
    "28": "33",  # Send Alerts
    "29": "41",  # Unified Scanner
    "30": "69",  # DuckDB Query Engine
    "31": "57",  # Train ML Models (Legacy 31)
    "32": "59",  # Run Strategy Optimizer (Legacy 32)
    "33": "45",  # Nifty Ki Dukan (Legacy 33)
    "34": "46",  # SMC Live Scan
    "35": "47",  # SMC Calls Ledger
    "36": "48",  # LuxAlgo Regimes
    "37": "32",  # Export LLM Dossier
    "38": "71",  # Toggle Data Mode
    "39": "21",  # Capsule 5-Star
    "40": "22",  # Train 920/130
    "41": "23",  # Turnover Surge
    "42": "24",  # Capsule SMC
    "43": "70",  # Data Source Settings
}


# Concise short titles and functional tags for the compact 2-column grid layout
_SHORT_NAMES: dict[str, str] = {
    "11": "Sync 1D History",
    "12": "Sync 1H Intraday",
    "13": "Data Quality Gate",
    "14": "Fyers API Token",
    "21": "Capsule 5-Star",
    "22": "Train No. 920/130",
    "23": "Turnover Surge",
    "24": "SMC Overlap Finder",
    "25": "Core Tech Screener",
    "26": "Minervini Template",
    "31": "Single-Stock TA",
    "32": "Symbol LLM Dossier",
    "33": "Telegram Alerts",
    "90": "Toggle Full Archive",
    "41": "Unified Scanner",
    "42": "Momentum Squeeze",
    "43": "MA Slope Analyzer",
    "44": "Liquid ETF Screen",
    "45": "Nifty Ki Dukan",
    "46": "SMC Live Scan",
    "47": "SMC Signals Ledger",
    "48": "LuxAlgo Regimes",
    "49": "Live NSE Data Hub",
    "50": "F&O Ban List",
    "51": "Market Mood Index",
    "52": "Sector Rotation JdK",
    "53": "Correlation Matrix",
    "54": "Indices Heatmap",
    "55": "Pair Scanner",
    "56": "ML Backtester",
    "57": "Train ML Models",
    "58": "ML Anomaly Detector",
    "59": "Strategy Optimizer",
    "60": "Strategy Inspector",
    "61": "Consensus Leader",
    "62": "Configure Alerts",
    "63": "Build Equity Master",
    "64": "Bhavcopy Sync ZIP",
    "65": "Sync Filtered Lake",
    "66": "Recompute All TA",
    "67": "Parquet Lake Status",
    "68": "Sync Registry Summary",
    "69": "DuckDB SQL Engine",
    "70": "Data Source Settings",
    "71": "Data Mode (Off/Live)",
}

_TAGS: dict[str, str] = {
    "12": "[1H]",
    "14": "[AUTH]",
    "21": "[5★]",
    "22": "[MOM]",
    "23": "[VOL]",
    "24": "[SMC]",
    "25": "[CORE]",
    "26": "[VCP]",
    "32": "[AI]",
    "33": "[TG]",
    "48": "[LUX]",
    "49": "[LIVE]",
    "51": "[SENT]",
    "56": "[ML]",
    "69": "[SQL]",
    "71": "[OFF]",
}


def _print_main_menu(show_archive: bool = False, status_bar: str | None = None) -> None:
    """Render the top-level menu using VisualUI in a compact 2-column side-by-side grid."""
    if status_bar is None:
        try:
            from src.core.config import get_stored_data_info
            data_info = get_stored_data_info("data/historical/1d")
            latest_d = data_info.get("latest_date") or "None"
            n_syms = data_info.get("symbol_count", 0)
            is_offline = getattr(Config, "OFFLINE", True)
            mode = "OFFLINE" if is_offline else "LIVE"
            mode_color = "green" if mode == "OFFLINE" else "yellow"
            status_bar = f"[bold cyan]FORTUNE ADSS[/bold cyan] [dim]│[/dim] Lake: [green]{n_syms:,} symbols[/green] ({latest_d}) [dim]│[/dim] Mode: [bold {mode_color}]{mode}[/bold {mode_color}]"
        except Exception:
            status_bar = "[bold cyan]FORTUNE ADSS[/bold cyan] [dim]│[/dim] Mode: [bold green]OFFLINE[/bold green]"

    sections_rich: dict[str, list[dict[str, Any]]] = {}
    sections_to_render = dict(PRIMARY_MENU_SECTIONS)
    if show_archive:
        sections_to_render.pop("CATEGORY 90 — ARCHIVED & EXPERIMENTAL TOOLS", None)
        sections_to_render.update(ARCHIVE_MENU_SECTIONS)
        sections_to_render["SYSTEM & NAVIGATION"] = [
            ("90", "Collapse Full Archive", "toggle_archive", "Collapse back to Categories 10, 20 & 30"),
            ("70", "Data Source Settings", "menu_data_source_settings", "Settings"),
            ("0", "Exit Application", "exit", "Exit"),
            ("71", "Toggle Data Mode", "menu_toggle_data_mode", "Data Mode"),
        ]
    else:
        sections_to_render.pop("CATEGORY 90 — ARCHIVED & EXPERIMENTAL TOOLS", None)
        sections_to_render["SYSTEM & NAVIGATION"] = [
            ("90", "Toggle Full Archive", "toggle_archive", "Show remaining 30 tools"),
            ("70", "Data Source Settings", "menu_data_source_settings", "Settings"),
            ("0", "Exit Application", "exit", "Exit"),
            ("71", "Toggle Data Mode", "menu_toggle_data_mode", "Data Mode"),
        ]

    for section_name, items in sections_to_render.items():
        opts = []
        for item in items:
            num = item[0]
            label = item[1]
            hint = item[3] if len(item) > 3 else ""
            short_name = _SHORT_NAMES.get(num, label)
            tag = _TAGS.get(num, "")
            opts.append({
                "id": num,
                "name": short_name,
                "tag": tag,
                "details": hint,
            })
        sections_rich[section_name] = opts

    _UI.render_menu("FORTUNE ADSS — MAIN MENU", sections_rich, status_bar=status_bar)


def interactive_menu(
    data_dir: str = Config.DEFAULT_DATA_DIR,
    hist_dir: str = Config.DEFAULT_HIST_DIR,
) -> None:
    """REPL-style interactive menu loop for Fortune Analytical Decision-Support System."""
    processed_dir = os.path.join(data_dir, "processed")
    from src.core.config import get_stored_data_info

    # 1. Startup Recency & Coverage Audit
    hist_1d = os.path.join(hist_dir, "1d")
    data_info = get_stored_data_info(hist_1d)
    latest_d = data_info.get("latest_date") or "None"
    n_syms = data_info.get("symbol_count", 0)
    ref_day = data_info.get("last_trading_day") or "Today"
    days_behind = data_info.get("days_behind", 0)

    is_offline = getattr(Config, "OFFLINE", True)
    mode = "OFFLINE" if is_offline else "LIVE"
    mode_color = "green" if mode == "OFFLINE" else "yellow"
    status_bar = f"[bold cyan]FORTUNE ADSS[/bold cyan] [dim]│[/dim] Lake: [green]{n_syms:,} symbols[/green] ({latest_d}) [dim]│[/dim] Mode: [bold {mode_color}]{mode}[/bold {mode_color}]"

    # 2. Inform user and ask if new data download is required if behind
    if days_behind > 0:
        print(f"\n  ⚠️  Exchange Session: {cyan(str(ref_day))} ({yellow(f'{days_behind} days behind stored data')}). Mode: {green('OFFLINE')}")
        try:
            ask = input("  Pull new data now? [y/N] (1st: YFinance, 2nd: Fyers, 3rd: NSE) [N]: ").strip().lower()
            if ask in ("y", "yes"):
                menu_sync_history(data_dir, hist_dir)
            else:
                print(f"  ✔ Continuing in {green('OFFLINE')} mode on stored data.\n")
        except (KeyboardInterrupt, EOFError):
            print()
    else:
        print(f"  ✔ Data lake is up to date with the latest NSE trading session.\n")

    # Action dispatch mapping: Category codes (11-14, 21-26, 31-33, 41-71)
    _DISPATCH: dict[str, Callable[[], None]] = {
        # Category 10 — Data & Lake Operations
        "11": lambda: menu_sync_history(data_dir, hist_dir),
        "12": lambda: menu_sync_intraday_1h(data_dir, hist_dir),
        "13": lambda: menu_data_quality(hist_dir, data_dir),
        "14": lambda: menu_fyers_token(),
        # Category 20 — Capsule & SMC Screeners
        "21": lambda: menu_capsule_5star(hist_dir, processed_dir),
        "22": lambda: menu_train_920130(hist_dir, processed_dir),
        "23": lambda: menu_capsule_turnover(hist_dir, processed_dir),
        "24": lambda: menu_capsule_smc(hist_dir, processed_dir),
        "25": lambda: menu_screen(data_dir, hist_dir, processed_dir),
        "26": lambda: menu_minervini(),
        # Category 30 — Inspection, Dossiers & Alerts
        "31": lambda: menu_ta_dashboard(hist_dir),
        "32": lambda: menu_llm_dossier(hist_dir),
        "33": lambda: menu_send_alerts(hist_dir),
        # Category 40 — Quantitative & Live Market (Archived)
        "41": lambda: menu_unified_scanner(data_dir, hist_dir),
        "42": lambda: menu_squeeze(),
        "43": lambda: menu_ma_slope(),
        "44": lambda: menu_liquid_etf(),
        "45": lambda: menu_nifty_ki_dukan(hist_dir, data_dir),
        "46": lambda: menu_smc_scan(data_dir, hist_dir),
        "47": lambda: menu_smc_calls(data_dir),
        "48": lambda: menu_lux_regimes(hist_dir),
        "49": lambda: menu_nse_live(),
        "50": lambda: menu_fo_ban(data_dir),
        "51": lambda: menu_mmi(),
        "52": lambda: menu_sector_rotation(),
        "53": lambda: menu_correlation(),
        "54": lambda: menu_heatmap(),
        # Category 50 — ML, Backtesting & Analytics (Archived)
        "55": lambda: menu_pair_scanner(hist_dir),
        "56": lambda: menu_backtest(hist_dir, data_dir),
        "57": lambda: menu_train_ml(hist_dir, data_dir),
        "58": lambda: menu_ml_anomaly(hist_dir, data_dir),
        "59": lambda: menu_run_optimizer(hist_dir, data_dir),
        "60": lambda: menu_strategy_inspector(hist_dir),
        "61": lambda: menu_consensus_leaderboard(hist_dir),
        "62": lambda: menu_configure_alerts(),
        # Category 60 — Storage, SQL & Advanced Data (Archived)
        "63": lambda: menu_build_master(data_dir),
        "64": lambda: menu_bhavcopy_sync(data_dir, hist_dir),
        "65": lambda: menu_sync_filtered(data_dir, hist_dir),
        "66": lambda: menu_recompute_ta(hist_dir),
        "67": lambda: menu_status(hist_dir, data_dir),
        "68": lambda: menu_registry(data_dir, hist_dir),
        "69": lambda: menu_query_engine(hist_dir, data_dir),
        "70": lambda: menu_data_source_settings(),
        "71": lambda: menu_toggle_data_mode(),
    }

    show_archive = False
    while True:
        _print_main_menu(show_archive=show_archive, status_bar=status_bar)
        try:
            choice = input(f"  {dim('>')} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n  {dim('Bye!')}\n")
            break

        if choice == "0" or choice.lower() == "exit":
            print(f"\n  {dim('Bye!')}\n")
            logger.info("menu_exit")
            break

        if choice == "90":
            show_archive = not show_archive
            mode_str = "Expanded (All Categories)" if show_archive else "Collapsed (Primary)"
            print(f"  {green('✔')} Archive View: {cyan(mode_str)}")
            continue

        handler = _DISPATCH.get(choice)
        if not handler and choice in LEGACY_MENU_ALIASES:
            target_code = LEGACY_MENU_ALIASES[choice]
            handler = _DISPATCH.get(target_code)

        if handler:
            handler()
        else:
            print(warn(f"'{choice}' is not a valid option — enter category codes (11-14, 21-26, 31-33, 41-71, 90) or legacy 1-43."))


__all__ = [
    "PRIMARY_MENU_SECTIONS",
    "ARCHIVE_MENU_SECTIONS",
    "MENU_SECTIONS",
    "LEGACY_MENU_ALIASES",
    "_print_main_menu",
    "interactive_menu",
    "_find_latest_master",
    "_load_symbols",
    "_get_delivery_history",
    "_display_strategy_results",
    "_screener_results_menu",
    "_pre_flight_check",
    "_render_capsule_table",
    "render_capsule_table",
    "render_strategy_inspector_card",
    "render_consensus_leaderboard",
    "render_strategy_results_table",
    "render_unified_signals_table",
    "render_lux_regimes_table",
    "render_backtest_table",
    "render_dq_audit_panel",
    "render_pre_flight_panel",
    "render_nse_live_quote_table",
    "render_option_chain_table",
    "menu_build_master",
    "menu_sync_history",
    "menu_sync_filtered",
    "menu_screen",
    "menu_status",
    "menu_registry",
    "menu_ta_dashboard",
    "menu_recompute_ta",
    "menu_liquid_etf",
    "menu_minervini",
    "menu_sector_rotation",
    "menu_correlation",
    "menu_heatmap",
    "menu_mmi",
    "menu_ma_slope",
    "menu_squeeze",
    "menu_nse_live",
    "menu_pair_scanner",
    "menu_backtest",
    "menu_fo_ban",
    "menu_bhavcopy_sync",
    "menu_fyers_token",
    "menu_ml_anomaly",
    "menu_strategy_inspector",
    "menu_consensus_leaderboard",
    "menu_data_quality",
    "menu_configure_alerts",
    "menu_send_alerts",
    "menu_unified_scanner",
    "menu_query_engine",
    "menu_train_ml",
    "menu_run_optimizer",
    "menu_nifty_ki_dukan",
    "menu_smc_scan",
    "menu_smc_calls",
    "menu_lux_regimes",
    "menu_llm_dossier",
    "menu_toggle_data_mode",
    "menu_capsule_5star",
    "menu_train_920130",
    "menu_capsule_turnover",
    "menu_capsule_smc",
    "menu_data_source_settings",
]
