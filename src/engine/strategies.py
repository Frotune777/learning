"""
File: src/engine/strategies.py
Purpose: Pure trading strategy signal calculators, extracted from StockScreener.
Last Modified: 2026-06-01
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency guards
# ---------------------------------------------------------------------------
try:
    import talib as _talib  # type: ignore[import-untyped]

    _HAS_TALIB = True
except ImportError:
    _HAS_TALIB = False

try:
    import advanced_ta as _ata  # type: ignore[import-untyped]

    _HAS_ATA = True
except ImportError:
    _HAS_ATA = False

try:
    from sklearn.neighbors import KNeighborsClassifier as _KNN  # type: ignore[import-untyped]
    from sklearn.preprocessing import MinMaxScaler as _Scaler  # type: ignore[import-untyped]

    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False


def calc_nifty_shop(rsi: float, cmp: float) -> dict[str, Any]:
    """
    Compute Nifty Shop (RSI ladder) strategy signal for a stock.

    Parameters:
        rsi (float): RSI-14 value. | May be NaN.
        cmp (float): Current market price. | May be NaN.

    Returns:
        dict[str, Any]: {'action': str, 'target': float, 'sl': float}

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> calc_nifty_shop(24.0, 100.0)
        {'action': 'Level 3 Buy', 'target': 106.28, 'sl': nan}
    """
    level = "No Action"
    target = cmp * 1.0628 if not pd.isna(cmp) else np.nan
    sl = np.nan
    if not pd.isna(rsi):
        if rsi < 25.0:
            level = "Level 3 Buy"
        elif rsi < 30.0:
            level = "Level 2 Buy"
        elif rsi < 35.0:
            level = "Level 1 Buy"
    return {"action": level, "target": target, "sl": sl}


def calc_buy_low_sell_high(cmp: float, low_200d: float, atr: float) -> dict[str, Any]:
    """
    Compute Buy Low Sell High (200D demand level) strategy signal.

    Parameters:
        cmp (float): Current market price. | May be NaN.
        low_200d (float): 200-day rolling low. | May be NaN.
        atr (float): ATR-14 value. | May be NaN.

    Returns:
        dict[str, Any]: {'action': str, 'target': float, 'sl': float}

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> calc_buy_low_sell_high(101.0, 100.0, 2.0)
        {'action': 'Buy on Support / Demand Level', 'target': 105.0, 'sl': 99.0}
    """
    action = "Hold"
    if not pd.isna(cmp) and not pd.isna(low_200d):
        diff = ((cmp - low_200d) / low_200d) * 100.0
        if diff <= 2.0:
            action = "Buy on Support / Demand Level"
    target = cmp + (2 * atr) if not pd.isna(atr) else np.nan
    sl = low_200d - (0.5 * atr) if not pd.isna(atr) else np.nan
    return {"action": action, "target": target, "sl": sl}


def calc_turtle_trading(
    cmp: float, high_55d: float, low_20d: float, atr: float
) -> dict[str, Any]:
    """
    Compute Turtle Trading (55-day breakout) strategy signal.

    Parameters:
        cmp (float): Current market price. | May be NaN.
        high_55d (float): 55-day rolling high. | May be NaN.
        low_20d (float): 20-day rolling low used as stop loss. | May be NaN.
        atr (float): ATR-14. | May be NaN.

    Returns:
        dict[str, Any]: {'action': str, 'target': float, 'sl': float}

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> calc_turtle_trading(101.0, 100.0, 90.0, 3.0)
        {'action': 'Buy (55D Breakout)', 'target': 110.0, 'sl': 90.0}
    """
    action = "No need to fresh start"
    if not pd.isna(cmp) and not pd.isna(high_55d):
        if cmp >= high_55d:
            action = "Buy (55D Breakout)"
    target = cmp + (3 * atr) if not pd.isna(atr) else np.nan
    sl = low_20d
    return {"action": action, "target": target, "sl": sl}


def calc_rdx(
    adx: float,
    plus_di: float,
    minus_di: float,
    rsi: float,
    atr: float,
    cmp: float,
) -> dict[str, Any]:
    """
    Compute RDX Indicator (ADX + DI crossover + RSI) strategy signal.

    Parameters:
        adx (float): ADX-14 value. | May be NaN.
        plus_di (float): +DI-14 value. | May be NaN.
        minus_di (float): -DI-14 value. | May be NaN.
        rsi (float): RSI-14 value. | May be NaN.
        atr (float): ATR-14 value. | May be NaN.
        cmp (float): Current market price. | May be NaN.

    Returns:
        dict[str, Any]: {'action': str, 'target': float, 'sl': float}

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> calc_rdx(30.0, 28.0, 20.0, 65.0, 2.0, 100.0)
        {'action': 'Explosive Buy', 'target': 104.0, 'sl': 97.0}
    """
    action = "Hold"
    if not any(pd.isna(v) for v in [adx, plus_di, minus_di, rsi]):
        if adx > 25.0 and plus_di > minus_di and rsi > 60.0:
            action = "Explosive Buy"
        elif adx > 25.0 and minus_di > plus_di and rsi < 40.0:
            action = "Explosive Sell"
    target = cmp + (2 * atr) if not pd.isna(atr) else np.nan
    sl = cmp - (1.5 * atr) if not pd.isna(atr) else np.nan
    return {"action": action, "target": target, "sl": sl}


def calc_100sma_breakout(
    cmp: float,
    prev_close: float,
    sma_100: float,
    prev_sma_100: float,
    low_6m: float,
    atr: float,
) -> dict[str, Any]:
    """
    Compute 100 SMA Breakout (institutional base breakout) strategy signal.

    Parameters:
        cmp (float): Current market price. | May be NaN.
        prev_close (float): Previous day close. | May be NaN.
        sma_100 (float): Current 100-day SMA. | May be NaN.
        prev_sma_100 (float): Previous day 100-day SMA. | May be NaN.
        low_6m (float): 126-day rolling low. | May be NaN.
        atr (float): ATR-14. | May be NaN.

    Returns:
        dict[str, Any]: {'action': str, 'target': float, 'sl': float}

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> calc_100sma_breakout(105.0, 99.0, 100.0, 101.0, 80.0, 3.0)
        {'action': 'Breakout Buy', 'target': 114.0, 'sl': 100.0}
    """
    action = "Hold"
    if not any(pd.isna(v) for v in [cmp, prev_close, sma_100, prev_sma_100, low_6m]):
        crossed = (prev_close <= prev_sma_100) and (cmp > sma_100)
        diff_from_low = ((cmp - low_6m) / low_6m) * 100.0
        if crossed and diff_from_low >= 20.0:
            action = "Breakout Buy"
    target = cmp + (3 * atr) if not pd.isna(atr) else np.nan
    sl = sma_100
    return {"action": action, "target": target, "sl": sl}


def calc_etf_shop(cmp: float, sma_20: float) -> dict[str, Any]:
    """
    Compute ETF Shop Method (20 DMA retracement) strategy signal.

    Parameters:
        cmp (float): Current market price. | May be NaN.
        sma_20 (float): 20-day SMA. | May be NaN.

    Returns:
        dict[str, Any]: {'action': str, 'diff_pct': float}

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> calc_etf_shop(97.0, 100.0)
        {'diff_pct': -3.0, 'action': 'Buy'}
    """
    diff_pct: float = np.nan
    action = "Hold"
    if not pd.isna(cmp) and not pd.isna(sma_20) and sma_20 > 0:
        diff_pct = ((cmp - sma_20) / sma_20) * 100.0
        if diff_pct < -2.0:
            action = "Buy"
    return {"diff_pct": diff_pct, "action": action}


def calc_super_bo(
    cmp: float,
    sma_50: float,
    sma_100: float,
    sma_150: float,
    sma_200: float,
    atr: float,
) -> dict[str, Any]:
    """
    Compute Super BO Stocks (recovery facing 200 SMA resistance) strategy signal.

    Parameters:
        cmp (float): Current market price. | May be NaN.
        sma_50 (float): 50-day SMA. | May be NaN.
        sma_100 (float): 100-day SMA. | May be NaN.
        sma_150 (float): 150-day SMA. | May be NaN.
        sma_200 (float): 200-day SMA. | May be NaN.
        atr (float): ATR-14. | May be NaN.

    Returns:
        dict[str, Any]: {'action': str, 'target': float, 'sl': float}

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> calc_super_bo(105.0, 102.0, 100.0, 98.0, 110.0, 2.0)
        {'action': 'Super BO Buy', 'target': 110.0, 'sl': 101.0}
    """
    action = "Hold"
    if not any(pd.isna(v) for v in [cmp, sma_50, sma_100, sma_150, sma_200]):
        if cmp > sma_50 and cmp > sma_100 and cmp > sma_150 and cmp < sma_200:
            action = "Super BO Buy"
    target = sma_200
    sl = cmp - (2 * atr) if not pd.isna(atr) else np.nan
    return {"action": action, "target": target, "sl": sl}


def calc_dmadma_reverse(
    cmp: float, sma_150: float, sma_200: float, atr: float
) -> dict[str, Any]:
    """
    Compute DMADMA Reverse (150 SMA breakout above 200 SMA) strategy signal.

    Parameters:
        cmp (float): Current market price. | May be NaN.
        sma_150 (float): 150-day SMA. | May be NaN.
        sma_200 (float): 200-day SMA. | May be NaN.
        atr (float): ATR-14. | May be NaN.

    Returns:
        dict[str, Any]: {'action': str, 'target': float, 'sl': float}

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> calc_dmadma_reverse(105.0, 98.0, 100.0, 2.0)
        {'action': '150 DMA Breakout | CMP > 200 DMA', 'target': 109.0, 'sl': 98.0}
    """
    action = "Hold"
    if not any(pd.isna(v) for v in [cmp, sma_150, sma_200]):
        if cmp > sma_200 and sma_200 > sma_150:
            diff = ((sma_200 - sma_150) / sma_150) * 100.0
            if diff > 0.0:
                action = "150 DMA Breakout | CMP > 200 DMA"
    target = cmp + (2 * atr) if not pd.isna(atr) else np.nan
    sl = sma_150
    return {"action": action, "target": target, "sl": sl}


def calc_dmadma_no_sl(cmp: float, sma_50: float, sma_200: float) -> dict[str, Any]:
    """
    Compute DMADMA No-SL (50 SMA golden cross above 200 SMA) strategy signal.

    Parameters:
        cmp (float): Current market price. | May be NaN.
        sma_50 (float): 50-day SMA. | May be NaN.
        sma_200 (float): 200-day SMA. | May be NaN.

    Returns:
        dict[str, Any]: {'action': str, 'target': float, 'sl': float}

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> calc_dmadma_no_sl(105.0, 103.0, 100.0)
        {'action': '50 DMA Breakout | CMP > 200 DMA', 'target': 111.594, 'sl': nan}
    """
    action = "Hold"
    if not any(pd.isna(v) for v in [cmp, sma_50, sma_200]):
        if cmp > sma_200 and cmp > sma_50:
            diff = ((sma_50 - sma_200) / sma_200) * 100.0
            if diff > 0.0:
                action = "50 DMA Breakout | CMP > 200 DMA"
    return {"action": action, "target": cmp * 1.0628, "sl": np.nan}


# ---------------------------------------------------------------------------
# New strategies ported from screeni-py
# ---------------------------------------------------------------------------


def calc_vcp(
    df: pd.DataFrame,
    lookback: int = 250,
    swing_window: int = 5,
) -> dict[str, Any]:
    """
    Compute Minervini Volatility Contraction Pattern (VCP) signal.

    Checks:
      1. Trend template: CMP > SMA-50 and CMP > SMA-200 (Stage 2 uptrend).
      2. Proximity: CMP >= 75% of 52-week high.
      3. Volatility contraction: Each successive swing-peak-to-trough leg is
         smaller than the previous (tightening), and the final leg < 10%.

    Parameters:
        df (pd.DataFrame): OHLCV history in chronological order (oldest→latest).
            Must contain 'Close', 'High', 'Low'. Optional 'SMA_50', 'SMA_200'.
        lookback (int): Minimum bars required. | 250
        swing_window (int): Rolling window for peak detection. | 5

    Returns:
        dict[str, Any]: {'action': str, 'reason': str}

    Complexity:
        Time: O(N)
        Space: O(N)

    Example:
        >>> calc_vcp(pd.DataFrame({'Close': [100]*260, 'High': [101]*260, 'Low': [99]*260}))
        {'action': 'No VCP', 'reason': 'Not enough price peaks found to detect contraction'}
    """
    if df is None or len(df) < lookback:
        reason = f"Insufficient data ({len(df) if df is not None else 0} < {lookback})"
        return {"action": "No VCP", "reason": reason}

    try:
        data = df.copy()

        # 1. Trend Filter
        current_price = float(data["Close"].iloc[-1])
        sma_50 = (
            float(data["SMA_50"].iloc[-1])
            if "SMA_50" in data.columns
            else float(data["Close"].rolling(50).mean().iloc[-1])
        )
        sma_200 = (
            float(data["SMA_200"].iloc[-1])
            if "SMA_200" in data.columns
            else float(data["Close"].rolling(200).mean().iloc[-1])
        )

        if pd.isna(sma_50) or pd.isna(sma_200):
            return {"action": "No VCP", "reason": "SMA data unavailable"}

        if current_price < sma_50 or current_price < sma_200:
            return {
                "action": "No VCP",
                "reason": "Price below SMA-50 or SMA-200 (Not in Stage 2 uptrend)",
            }

        # 2. Proximity to 52-Week High
        yearly_high = float(data["High"].tail(252).max())
        if current_price < 0.75 * yearly_high:
            return {
                "action": "No VCP",
                "reason": f"Price too far from 52W High ({current_price:.2f} < 75% of {yearly_high:.2f})",
            }

        # 3. Volatility Contraction (swing-based)
        data = data.copy()
        data["_Peak"] = data["High"].rolling(swing_window, center=True).max()
        peaks = data[data["High"] == data["_Peak"]].tail(4)

        if len(peaks) < 3:
            return {
                "action": "No VCP",
                "reason": "Not enough price peaks found to detect contraction",
            }

        legs: list[float] = []
        for i in range(len(peaks) - 1):
            start_idx = peaks.index[i]
            end_idx = peaks.index[i + 1]
            leg_data = data.loc[start_idx:end_idx]
            peak_val = float(peaks["High"].iloc[i])
            low_val = float(leg_data["Low"].min())
            if peak_val > 0:
                contraction = (peak_val - low_val) / peak_val * 100.0
                legs.append(contraction)

        if not legs:
            return {"action": "No VCP", "reason": "Could not compute contraction legs"}

        # VCP: each leg should be smaller than the previous (10% buffer allowed)
        is_tightening = all(
            legs[i + 1] <= legs[i] * 1.1 for i in range(len(legs) - 1)
        )

        legs_str = ", ".join(f"{leg:.1f}%" for leg in legs)
        if is_tightening and legs[-1] < 10.0:
            return {
                "action": "VCP Tightening",
                "reason": f"VCP Tightening Detected: Legs({legs_str})",
            }

        return {"action": "No VCP", "reason": f"No VCP (Legs: {legs_str})"}

    except Exception as exc:
        LOGGER.warning("VCP error: %s", exc)
        return {"action": "No VCP", "reason": f"VCP Error: {exc}"}


def calc_ttm_squeeze(
    df: pd.DataFrame,
    period: int = 20,
    bb_mult: float = 2.0,
    kc_mult: float = 1.5,
) -> dict[str, Any]:
    """
    Compute TTM Squeeze signal (Bollinger Bands inside Keltner Channels).

    A squeeze is active when BB upper < KC upper AND BB lower > KC lower.
    Momentum direction is derived from Close vs SMA-20.

    Parameters:
        df (pd.DataFrame): OHLCV history (chronological). Must contain 'Close'.
            Optional: 'High', 'Low', 'ATR_14'.
        period (int): Rolling period for BB and KC. | 20
        bb_mult (float): Bollinger Band standard-deviation multiplier. | 2.0
        kc_mult (float): Keltner Channel ATR multiplier. | 1.5

    Returns:
        dict[str, Any]: {'action': str, 'squeeze_active': bool, 'momentum': float}

    Complexity:
        Time: O(N)
        Space: O(N)

    Example:
        >>> calc_ttm_squeeze(pd.DataFrame({'Close': [100.0]*50}))
        {'action': 'No Squeeze', 'squeeze_active': False, 'momentum': 0.0}
    """
    min_bars = period + 14
    if df is None or len(df) < min_bars:
        return {
            "action": "Insufficient Data",
            "squeeze_active": False,
            "momentum": np.nan,
        }

    try:
        data = df.copy()
        close = data["Close"].astype(float)

        sma20 = close.rolling(period).mean()
        std20 = close.rolling(period).std()
        bb_upper = sma20 + (bb_mult * std20)
        bb_lower = sma20 - (bb_mult * std20)

        # Keltner Channels — use pre-computed ATR if available
        if "ATR_14" in data.columns:
            atr_series = data["ATR_14"].astype(float)
        elif "High" in data.columns and "Low" in data.columns:
            high = data["High"].astype(float)
            low = data["Low"].astype(float)
            high_low = high - low
            high_pc = (high - close.shift(1)).abs()
            low_pc = (low - close.shift(1)).abs()
            tr = pd.concat([high_low, high_pc, low_pc], axis=1).max(axis=1)
            atr_series = tr.rolling(period).mean()
        else:
            # Fallback: use std as ATR proxy
            atr_series = std20

        kc_upper = sma20 + (kc_mult * atr_series)
        kc_lower = sma20 - (kc_mult * atr_series)

        bb_u = float(bb_upper.iloc[-1])
        bb_l = float(bb_lower.iloc[-1])
        kc_u = float(kc_upper.iloc[-1])
        kc_l = float(kc_lower.iloc[-1])
        sma_last = float(sma20.iloc[-1])
        close_last = float(close.iloc[-1])

        if any(pd.isna(v) for v in [bb_u, bb_l, kc_u, kc_l]):
            return {
                "action": "Insufficient Data",
                "squeeze_active": False,
                "momentum": np.nan,
            }

        is_squeeze = (bb_u < kc_u) and (bb_l > kc_l)
        momentum = close_last - sma_last if not pd.isna(sma_last) else 0.0

        if is_squeeze:
            direction = "Bullish" if momentum > 0 else "Bearish"
            return {
                "action": f"Squeeze Active ({direction})",
                "squeeze_active": True,
                "momentum": momentum,
            }

        return {"action": "No Squeeze", "squeeze_active": False, "momentum": momentum}

    except Exception as exc:
        LOGGER.warning("TTM Squeeze error: %s", exc)
        return {
            "action": "Insufficient Data",
            "squeeze_active": False,
            "momentum": np.nan,
        }


def _supertrend_impl(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    atr_period: int,
    factor: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Standalone SuperTrend indicator (no backtesting.py dependency).

    Convention used (consistent with original screeni-py script):
        direction = -1  →  Uptrend  (Green / Long)
        direction =  1  →  Downtrend (Red / Short)

    Parameters:
        high, low, close (pd.Series): OHLC price series (chronological).
        atr_period (int): ATR smoothing period.
        factor (float): ATR multiplier for band width.

    Returns:
        tuple[np.ndarray, np.ndarray]: (supertrend_line, direction_array)
    """
    high = pd.Series(high.values)
    low = pd.Series(low.values)
    close = pd.Series(close.values)

    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
    ).max(axis=1)
    atr = tr.rolling(atr_period).mean().fillna(0)

    hl2 = (high + low) / 2.0
    upper = (hl2 + factor * atr).values
    lower = (hl2 - factor * atr).values
    close_arr = close.values
    n = len(close_arr)

    direction = np.ones(n, dtype=float)  # start as 1 (downtrend)
    st = np.zeros(n, dtype=float)

    for i in range(atr_period, n):
        if close_arr[i] > upper[i - 1]:
            direction[i] = -1  # Uptrend
        elif close_arr[i] < lower[i - 1]:
            direction[i] = 1  # Downtrend
        else:
            direction[i] = direction[i - 1]
            if direction[i] == -1:  # Uptrend — raise floor
                lower[i] = max(lower[i], lower[i - 1])
            else:  # Downtrend — lower ceiling
                upper[i] = min(upper[i], upper[i - 1])

        st[i] = lower[i] if direction[i] == -1 else upper[i]

    return st, direction


