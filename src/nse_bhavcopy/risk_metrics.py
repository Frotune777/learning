"""
File: src/nse_bhavcopy/risk_metrics.py
Purpose: Computes Sharpe ratio, Calmar ratio, Beta, and Max Drawdown per stock.
Last Modified: 2026-05-27
"""

from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

LOGGER: logging.Logger = logging.getLogger(__name__)

# ─── Constants ─────────────────────────────────────────────────────────────────

_TRADING_DAYS: int = 252
_RISK_FREE_ANNUAL: float = 0.06  # 6% annualised (approximate Indian T-bill rate)
_RISK_FREE_DAILY: float = _RISK_FREE_ANNUAL / _TRADING_DAYS
_LOOKBACK: int = 252  # 1 trading year
_MIN_OBS: int = 30  # Minimum observations required to compute any metric


# ─── Core Calculation Functions ────────────────────────────────────────────────


def calculate_max_drawdown(prices: pd.Series, lookback: int = _LOOKBACK) -> float:
    """
    Compute the peak-to-trough maximum drawdown over a trailing lookback window.

    Parameters:
        prices (pd.Series): Historical closing prices in chronological order.
            | Must have ≥ 2 valid non-null data points.
        lookback (int): Number of most-recent trading days to use. | Default: 252

    Returns:
        float: Maximum drawdown as a negative percentage (e.g. -22.4 means
            -22.4% peak-to-trough). Returns NaN when insufficient data.

    Raises:
        None

    Complexity:
        Time: O(N) [cummax + divide]
        Space: O(N) [rolling series]

    Example:
        >>> import pandas as pd
        >>> prices = pd.Series([100, 120, 90, 110, 80, 130])
        >>> calculate_max_drawdown(prices)
        -33.33...
    """
    clean = prices.dropna()
    if len(clean) < 2:
        return float("nan")
    window = clean.tail(lookback)
    roll_max = window.cummax()
    drawdown = (window - roll_max) / roll_max * 100.0
    return float(drawdown.min())


def calculate_sharpe_ratio(
    prices: pd.Series,
    risk_free_daily: float = _RISK_FREE_DAILY,
    lookback: int = _LOOKBACK,
) -> float:
    """
    Compute the annualised Sharpe ratio from trailing daily log returns.

    Parameters:
        prices (pd.Series): Historical closing prices in chronological order.
            | Must have ≥ min 31 valid data points after dropna.
        risk_free_daily (float): Daily risk-free rate used in excess-return calc.
            | Default: 0.06/252 ≈ 0.0002381 (6% annual / 252 days)
        lookback (int): Trailing days window for computation. | Default: 252

    Returns:
        float: Annualised Sharpe ratio. Returns NaN when data is insufficient
            or standard deviation is zero.

    Raises:
        None

    Complexity:
        Time: O(N) [log + mean + std]
        Space: O(N) [returns Series]

    Example:
        >>> import pandas as pd
        >>> prices = pd.Series([100.0 * (1.001 ** i) for i in range(260)])
        >>> calculate_sharpe_ratio(prices)
        3.14...
    """
    clean = prices.dropna()
    if len(clean) < _MIN_OBS + 1:
        return float("nan")

    window = clean.tail(lookback + 1)
    log_returns = np.log(window / window.shift(1)).dropna()

    if len(log_returns) < _MIN_OBS:
        return float("nan")

    excess = log_returns - risk_free_daily
    std = float(excess.std(ddof=1))
    if std == 0.0 or not np.isfinite(std):
        return float("nan")

    sharpe = float(excess.mean()) / std * np.sqrt(_TRADING_DAYS)
    return float(round(sharpe, 4))


def calculate_calmar_ratio(
    prices: pd.Series,
    lookback: int = _LOOKBACK,
) -> float:
    """
    Compute the Calmar ratio as annualised CAGR divided by absolute max drawdown.

    Parameters:
        prices (pd.Series): Historical closing prices in chronological order.
            | Must have ≥ 2 valid data points.
        lookback (int): Trailing days window for computation. | Default: 252

    Returns:
        float: Calmar ratio (positive = good). Returns NaN when max drawdown
            is zero or data is insufficient.

    Raises:
        None

    Complexity:
        Time: O(N)
        Space: O(N)

    Example:
        >>> import pandas as pd
        >>> prices = pd.Series([100.0 * (1.001 ** i) for i in range(260)])
        >>> calculate_calmar_ratio(prices)
        3.87...
    """
    clean = prices.dropna()
    if len(clean) < 2:
        return float("nan")

    window = clean.tail(lookback)
    n_days = len(window)
    if n_days < 2:
        return float("nan")

    start = float(window.iloc[0])
    end = float(window.iloc[-1])
    if start <= 0.0 or end <= 0.0:
        return float("nan")

    cagr = ((end / start) ** (_TRADING_DAYS / n_days)) - 1.0
    max_dd = calculate_max_drawdown(window, lookback=n_days)

    if np.isnan(max_dd) or max_dd == 0.0:
        return float("nan")

    calmar = cagr / abs(max_dd / 100.0)
    return round(float(calmar), 4)


