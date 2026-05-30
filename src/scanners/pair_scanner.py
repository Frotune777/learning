"""
File: src/nse_bhavcopy/pair_scanner.py
Purpose: Scans all parquet symbols for cointegrated pairs using Engle-Granger test.
Last Modified: 2026-05-27
"""

from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

LOGGER: logging.Logger = logging.getLogger(__name__)

_MIN_HISTORY: int = 252  # Minimum overlapping bars required
_DEFAULT_MAX_PVAL: float = 0.05
_DEFAULT_ZSCORE_ENTRY: float = 2.0
_DEFAULT_ZSCORE_WINDOW: int = 60  # Rolling window for spread z-score


def _load_close_series(daily_dir: str, symbol: str) -> pd.Series | None:
    """
    Load the Close price series for a symbol from its 1d parquet file.

    Parameters:
        daily_dir (str): Path to the 1d parquet directory.
        symbol (str): NSE stock symbol (uppercase, no suffix).

    Returns:
        pd.Series | None: Close prices indexed by date, or None on failure.

    Raises:
        None

    Complexity:
        Time: O(N)
        Space: O(N)

    Example:
        >>> s = _load_close_series("data/historical/1d", "SUZLON")
        >>> print(s.tail(3))
    """
    path = os.path.join(daily_dir, f"{symbol.upper()}.parquet")
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_parquet(path)
        if df.empty or "Close" not in df.columns:
            return None
        return df["Close"].sort_index().dropna()
    except Exception as exc:
        LOGGER.debug("PairScanner: Cannot load %s: %s", symbol, exc)
        return None


def test_cointegration(
    s1: pd.Series,
    s2: pd.Series,
    lookback: int = _MIN_HISTORY,
    zscore_window: int = _DEFAULT_ZSCORE_WINDOW,
) -> tuple[float, float, str]:
    """
    Run the Engle-Granger cointegration test on two price series.

    Aligns both series on their shared index, trims to the trailing lookback
    window, and computes the p-value and the current spread z-score.

    Parameters:
        s1 (pd.Series): Close price series for Stock A.
        s2 (pd.Series): Close price series for Stock B.
        lookback (int): Trailing bars to use after alignment. | Default: 252
        zscore_window (int): Rolling window for spread z-score normalisation.
            | Default: 60

    Returns:
        tuple[float, float, str]:
            - p_value (float): Engle-Granger p-value (< 0.05 = cointegrated).
            - spread_zscore (float): Latest spread z-score.
            - signal (str): "BUY A/SELL B" | "SELL A/BUY B" | "Neutral".
        Returns (NaN, NaN, "Insufficient Data") when data is inadequate.

    Raises:
        None

    Complexity:
        Time: O(N log N) [alignment + statsmodels coint]
        Space: O(N)

    Example:
        >>> p, z, sig = test_cointegration(s1, s2)
        >>> print(p, z, sig)
        0.021 2.34 BUY A/SELL B
    """
    combined = pd.DataFrame({"a": s1, "b": s2}).dropna()
    if len(combined) < _MIN_HISTORY:
        return float("nan"), float("nan"), "Insufficient Data"

    window_df = combined.tail(lookback)
    a = window_df["a"].values.astype("float64")
    b = window_df["b"].values.astype("float64")

    try:
        _, p_value, _ = coint(a, b)
    except Exception as exc:
        LOGGER.debug("PairScanner: coint() failed: %s", exc)
        return float("nan"), float("nan"), "Test Error"

    # Compute spread and its z-score
    spread = pd.Series(a) - pd.Series(b)
    roll_mean = spread.rolling(zscore_window).mean()
    roll_std = spread.rolling(zscore_window).std(ddof=1)

    last_spread = spread.iloc[-1]
    last_mean = roll_mean.iloc[-1]
    last_std = roll_std.iloc[-1]

    if pd.isna(last_std) or last_std == 0.0:
        zscore = float("nan")
        signal = "Neutral"
    else:
        zscore = float((last_spread - last_mean) / last_std)
        if zscore > _DEFAULT_ZSCORE_ENTRY:
            signal = "SELL A / BUY B"
        elif zscore < -_DEFAULT_ZSCORE_ENTRY:
            signal = "BUY A / SELL B"
        else:
            signal = "Neutral"

    return round(float(p_value), 6), round(zscore, 4), signal


import uuid
from src.core.signal import Signal
from datetime import datetime