def calc_dual_supertrend(
    df: pd.DataFrame,
    buy_atr: int = 10,
    buy_factor: float = 3.0,
    sell_atr: int = 10,
    sell_factor: float = 3.0,
) -> dict[str, Any]:
    """
    Compute Dual SuperTrend crossover signal.

    A Long Entry is signalled when the buy SuperTrend flips from downtrend (1)
    to uptrend (-1) on the most recent bar. A Close signal fires when the sell
    SuperTrend flips from uptrend (-1) to downtrend (1).

    Parameters:
        df (pd.DataFrame): OHLCV history (chronological). Requires 'High', 'Low', 'Close'.
        buy_atr (int): ATR period for the buy SuperTrend. | 10
        buy_factor (float): ATR multiplier for buy SuperTrend. | 3.0
        sell_atr (int): ATR period for the sell SuperTrend. | 10
        sell_factor (float): ATR multiplier for sell SuperTrend. | 3.0

    Returns:
        dict[str, Any]: {'action': str, 'buy_dir': float, 'sell_dir': float}

    Complexity:
        Time: O(N)
        Space: O(N)

    Example:
        >>> calc_dual_supertrend(pd.DataFrame({'High': [105.0]*30, 'Low': [95.0]*30, 'Close': [100.0]*30}))
        {'action': 'Hold', 'buy_dir': 1.0, 'sell_dir': 1.0}
    """
    min_bars = max(buy_atr, sell_atr) + 2
    if df is None or len(df) < min_bars or not all(
        c in df.columns for c in ("High", "Low", "Close")
    ):
        return {"action": "Insufficient Data", "buy_dir": np.nan, "sell_dir": np.nan}

    try:
        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        close = df["Close"].astype(float)

        _, buy_dir = _supertrend_impl(high, low, close, buy_atr, buy_factor)
        _, sell_dir = _supertrend_impl(high, low, close, sell_atr, sell_factor)

        curr_buy = buy_dir[-1]
        prev_buy = buy_dir[-2]
        curr_sell = sell_dir[-1]
        prev_sell = sell_dir[-2]

        if curr_buy == -1 and prev_buy == 1:
            action = "Long Entry"
        elif curr_sell == 1 and prev_sell == -1:
            action = "Close Long"
        else:
            action = "Hold"

        return {"action": action, "buy_dir": curr_buy, "sell_dir": curr_sell}

    except Exception as exc:
        LOGGER.warning("Dual Supertrend error: %s", exc)
        return {"action": "Insufficient Data", "buy_dir": np.nan, "sell_dir": np.nan}


