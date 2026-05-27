"""
File: src/nse_bhavcopy/volatility_regime.py
Purpose: Classifies each stock's current volatility environment using GARCH(1,1).
Last Modified: 2026-05-27
"""

from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

LOGGER: logging.Logger = logging.getLogger(__name__)

_TRADING_DAYS: int = 252
_MIN_OBS: int = 60
_HIGH_VOL_THRESHOLD: float = 35.0
_LOW_VOL_THRESHOLD: float = 15.0


def fit_garch_vol(returns: pd.Series, p: int = 1, q: int = 1) -> float:
    """
    Fit a GARCH(p, q) model and return the latest annualised conditional volatility.

    Parameters:
        returns (pd.Series): Daily log-return series. | Minimum 60 observations.
        p (int): GARCH lag order. | Default: 1
        q (int): ARCH lag order. | Default: 1

    Returns:
        float: Latest annualised conditional volatility in percent. NaN on failure.

    Raises:
        None

    Complexity:
        Time: O(N) [GARCH EM iteration]
        Space: O(N)

    Example:
        >>> import pandas as pd, numpy as np
        >>> rets = pd.Series(np.random.randn(300) * 0.01)
        >>> fit_garch_vol(rets)
        16.42...
    """
    try:
        from arch import arch_model
    except ImportError:
        LOGGER.warning("VolRegime: 'arch' not installed — GARCH unavailable.")
        return float("nan")

    clean = returns.dropna()
    if len(clean) < _MIN_OBS:
        return float("nan")

    try:
        scaled = clean * 100.0
        model = arch_model(scaled, vol="GARCH", p=p, q=q, dist="normal")
        res = model.fit(disp="off", show_warning=False)
        cond_vol = res.conditional_volatility
        cond_vol_pct = float(pd.Series(cond_vol).iloc[-1])
        annual_vol = cond_vol_pct * np.sqrt(_TRADING_DAYS)
        return float(round(annual_vol, 4))
    except Exception as exc:
        LOGGER.debug("GARCH fit failed: %s", exc)
        return float("nan")


def classify_vol_regime(annual_vol_pct: float) -> str:
    """
    Classify annualised volatility into a named regime tier.

    Parameters:
        annual_vol_pct (float): Annualised conditional volatility in percent.

    Returns:
        str: One of "High", "Medium", "Low", or "Unknown" if NaN/infinite.

    Raises:
        None

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> classify_vol_regime(40.0)
        'High'
        >>> classify_vol_regime(10.0)
        'Low'
    """
    if not np.isfinite(annual_vol_pct):
        return "Unknown"
    if annual_vol_pct >= _HIGH_VOL_THRESHOLD:
        return "High"
    if annual_vol_pct <= _LOW_VOL_THRESHOLD:
        return "Low"
    return "Medium"


def _vol_callout(regime: str, vol_pct: float, symbol: str) -> str:
    """
    Build a user-facing volatility callout string.

    Parameters:
        regime (str): Volatility regime ("High" / "Medium" / "Low" / "Unknown").
        vol_pct (float): Annualised conditional volatility percentage.
        symbol (str): Stock symbol for context.

    Returns:
        str: Emoji-prefixed one-line description with trading implication.

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> _vol_callout("High", 42.3, "SUZLON")
        '🔴 SUZLON: High Vol 42.30% — tighten stops, consider reduced size'
    """
    vol_str = f"{vol_pct:.2f}%" if np.isfinite(vol_pct) else "N/A"
    if regime == "High":
        return (
            f"🔴 {symbol}: High Vol {vol_str} " "— tighten stops, consider reduced size"
        )
    if regime == "Low":
        return f"🟢 {symbol}: Low Vol {vol_str} — range-bound / accumulation"
    if regime == "Medium":
        return (
            f"🟡 {symbol}: Medium Vol {vol_str} " "— normal conditions, standard sizing"
        )
    return f"⚫ {symbol}: Vol regime unknown — insufficient data"


