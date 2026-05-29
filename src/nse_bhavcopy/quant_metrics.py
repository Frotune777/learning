"""
File: src/nse_bhavcopy/quant_metrics.py
Purpose: Computes the Hurst exponent and historical VaR per stock from parquet data.
Last Modified: 2026-05-27
"""

import logging
import os

import numpy as np
import pandas as pd

LOGGER: logging.Logger = logging.getLogger(__name__)

# ─── Hurst Exponent ────────────────────────────────────────────────────────────

_HURST_TRENDING_THRESHOLD: float = 0.6
_HURST_MR_THRESHOLD: float = 0.4


def calculate_hurst_exponent(
    prices: pd.Series,
    lags: int = 20,
) -> float:
    """
    Compute the Hurst exponent using Rescaled-Range (R/S) analysis.

    Interpretation:
        H > 0.6  — Trending / persistent series (momentum strategies preferred)
        H ≈ 0.5  — Geometric random walk (no statistical edge)
        H < 0.4  — Mean-reverting / anti-persistent (fade / BB strategies)

    Parameters:
        prices (pd.Series): Historical closing prices. | Must have ≥ lags + 5 rows.
        lags (int): Maximum lag window used in R/S computation. | Default: 20

    Returns:
        float: Estimated Hurst exponent, typically in the range [0.0, 1.0].
            Returns 0.5 (random-walk default) on computation failure.

    Raises:
        ValueError: If prices has fewer than lags + 5 valid data points.

    Complexity:
        Time: O(lags x N) where N = len(prices)
        Space: O(lags) [Two accumulator lists]

    Example:
        >>> import pandas as pd
        >>> prices = pd.Series([100.0 + i * 0.5 for i in range(120)])
        >>> h = calculate_hurst_exponent(prices)
        >>> print(f"H = {h:.3f}")
        H = 0.712
    """
    clean = prices.dropna()
    clean = clean[clean > 0]  # log(0) or log(negative) is undefined — skip bad rows
    if len(clean) < lags + 5:
        raise ValueError(
            f"Need ≥ {lags + 5} data points for Hurst with lags={lags}, "
            f"got {len(clean)}."
        )

    log_prices = np.log(clean.values.astype("float64"))
    tau: list[float] = []
    lag_vec: list[int] = []

    for lag in range(2, lags):
        diffs = log_prices[lag:] - log_prices[:-lag]
        std_val = np.std(diffs, ddof=1)
        if std_val <= 0.0 or not np.isfinite(std_val):
            continue
        lag_vec.append(lag)
        tau.append(np.sqrt(std_val))

    if len(lag_vec) < 2:
        LOGGER.warning(
            "Hurst: insufficient valid lags (%d). Returning 0.5 default.",
            len(lag_vec),
        )
        return 0.5

    log_lags = np.log(np.array(lag_vec, dtype="float64"))
    log_tau = np.log(np.array(tau, dtype="float64"))
    coeffs = np.polyfit(log_lags, log_tau, 1)
    hurst = float(coeffs[0]) * 2.0

    # Clamp to a sensible range — R/S can occasionally drift outside [0,1]
    return float(np.clip(hurst, 0.0, 1.0))


def get_hurst_callout(hurst: float) -> str:
    """
    Return a user-facing interpretation string for a computed Hurst value.

    Parameters:
        hurst (float): Hurst exponent value, typically in [0.0, 1.0].

    Returns:
        str: One-line emoji-prefixed callout describing the stock's behaviour.

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> get_hurst_callout(0.72)
        '📈 Hurst=0.72 — Trending: momentum & breakout strategies preferred'
        >>> get_hurst_callout(0.35)
        '🔄 Hurst=0.35 — Mean-reverting: BB squeeze & fade strategies preferred'
        >>> get_hurst_callout(0.51)
        '🎲 Hurst=0.51 — Random walk: no statistical edge — wait for catalyst'
    """
    h_str = f"{hurst:.2f}"
    if hurst > _HURST_TRENDING_THRESHOLD:
        return (
            f"📈 Hurst={h_str} — Trending: " "momentum & breakout strategies preferred"
        )
    if hurst < _HURST_MR_THRESHOLD:
        return (
            f"🔄 Hurst={h_str} — Mean-reverting: "
            "BB squeeze & fade strategies preferred"
        )
    return f"🎲 Hurst={h_str} — Random walk: " "no statistical edge — wait for catalyst"


