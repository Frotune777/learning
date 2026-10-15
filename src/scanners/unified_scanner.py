"""
File: src/scanners/unified_scanner.py
Purpose: Coordinator that executes, groups, and consolidates all strategy scanners.
Last Modified: 2026-06-09
"""

import glob
import logging
import os

import pandas as pd

from src.core.signal import Signal
from src.scanners.darvas_box import scan_darvas_breakouts
from src.scanners.etf_screener import run_liquid_etf_screener
from src.scanners.minervini_screener import run_minervini_cli
from src.scanners.momentum_squeeze import run_squeeze_cli
from src.scanners.pair_scanner import run_pair_scanner_cli
from src.scanners.rsi_scanner import scan_rsi_signals

LOGGER = logging.getLogger(__name__)

# Scanner Group definitions
SCANNER_GROUPS = {
    "Bull Trend": ["minervini_screener", "darvas_box"],
    "Momentum": ["momentum_squeeze"],
    "Mean Reversion": ["rsi_scanner", "pair_scanner"],
    "Asset Allocation": ["etf_screener"],
}


def get_latest_analyzed_csv(processed_dir: str) -> str | None:
    """Finds the latest analyzed CSV file from the processed directory."""
    if not os.path.isdir(processed_dir):
        return None
    
    # Check analyzed files first, then fallback to enriched or general CSVs
    candidates = sorted(glob.glob(os.path.join(processed_dir, "top_250_analyzed_*.csv")))
    if not candidates:
        candidates = sorted(glob.glob(os.path.join(processed_dir, "top_250_enriched_*.csv")))
    if not candidates:
        candidates = sorted(glob.glob(os.path.join(processed_dir, "top_250_*.csv")))
    if not candidates:
        candidates = sorted(glob.glob(os.path.join(processed_dir, "*.csv")))
        
    return candidates[-1] if candidates else None


def run_unified_scanner(
    group_name: str,
    data_dir: str = "data",
    hist_dir: str = "data/historical",
) -> list[Signal]:
    """
    Executes and consolidates signals from a selected group of scanners.
    
    Parameters:
        group_name (str): One of "Bull Trend", "Momentum", "Mean Reversion",
                          "Asset Allocation", or "All".
        data_dir (str): Root data directory.
        hist_dir (str): Directory containing historical parquets.
        
    Returns:
        list[Signal]: Consolidated list of Signal objects.
    """
    group_name = group_name.strip()
    active_groups = []
    if group_name == "All":
        active_groups = list(SCANNER_GROUPS.keys())
    elif group_name in SCANNER_GROUPS:
        active_groups = [group_name]
    else:
        LOGGER.error("Invalid scanner group requested: %s", group_name)
        return []

    processed_dir = os.path.join(data_dir, "processed")
    daily_dir = os.path.join(hist_dir, "1d")
    latest_csv = get_latest_analyzed_csv(processed_dir)

    all_signals: list[Signal] = []

    # 1. Bull Trend Group
    if "Bull Trend" in active_groups:
        LOGGER.info("Running Bull Trend scanner group...")
        
        # Minervini Screener
        try:
            LOGGER.info("Executing Mark Minervini template...")
            signals = run_minervini_cli(hist_dir=daily_dir)
            all_signals.extend(signals)
        except Exception as exc:
            LOGGER.error("Minervini template failed: %s", exc)

        # Darvas Box Breakout
        if latest_csv:
            try:
                LOGGER.info("Executing Darvas Box breakouts on %s...", latest_csv)
                df_analyzed = pd.read_csv(latest_csv)
                signals = scan_darvas_breakouts(
                    df_analyzed, daily_dir=daily_dir, date_str=""
                )
                all_signals.extend(signals)
            except Exception as exc:
                LOGGER.error("Darvas Box breakouts failed: %s", exc)
        else:
            LOGGER.warning("Skipping Darvas Box: No analyzed CSV found in %s", processed_dir)

    # 2. Momentum Group
    if "Momentum" in active_groups:
        LOGGER.info("Running Momentum scanner group...")
        
        # Momentum Squeeze - run on indices to evaluate market impulse
        momentum_symbols = ["^NSEI", "^CNXIT", "^CNXBANK", "^CNXMETAL", "^CNXAUTO"]
        for sym in momentum_symbols:
            try:
                LOGGER.info("Executing Momentum Squeeze for %s...", sym)
                signals = run_squeeze_cli(symbol=sym, period="6mo", hist_dir=daily_dir)
                # run_squeeze_cli returns the last 10 signals; we only want the latest one
                if signals:
                    all_signals.append(signals[-1])
            except Exception as exc:
                LOGGER.error("Momentum Squeeze failed for %s: %s", sym, exc)

    # 3. Mean Reversion Group
    if "Mean Reversion" in active_groups:
        LOGGER.info("Running Mean Reversion scanner group...")
        
        # RSI Oversold Scanner
        if latest_csv:
            try:
                LOGGER.info("Executing RSI oversold scanner on %s...", latest_csv)
                signals = scan_rsi_signals(latest_csv)
                all_signals.extend(signals)
            except Exception as exc:
                LOGGER.error("RSI oversold scanner failed: %s", exc)
        else:
            LOGGER.warning("Skipping RSI scanner: No analyzed CSV found in %s", processed_dir)

        # Cointegration Pair Scanner
        try:
            LOGGER.info("Executing Cointegration Pair scanner...")
            signals = run_pair_scanner_cli(daily_dir=daily_dir, max_pairs=30, symbol_limit=80)
            all_signals.extend(signals)
        except Exception as exc:
            LOGGER.error("Cointegration Pair scanner failed: %s", exc)

    # 4. Asset Allocation Group
    if "Asset Allocation" in active_groups:
        LOGGER.info("Running Asset Allocation scanner group...")
        
        # Liquid ETF Screener
        try:
            LOGGER.info("Executing Liquid ETF screener...")
            signals = run_liquid_etf_screener()
            all_signals.extend(signals)
        except Exception as exc:
            LOGGER.error("Liquid ETF screener failed: %s", exc)

    return all_signals


