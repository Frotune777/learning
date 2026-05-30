from typing import Callable
from src.core.signal import Signal

# Import all scanners
from src.scanners.rsi_scanner import scan_rsi_signals
from src.scanners.darvas_box import scan_darvas_breakouts
from src.scanners.momentum_squeeze import run_squeeze_cli
from src.scanners.pair_scanner import scan_cointegrated_pairs
from src.scanners.etf_screener import run_liquid_etf_screener
from src.scanners.minervini_screener import run_minervini_cli

def get_all_scanners() -> list[Callable[..., list[Signal]]]:
    """
    Returns a list of all active scanner functions that adhere to the Signal protocol.
    """
    return [
        scan_rsi_signals,
        scan_darvas_breakouts,
        run_squeeze_cli,
        scan_cointegrated_pairs,
        run_liquid_etf_screener,
        run_minervini_cli,
    ]