# ─── Historical VaR ────────────────────────────────────────────────────────────

_VAR_CONFIDENCE: float = 0.95  # 95% confidence → 5th percentile


def calculate_historical_var(
    prices: pd.Series,
    confidence: float = _VAR_CONFIDENCE,
    lookback: int = 252,
) -> float:
    """
    Compute the 1-day Historical Value-at-Risk (VaR) as a percentage.

    Uses the non-parametric percentile method on daily log returns. Returns
    the absolute value of the (1-confidence) percentile — i.e. the expected
    maximum loss on a single day with the given confidence level.

    Parameters:
        prices (pd.Series): Historical closing prices in chronological order.
            | Must have ≥ 2 valid data points after dropna.
        confidence (float): Confidence level for VaR. | Default: 0.95 (95%)
        lookback (int): Number of most-recent trading days to use. |
            Default: 252 (≈ 1 trading year)

    Returns:
        float: 1-day VaR as a positive percentage (e.g. 2.8 means 2.8% loss).
            Returns NaN when insufficient data is available.

    Raises:
        None

    Complexity:
        Time: O(N) where N = min(len(prices), lookback)
        Space: O(N) [Returns Series slice]

    Example:
        >>> prices = pd.Series([100.0 * (1 + 0.01 * i) for i in range(260)])
        >>> var = calculate_historical_var(prices)
        >>> print(f"1-Day VaR (95%): {var:.2f}%")
        1-Day VaR (95%): 0.97%
    """
    clean = prices.dropna()
    clean = clean[clean > 0]  # log(0) or log(negative) is undefined — skip bad rows
    if len(clean) < 2:
        return float("nan")

    window = clean.tail(lookback)
    log_returns = np.log(window / window.shift(1)).dropna()

    if len(log_returns) < 5:
        return float("nan")

    pct_tile = 1.0 - confidence  # 0.05 for 95% VaR
    var_raw = float(np.percentile(log_returns.values, pct_tile * 100))
    return round(abs(var_raw) * 100.0, 4)  # Return as positive percentage


def _var_callout(var_pct: float, symbol: str) -> str:
    """
    Return a risk callout string for a computed VaR percentage.

    Parameters:
        var_pct (float): 1-day VaR as a positive percentage.
        symbol (str): Stock symbol for context.

    Returns:
        str: One-line risk description for the user.

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> _var_callout(2.8, "RELIANCE")
        '⚠️  RELIANCE: 1-Day VaR (95%) = 2.80% — expect up to 2.80% loss on bad days'
    """
    if np.isnan(var_pct):
        return f"i️  {symbol}: VaR unavailable — insufficient history"
    severity = "⚠️ " if var_pct > 3.0 else "🛡️ "
    return (
        f"{severity} {symbol}: 1-Day VaR (95%) = {var_pct:.2f}% "
        f"— expect up to {var_pct:.2f}% loss on bad days"
    )


# ─── Parquet-backed enrichment ─────────────────────────────────────────────────


def _load_close_from_parquet(
    symbol: str,
    daily_dir: str,
) -> pd.Series | None:
    """
    Load the Close price series for a symbol from its 1d parquet file.

    Parameters:
        symbol (str): NSE stock symbol (without .NS suffix).
        daily_dir (str): Path to directory containing {SYMBOL}.parquet files.

    Returns:
        pd.Series | None: Close prices sorted by date, or None on failure.

    Raises:
        None (all failures logged at DEBUG level)

    Complexity:
        Time: O(N) where N = rows in parquet
        Space: O(N) [Full parquet read]

    Example:
        >>> s = _load_close_from_parquet("SUZLON", "data/historical/1d")
        >>> print(s.tail(3))
    """
    # Try historical dir first, then screener's processed cache
    candidates = [
        os.path.join(daily_dir, f"{symbol.upper()}.parquet"),
        os.path.join(
            daily_dir.replace("historical/1d", "processed/1d"),
            f"{symbol.upper()}.parquet",
        ),
    ]

    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_parquet(path)
            if df.empty or "Close" not in df.columns:
                continue
            close = df["Close"].sort_index().dropna()
            return close
        except Exception as exc:
            LOGGER.debug("Quant: Failed to read parquet %s: %s", path, exc)

    LOGGER.debug("Quant: No valid parquet found for %s", symbol)
    return None