def calc_candle_patterns(df: pd.DataFrame) -> dict[str, Any]:
    """
    Detect standard candlestick patterns on the latest bar using TA-Lib.

    Patterns checked: Doji, Bullish/Bearish Engulfing, Hammer,
    Shooting Star, Morning Star.

    Parameters:
        df (pd.DataFrame): OHLCV history (chronological).
            Requires 'Open', 'High', 'Low', 'Close'.

    Returns:
        dict[str, Any]: {'action': str, 'pattern': str}
            action is 'Pattern Detected' when a pattern is found, else 'None'.

    Complexity:
        Time: O(N)
        Space: O(N)

    Example:
        >>> calc_candle_patterns(pd.DataFrame({'Open': [100.0]*5, 'High': [101.0]*5, 'Low': [99.0]*5, 'Close': [100.0]*5}))
        {'action': 'None', 'pattern': 'None'}
    """
    required = {"Open", "High", "Low", "Close"}
    if not _HAS_TALIB:
        return {"action": "TA-Lib Unavailable", "pattern": "None"}
    if df is None or df.empty or not required.issubset(df.columns):
        return {"action": "None", "pattern": "None"}

    try:
        op = df["Open"].astype("float64").to_numpy()
        hi = df["High"].astype("float64").to_numpy()
        lo = df["Low"].astype("float64").to_numpy()
        cl = df["Close"].astype("float64").to_numpy()

        idx = -1
        patterns: list[str] = []

        if _talib.CDLDOJI(op, hi, lo, cl)[idx] != 0:
            patterns.append("Doji")
        engulfing = _talib.CDLENGULFING(op, hi, lo, cl)[idx]
        if engulfing == 100:
            patterns.append("Bullish Engulfing")
        elif engulfing == -100:
            patterns.append("Bearish Engulfing")
        if _talib.CDLHAMMER(op, hi, lo, cl)[idx] != 0:
            patterns.append("Hammer")
        if _talib.CDLSHOOTINGSTAR(op, hi, lo, cl)[idx] != 0:
            patterns.append("Shooting Star")
        if _talib.CDLMORNINGSTAR(op, hi, lo, cl)[idx] != 0:
            patterns.append("Morning Star")

        if patterns:
            pat_str = ", ".join(patterns)
            return {"action": "Pattern Detected", "pattern": pat_str}

        return {"action": "None", "pattern": "None"}

    except Exception as exc:
        LOGGER.warning("Candle patterns error: %s", exc)
        return {"action": "None", "pattern": "None"}