def calculate_beta(
    stock_prices: pd.Series,
    benchmark_prices: pd.Series,
    lookback: int = _LOOKBACK,
) -> float:
    """
    Compute the stock's beta relative to a benchmark using OLS on log returns.

    Beta > 1: amplifies benchmark moves (aggressive).
    Beta < 1: dampens benchmark moves (defensive).
    Beta < 0: moves inversely to benchmark.

    Parameters:
        stock_prices (pd.Series): Stock daily close prices (chronological).
        benchmark_prices (pd.Series): Benchmark daily close prices (^NSEI).
            | Dates must overlap sufficiently with stock_prices.
        lookback (int): Trailing days window. | Default: 252

    Returns:
        float: OLS beta coefficient. Returns NaN on insufficient overlap
            or singular matrix.

    Raises:
        None

    Complexity:
        Time: O(N) [align + OLS]
        Space: O(N)

    Example:
        >>> stock = pd.Series([100.0 * (1.001 ** i) for i in range(260)])
        >>> nifty = pd.Series([200.0 * (1.0008 ** i) for i in range(260)])
        >>> calculate_beta(stock, nifty)
        1.24...
    """
    s_clean = stock_prices.dropna().tail(lookback + 1)
    b_clean = benchmark_prices.dropna().tail(lookback + 1)

    # Align on common index
    combined = pd.DataFrame({"stock": s_clean, "bench": b_clean}).dropna()

    if len(combined) < _MIN_OBS:
        return float("nan")

    r_stock = np.log(combined["stock"] / combined["stock"].shift(1)).dropna()
    r_bench = np.log(combined["bench"] / combined["bench"].shift(1)).dropna()

    # Re-align after pct_change shift
    r_combined = pd.DataFrame({"stock": r_stock, "bench": r_bench}).dropna()

    if len(r_combined) < _MIN_OBS:
        return float("nan")

    cov_matrix = np.cov(r_combined["stock"].values, r_combined["bench"].values)
    bench_var = cov_matrix[1, 1]

    if bench_var == 0.0 or not np.isfinite(bench_var):
        return float("nan")

    beta = cov_matrix[0, 1] / bench_var
    return round(float(beta), 4)


# ─── Callout Builder ───────────────────────────────────────────────────────────


def _risk_callout(
    sharpe: float,
    calmar: float,
    beta: float,
    max_dd: float,
    symbol: str,
) -> str:
    """
    Build a concise risk summary string for a stock.

    Parameters:
        sharpe (float): Annualised Sharpe ratio.
        calmar (float): Calmar ratio.
        beta (float): OLS beta vs Nifty.
        max_dd (float): Max drawdown % (negative).
        symbol (str): Stock symbol for labelling.

    Returns:
        str: One-line emoji-prefixed risk summary.

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> _risk_callout(1.8, 2.1, 1.2, -15.3, "SUZLON")
        '⭐ SUZLON: Sharpe=1.80 | Calmar=2.10 | Beta=1.20 | MaxDD=-15.30%'
    """
    parts: list[str] = [symbol]
    if np.isfinite(sharpe):
        parts.append(f"Sharpe={sharpe:.2f}")
    if np.isfinite(calmar):
        parts.append(f"Calmar={calmar:.2f}")
    if np.isfinite(beta):
        parts.append(f"Beta={beta:.2f}")
    if np.isfinite(max_dd):
        parts.append(f"MaxDD={max_dd:.2f}%")

    # Pick badge based on Sharpe
    if np.isfinite(sharpe) and sharpe >= 1.5:
        badge = "⭐"
    elif np.isfinite(sharpe) and sharpe >= 0.5:
        badge = "📊"
    else:
        badge = "⚠️ "

    return f"{badge} {' | '.join(parts)}"


# ─── Parquet Loader ────────────────────────────────────────────────────────────