def _load_returns(symbol: str, daily_dir: str) -> pd.Series | None:
    """
    Load daily log-returns for a symbol from its 1d parquet file.

    Parameters:
        symbol (str): NSE stock symbol without suffix.
        daily_dir (str): Path to the directory containing parquet files.

    Returns:
        pd.Series | None: Log-return series sorted by date, or None on failure.

    Raises:
        None

    Complexity:
        Time: O(N)
        Space: O(N)

    Example:
        >>> rets = _load_returns("RELIANCE", "data/historical/1d")
        >>> print(rets.tail(3))
    """
    path = os.path.join(daily_dir, f"{symbol.upper()}.parquet")
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_parquet(path)
        if df.empty or "Close" not in df.columns:
            return None
        close = df["Close"].sort_index().dropna()
        log_returns = np.log(close / close.shift(1)).dropna()
        return log_returns
    except Exception as exc:
        LOGGER.debug("VolRegime: Failed reading %s: %s", path, exc)
        return None


def add_volatility_regime(
    df: pd.DataFrame,
    daily_dir: str,
    symbol_col: str = "SYMBOL",
    min_obs: int = _MIN_OBS,
) -> pd.DataFrame:
    """
    Append GARCH(1,1) volatility regime columns to the screener DataFrame.

    Reads each stock's historical daily returns from parquet, fits a GARCH(1,1)
    model, and classifies the resulting conditional volatility into a named regime.
    Stocks with insufficient data receive NaN vol and "Unknown" regime.

    Parameters:
        df (pd.DataFrame): Analyzed screener DataFrame with a symbol column.
        daily_dir (str): Path to directory containing 1d parquet files.
        symbol_col (str): Column name for NSE symbols. | Default: "SYMBOL"
        min_obs (int): Minimum observations required to fit GARCH. | Default: 60

    Returns:
        pd.DataFrame: Copy of input with three new columns:
            - GARCH_VOL_PCT (float): Annualised conditional volatility (%).
            - VOL_REGIME (str): "High" / "Medium" / "Low" / "Unknown".
            - VOL_CALLOUT (str): Trading implication one-liner.

    Raises:
        KeyError: If symbol_col is not present in df.columns.

    Complexity:
        Time: O(N x W) where N = stocks, W = GARCH convergence + parquet rows
        Space: O(N) [Three new Series]

    Example:
        >>> df = pd.read_csv("data/historical/top_250_analyzed_20260527.csv")
        >>> enriched = add_volatility_regime(df, "data/historical/1d")
        >>> print(enriched[["SYMBOL", "GARCH_VOL_PCT", "VOL_REGIME"]].head())
    """
    if symbol_col not in df.columns:
        raise KeyError(
            f"Symbol column '{symbol_col}' not found. "
            f"Available: {df.columns.tolist()}"
        )

    df = df.copy()
    vol_vals: list[float] = []
    regime_vals: list[str] = []
    callout_vals: list[str] = []

    computed = 0
    for _, row in df.iterrows():
        sym = str(row[symbol_col]).strip().upper()
        returns = _load_returns(sym, daily_dir)

        garch_vol = float("nan")
        regime = "Unknown"

        if returns is not None and len(returns) >= min_obs:
            garch_vol = fit_garch_vol(returns)
            regime = classify_vol_regime(garch_vol)
            if np.isfinite(garch_vol):
                computed += 1

        vol_vals.append(garch_vol)
        regime_vals.append(regime)
        callout_vals.append(_vol_callout(regime, garch_vol, sym))

    df["GARCH_VOL_PCT"] = vol_vals
    df["VOL_REGIME"] = regime_vals
    df["VOL_CALLOUT"] = callout_vals

    high = regime_vals.count("High")
    med = regime_vals.count("Medium")
    low = regime_vals.count("Low")
    LOGGER.info(
        "VolRegime: %d/%d fitted | High=%d Medium=%d Low=%d.",
        computed,
        len(df),
        high,
        med,
        low,
    )
    return df