def calc_lorentzian(df: pd.DataFrame) -> dict[str, Any]:
    """
    Compute Lorentzian Classification signal.

    Strategy A (preferred): Uses the ``advanced_ta`` library's
    ``LorentzianClassification`` with features RSI-14, WaveTrend, CCI-20,
    ADX-20, RSI-9, and MFI-14.

    Strategy B (fallback): When ``advanced_ta`` is unavailable, trains a
    sklearn KNN classifier (neighbours=8) with a Lorentzian distance metric
    (Manhattan / L1 as proxy) on RSI, ADX, CCI, MACD-Hist features derived
    from the DataFrame columns populated by ``add_ta_indicators``.

    Parameters:
        df (pd.DataFrame): OHLCV + TA-enriched history (chronological).
            Minimum 50 bars. For Strategy A: Open/High/Low/Close/Volume.
            For Strategy B: RSI_14, ADX_14, CCI_14, MACD_HIST.

    Returns:
        dict[str, Any]: {'action': str, 'confidence': str}

    Complexity:
        Time: O(N·k) — KNN training dominates.
        Space: O(N)

    Example:
        >>> calc_lorentzian(pd.DataFrame({'Close': [100.0]*50}))
        {'action': 'No Signal', 'confidence': 'Low'}
    """
    if df is None or len(df) < 50:
        return {"action": "No Signal", "confidence": "Insufficient Data"}

    # --- Strategy A: advanced_ta LorentzianClassification ---
    if _HAS_ATA:
        try:
            import talib as talib_  # noqa: PLC0415  (local import inside guard)

            data = df.copy().rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )
            features = [
                _ata.LorentzianClassification.Feature("RSI", 14, 2),
                _ata.LorentzianClassification.Feature("WT", 10, 11),
                _ata.LorentzianClassification.Feature("CCI", 20, 2),
                _ata.LorentzianClassification.Feature("ADX", 20, 2),
                _ata.LorentzianClassification.Feature("RSI", 9, 2),
                talib_.MFI(
                    data["high"].astype(float),
                    data["low"].astype(float),
                    data["close"].astype(float),
                    data["volume"].astype(float),
                    14,
                ),
            ]
            lc = _ata.LorentzianClassification(
                data=data,
                features=features,
                settings=_ata.LorentzianClassification.Settings(
                    source=data["close"],
                    neighborsCount=8,
                    maxBarsBack=2000,
                    useDynamicExits=False,
                ),
                filterSettings=_ata.LorentzianClassification.FilterSettings(
                    useVolatilityFilter=True,
                    useRegimeFilter=True,
                    useAdxFilter=False,
                    regimeThreshold=-0.1,
                    adxThreshold=20,
                    kernelFilter=_ata.LorentzianClassification.KernelFilter(
                        useKernelSmoothing=False,
                        lookbackWindow=8,
                        relativeWeight=8.0,
                        regressionLevel=25,
                        crossoverLag=2,
                    ),
                ),
            )
            latest = lc.df.iloc[-1]
            if latest["isNewBuySignal"]:
                return {"action": "Lorentzian Buy", "confidence": "High"}
            elif latest["isNewSellSignal"]:
                return {"action": "Lorentzian Sell", "confidence": "High"}
            return {"action": "No Signal", "confidence": "Neutral"}

        except Exception as exc:
            LOGGER.debug("advanced_ta Lorentzian error, falling back: %s", exc)

    # --- Strategy B: sklearn KNN fallback ---
    if not _HAS_SKLEARN:
        return {"action": "No Signal", "confidence": "Library Unavailable"}

    feature_cols = ["RSI_14", "ADX_14", "CCI_14", "MACD_HIST"]
    available = [c for c in feature_cols if c in df.columns]
    if len(available) < 3:
        return {"action": "No Signal", "confidence": "Insufficient Indicators"}

    try:
        data = df[available].copy()
        # Target: 1 if next close > current close
        close_series = df["Close"].astype(float)
        data = data.copy()
        data["_target"] = (close_series.shift(-1) > close_series).astype(int)
        valid = data.dropna()

        if len(valid) < 20:
            return {"action": "No Signal", "confidence": "Insufficient Data"}

        X = valid[available].values
        y = valid["_target"].values

        lookback = 2000
        if len(X) > lookback:
            X = X[-lookback:]
            y = y[-lookback:]

        # Most recent complete row for prediction
        latest_features = valid[available].iloc[-1].values.reshape(1, -1)
        if np.isnan(latest_features).any():
            return {"action": "No Signal", "confidence": "NaN Features"}

        scaler = _Scaler()
        X_scaled = scaler.fit_transform(X)
        latest_scaled = scaler.transform(latest_features)

        clf = _KNN(n_neighbors=8, metric="manhattan", weights="distance")
        clf.fit(X_scaled, y)
        prediction = int(clf.predict(latest_scaled)[0])

        if prediction == 1:
            return {"action": "Lorentzian Buy", "confidence": "Medium (sklearn)"}
        return {"action": "No Signal", "confidence": "Medium (sklearn)"}

    except Exception as exc:
        LOGGER.warning("Lorentzian sklearn fallback error: %s", exc)
        return {"action": "No Signal", "confidence": "Error"}