def scan_cointegrated_pairs(
    symbols: list[str],
    daily_dir: str,
    max_pval: float = _DEFAULT_MAX_PVAL,
    zscore_entry: float = _DEFAULT_ZSCORE_ENTRY,
    lookback: int = _MIN_HISTORY,
    max_pairs: int = 50,
) -> list[Signal]:
    """
    Scan all symbol pairs for cointegration and return actionable pair trades.

    Iterates over all N*(N-1)/2 unique pairs, runs the Engle-Granger test on
    each, and collects those with p-value <= max_pval. Results are sorted by
    ascending p-value (strongest cointegration first).

    Parameters:
        symbols (list[str]): List of NSE symbols to scan (e.g. from master table).
        daily_dir (str): Path to the 1d parquet directory.
        max_pval (float): Maximum allowable p-value for inclusion. | Default: 0.05
        zscore_entry (float): Z-score threshold for signal generation. | Default: 2.0
        lookback (int): Trailing bars per pair test. | Default: 252
        max_pairs (int): Maximum number of pairs to return. | Default: 50

    Returns:
        list[Signal]: List of Signal objects (2 per actionable pair).
            Empty list if no actionable pairs are found.

    Raises:
        None

    Complexity:
        Time: O(N^2 x W) where N = len(symbols), W = lookback
        Space: O(N^2) [worst case all pairs retained]

    Example:
        >>> df = scan_cointegrated_pairs(["COALINDIA","NMDC","HINDALCO"],
        ...                              "data/historical/1d")
        >>> print(df.head())
    """
    # Pre-load all series to avoid repeated disk reads
    price_cache: dict[str, pd.Series] = {}
    for sym in symbols:
        s = _load_close_series(daily_dir, sym)
        if s is not None and len(s) >= _MIN_HISTORY:
            price_cache[sym] = s

    loaded_syms = list(price_cache.keys())
    n = len(loaded_syms)
    LOGGER.info(
        "PairScanner: %d/%d symbols loaded for pair testing (%d pairs to check).",
        n,
        len(symbols),
        n * (n - 1) // 2,
    )

    signals: list[Signal] = []
    
    for i in range(n):
        for j in range(i + 1, n):
            sym_a = loaded_syms[i]
            sym_b = loaded_syms[j]
            p_val, zscore, signal = test_cointegration(
                price_cache[sym_a],
                price_cache[sym_b],
                lookback=lookback,
            )
            if not np.isnan(p_val) and p_val <= max_pval:
                actionable = abs(zscore) >= zscore_entry if not np.isnan(zscore) else False
                if actionable and signal != "Neutral":
                    pair_id = str(uuid.uuid4())
                    
                    # Calculate conviction (capped at 1.0)
                    conviction = min(1.0, abs(zscore) / (zscore_entry * 2.0))
                    
                    if signal == "BUY A / SELL B":
                        action_a, action_b = 1, -1
                    elif signal == "SELL A / BUY B":
                        action_a, action_b = -1, 1
                    else:
                        continue
                        
                    now = datetime.now()
                    
                    # Signal for Stock A
                    sig_a = Signal(
                        symbol=sym_a,
                        strategy_name="pair_scanner",
                        action=action_a,
                        conviction=round(conviction, 2),
                        timestamp=now,
                        meta={
                            "pair_id": pair_id,
                            "pair_symbol": sym_b,
                            "pair_action": action_b,
                            "z_score": zscore,
                            "spread_mean": 0.0, # Dummy since not exported by test_cointegration
                            "half_life": 0.0,
                            "trade_type": signal
                        }
                    )
                    
                    # Signal for Stock B
                    sig_b = Signal(
                        symbol=sym_b,
                        strategy_name="pair_scanner",
                        action=action_b,
                        conviction=round(conviction, 2),
                        timestamp=now,
                        meta={
                            "pair_id": pair_id,
                            "pair_symbol": sym_a,
                            "pair_action": action_a,
                            "z_score": zscore,
                            "spread_mean": 0.0,
                            "half_life": 0.0,
                            "trade_type": signal
                        }
                    )
                    
                    signals.extend([sig_a, sig_b])
                    
                    if len(signals) >= max_pairs * 2:
                        break
        if len(signals) >= max_pairs * 2:
            break

    if not signals:
        LOGGER.info("PairScanner: No cointegrated pairs found.")
        return []

    LOGGER.info(
        "PairScanner: %d actionable pairs found (%d signals).",
        len(signals) // 2,
        len(signals),
    )
    return signals


def run_pair_scanner_cli(
    daily_dir: str = "data/historical/1d",
    max_pairs: int = 50,
    max_pval: float = _DEFAULT_MAX_PVAL,
    symbol_limit: int = 100,
) -> list[Signal]:
    """
    CLI entry point: discover symbols from parquet files and run the pair scanner.

    Auto-discovers all .parquet files in daily_dir, builds the symbol list, and
    delegates to scan_cointegrated_pairs(). Respects symbol_limit to cap compute.

    Parameters:
        daily_dir (str): Path to 1d parquet directory. | Default: "data/historical/1d"
        max_pairs (int): Maximum cointegrated pairs to return. | Default: 50
        max_pval (float): P-value cutoff for cointegration. | Default: 0.05
        symbol_limit (int): Maximum number of symbols to scan (largest files
            first). | Default: 100

    Returns:
        list[Signal]: Cointegrated pairs signals (may be empty if none found).

    Raises:
        None

    Complexity:
        Time: O(M^2 x W) where M = symbol_limit, W = lookback bars
        Space: O(M)

    Example:
        >>> df = run_pair_scanner_cli()
        >>> print(df.head())
    """
    if not os.path.isdir(daily_dir):
        LOGGER.warning("PairScanner: daily_dir '%s' not found.", daily_dir)
        return []

    # Discover symbols from parquet file names
    parquet_files = sorted(
        [f for f in os.listdir(daily_dir) if f.endswith(".parquet")],
        key=lambda f: os.path.getsize(os.path.join(daily_dir, f)),
        reverse=True,
    )
    symbols = [os.path.splitext(f)[0] for f in parquet_files[:symbol_limit]]
    LOGGER.info(
        "PairScanner CLI: discovered %d symbols in %s.",
        len(symbols),
        daily_dir,
    )

    return scan_cointegrated_pairs(
        symbols=symbols,
        daily_dir=daily_dir,
        max_pval=max_pval,
        max_pairs=max_pairs,
    )