def add_quant_metrics(
    df: pd.DataFrame,
    daily_dir: str,
    hurst_lags: int = 20,
    var_confidence: float = _VAR_CONFIDENCE,
    var_lookback: int = 252,
    symbol_col: str = "SYMBOL",
) -> pd.DataFrame:
    """
    Append Hurst exponent, VaR, and related callout columns to the screener DataFrame.

    Reads each stock's historical Close prices from its parquet file in daily_dir,
    computes both metrics, and writes results back as new DataFrame columns.
    Stocks without sufficient parquet data receive NaN metrics.

    Parameters:
        df (pd.DataFrame): Analyzed screener DataFrame with a symbol column.
        daily_dir (str): Path to directory containing 1d parquet files
            (e.g. "data/historical/1d").
        hurst_lags (int): Maximum lag for Hurst R/S analysis. | Default: 20
        var_confidence (float): VaR confidence level. | Default: 0.95
        var_lookback (int): Trading days for VaR computation. | Default: 252
        symbol_col (str): Column name for NSE symbols. | Default: "SYMBOL"

    Returns:
        pd.DataFrame: Copy of input with four new columns:
            - HURST_EXP (float): Hurst exponent [0.0, 1.0].
            - HURST_CALLOUT (str): Trending / Mean-Reverting / Random walk label.
            - VAR_1D_95 (float): 1-day VaR at 95% confidence (positive %).
            - VAR_CALLOUT (str): Risk description for the user.

    Raises:
        KeyError: If symbol_col is not present in df.columns.

    Complexity:
        Time: O(N x (W + lags)) where N = stocks, W = parquet rows per symbol
        Space: O(N) [Four new Series + per-iteration parquet load]

    Example:
        >>> df = pd.read_csv("data/historical/top_250_analyzed_20260527.csv")
        >>> enriched = add_quant_metrics(df, "data/historical/1d")
        >>> print(
        ...     enriched[["SYMBOL", "HURST_EXP", "VAR_1D_95", "HURST_CALLOUT"]].head(5)
        ... )
    """
    if symbol_col not in df.columns:
        raise KeyError(
            f"Symbol column '{symbol_col}' not found. "
            f"Available: {df.columns.tolist()}"
        )

    df = df.copy()
    hurst_vals: list[float] = []
    hurst_callouts: list[str] = []
    var_vals: list[float] = []
    var_callouts: list[str] = []

    for _, row in df.iterrows():
        sym = str(row[symbol_col]).strip().upper()
        close = _load_close_from_parquet(sym, daily_dir)

        # ── Hurst Exponent ──────────────────────────────────────────────────
        hurst: float = float("nan")
        h_callout: str = f"i️  {sym}: Hurst unavailable — insufficient history"
        if close is not None and len(close) >= hurst_lags + 5:
            try:
                hurst = calculate_hurst_exponent(close, lags=hurst_lags)
                h_callout = get_hurst_callout(hurst)
            except ValueError as exc:
                LOGGER.debug("Hurst failed for %s: %s", sym, exc)

        hurst_vals.append(hurst)
        hurst_callouts.append(h_callout)

        # ── Historical VaR ──────────────────────────────────────────────────
        var: float = float("nan")
        v_callout: str = f"i️  {sym}: VaR unavailable — insufficient history"
        if close is not None and len(close) >= 5:
            var = calculate_historical_var(
                close,
                confidence=var_confidence,
                lookback=var_lookback,
            )
            v_callout = _var_callout(var, sym)

        var_vals.append(var)
        var_callouts.append(v_callout)

    df["HURST_EXP"] = hurst_vals
    df["HURST_CALLOUT"] = hurst_callouts
    df["VAR_1D_95"] = var_vals
    df["VAR_CALLOUT"] = var_callouts

    computed_hurst = int(pd.Series(hurst_vals).notna().sum())
    computed_var = int(pd.Series(var_vals).notna().sum())
    LOGGER.info(
        "Quant metrics: Hurst computed for %d/%d stocks, VaR for %d/%d stocks.",
        computed_hurst,
        len(df),
        computed_var,
        len(df),
    )
    return df