def get_group_for_strategy(strategy_name: str) -> str:
    """Helper to map strategy name to its category group."""
    for grp, strats in SCANNER_GROUPS.items():
        if strategy_name in strats:
            return grp
    return "Other"


def get_display_name_for_strategy(strategy_name: str) -> str:
    """Helper to map a strategy name to a clean display name."""
    mapping = {
        "minervini_screener": "Mark Minervini Template",
        "darvas_box": "Darvas Box Breakout",
        "momentum_squeeze": "Momentum Squeeze",
        "rsi_scanner": "RSI Oversold (<35)",
        "pair_scanner": "Cointegration Pair Spread",
        "etf_screener": "Liquid ETF Screener",
    }
    return mapping.get(strategy_name, strategy_name)


def compile_signals_to_dataframe(signals: list[Signal]) -> pd.DataFrame:
    """
    Compiles a raw list of Signal objects into a clean, unified DataFrame.
    """
    if not signals:
        return pd.DataFrame()

    records = []
    for sig in signals:
        grp = get_group_for_strategy(sig.strategy_name)
        strat = get_display_name_for_strategy(sig.strategy_name)
        action_str = "BUY" if sig.action == 1 else "SELL" if sig.action == -1 else "HOLD"
        
        # Build clean user-facing details string from meta dictionary
        details = ""
        meta = sig.meta or {}
        if sig.strategy_name == "darvas_box":
            details = f"{meta.get('raw_signal', 'Consolidating')} | Box High: {meta.get('box_high', 'N/A')}, Low: {meta.get('box_low', 'N/A')} ({meta.get('box_days', 0)} days)"
        elif sig.strategy_name == "minervini_screener":
            details = f"Score: {meta.get('template_score', 0)}/9 | RS Rating: {meta.get('rs_rating', 0.0)} | Vol: {meta.get('rvol', 0.0)}x"
        elif sig.strategy_name == "momentum_squeeze":
            details = f"{meta.get('raw_signal', 'Neutral')} | Close: {meta.get('close', 0.0):.2f}"
        elif sig.strategy_name == "rsi_scanner":
            details = f"RSI: {meta.get('rsi_value', 0.0):.1f} ({meta.get('step_hint', 'Step 1')}) | CMP: {meta.get('cmp', 0.0)}"
        elif sig.strategy_name == "pair_scanner":
            details = f"Pair with {meta.get('pair_symbol', 'N/A')} | Trade: {meta.get('trade_type', 'Neutral')} (z-score: {meta.get('z_score', 0.0):.2f})"
        elif sig.strategy_name == "etf_screener":
            details = f"Sector ETF for {meta.get('category', 'Index')} | Underlying: {meta.get('underlying', 'N/A')}"
        else:
            details = f"Conviction: {sig.conviction} | Action: {action_str}"

        records.append({
            "Symbol": sig.symbol,
            "Scanner Group": grp,
            "Strategy": strat,
            "Direction": action_str,
            "Conviction": f"{int(sig.conviction * 100)}%",
            "Details": details,
            "Timestamp": sig.timestamp.strftime("%Y-%m-%d %H:%M") if hasattr(sig.timestamp, "strftime") else str(sig.timestamp)
        })

    df = pd.DataFrame(records)
    # Sort logically: group first, then symbol, then strategy
    df = df.sort_values(by=["Scanner Group", "Symbol", "Strategy"]).reset_index(drop=True)
    return df