def _load_close(symbol: str, daily_dir: str) -> pd.Series | None:
    """
    Load the Close price series for a symbol from its 1d parquet file.

    Parameters:
        symbol (str): NSE stock symbol without suffix (e.g. "SUZLON").
        daily_dir (str): Path to directory containing {SYMBOL}.parquet files.

    Returns:
        pd.Series | None: Close prices sorted by date, or None on failure.

    Raises:
        None

    Complexity:
        Time: O(N) where N = parquet rows
        Space: O(N)

    Example:
        >>> s = _load_close("TCS", "data/historical/1d")
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
        LOGGER.debug("RiskMetrics: Failed reading %s: %s", path, exc)
        return None


# ─── DataFrame Enrichment ──────────────────────────────────────────────────────


def add_risk_metrics(
    df: pd.DataFrame,
    daily_dir: str,
    symbol_col: str = "SYMBOL",
    lookback: int = _LOOKBACK,
) -> pd.DataFrame:
    """
    Append Sharpe, Calmar, Beta, MaxDrawdown, and risk callout to screener DataFrame.

    Reads each stock's historical Close prices from parquet, computes all
    four metrics, and writes results as new DataFrame columns. Stocks without
    sufficient parquet data receive NaN metrics; the enrichment never raises.

    Parameters:
        df (pd.DataFrame): Analyzed screener DataFrame with a symbol column.
        daily_dir (str): Path to directory containing 1d parquet files.
            | Expected filename pattern: {SYMBOL}.parquet
        symbol_col (str): Column name for NSE symbols. | Default: "SYMBOL"
        lookback (int): Trailing trading days for all metrics. | Default: 252

    Returns:
        pd.DataFrame: Copy of input with five new columns:
            - SHARPE_1Y (float): Annualised Sharpe ratio (1-year window).
            - CALMAR_RATIO (float): CAGR divided by absolute max drawdown.
            - BETA_NIFTY (float): OLS beta relative to Nifty 50 (^NSEI).
            - MAX_DRAWDOWN_PCT (float): Peak-to-trough % loss (negative).
            - RISK_CALLOUT (str): Human-readable risk summary.

    Raises:
        KeyError: If symbol_col is not present in df.columns.

    Complexity:
        Time: O(N x W) where N = stocks, W = parquet rows per symbol
        Space: O(N) [Five new Series + per-iteration parquet load]

    Example:
        >>> df = pd.read_csv("data/historical/top_250_analyzed_20260527.csv")
        >>> enriched = add_risk_metrics(df, "data/historical/1d")
        >>> print(enriched[["SYMBOL","SHARPE_1Y","CALMAR_RATIO","BETA_NIFTY"]].head())
    """
    if symbol_col not in df.columns:
        raise KeyError(
            f"Symbol column '{symbol_col}' not found. "
            f"Available: {df.columns.tolist()}"
        )

    df = df.copy()

    # Pre-load Nifty benchmark once
    nifty_close: pd.Series | None = None
    for nifty_sym in ("NSEI", "^NSEI", "NIFTY50"):
        nifty_close = _load_close(nifty_sym, daily_dir)
        if nifty_close is not None:
            break
    if nifty_close is None:
        LOGGER.warning(
            "RiskMetrics: Nifty benchmark not found in %s — Beta will be NaN.",
            daily_dir,
        )

    sharpe_vals: list[float] = []
    calmar_vals: list[float] = []
    beta_vals: list[float] = []
    maxdd_vals: list[float] = []
    callout_vals: list[str] = []

    computed = 0
    for _, row in df.iterrows():
        sym = str(row[symbol_col]).strip().upper()
        close = _load_close(sym, daily_dir)

        sharpe = float("nan")
        calmar = float("nan")
        beta = float("nan")
        max_dd = float("nan")

        if close is not None and len(close) >= _MIN_OBS + 1:
            sharpe = calculate_sharpe_ratio(close, lookback=lookback)
            calmar = calculate_calmar_ratio(close, lookback=lookback)
            max_dd = calculate_max_drawdown(close, lookback=lookback)

            if nifty_close is not None:
                beta = calculate_beta(close, nifty_close, lookback=lookback)

            computed += 1

        sharpe_vals.append(sharpe)
        calmar_vals.append(calmar)
        beta_vals.append(beta)
        maxdd_vals.append(max_dd)
        callout_vals.append(_risk_callout(sharpe, calmar, beta, max_dd, sym))

    df["SHARPE_1Y"] = sharpe_vals
    df["CALMAR_RATIO"] = calmar_vals
    df["BETA_NIFTY"] = beta_vals
    df["MAX_DRAWDOWN_PCT"] = maxdd_vals
    df["RISK_CALLOUT"] = callout_vals

    LOGGER.info(
        "RiskMetrics: computed for %d/%d stocks (Sharpe, Calmar, Beta, MaxDD).",
        computed,
        len(df),
    )
    return df
