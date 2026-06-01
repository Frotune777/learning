"""
File: src/nse_bhavcopy/ta_indicators.py
Purpose: Compute technical analysis indicators using TA-Lib and generate unified scores.
Last Modified: 2026-05-27
"""

import logging
from typing import Any

import pandas as pd
import talib

LOGGER: logging.Logger = logging.getLogger(__name__)


def add_ta_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate advanced technical indicators using TA-Lib on the input DataFrame.

    Parameters:
        df (pd.DataFrame): DataFrame containing Open, High, Low, Close, Volume.

    Returns:
        pd.DataFrame: Original DataFrame enriched with TA-Lib indicator columns.

    Raises:
        None

    Complexity:
        Time: O(N) [TA-Lib computations are O(N) in C]
        Space: O(N) [Temporary indicator column allocations]

    Example:
        >>> df = pd.DataFrame({"Close": [100.0] * 50})
        >>> res = add_ta_indicators(df)
    """
    if df.empty:
        return df

    # Work on a copy to avoid mutating original
    df = df.copy()

    # We need a DatetimeIndex or at least sorted index
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    # Convert columns to float64 for TA-Lib
    close = df["Close"].astype("float64")

    # Add RSI (14)
    df["RSI_14"] = pd.Series(talib.RSI(close, timeperiod=14), index=df.index)

    # Add MACD
    macd, macdsignal, macdhist = talib.MACD(
        close, fastperiod=12, slowperiod=26, signalperiod=9
    )
    df["MACD"] = pd.Series(macd, index=df.index)
    df["MACD_SIGNAL"] = pd.Series(macdsignal, index=df.index)
    df["MACD_HIST"] = pd.Series(macdhist, index=df.index)

    # Add Bollinger Bands
    upper, middle, lower = talib.BBANDS(
        close,
        timeperiod=20,
        nbdevup=2.0,
        nbdevdn=2.0,
        matype=talib.MA_Type.SMA,  # type: ignore[attr-defined]
    )
    df["BB_UPPER"] = pd.Series(upper, index=df.index)
    df["BB_MIDDLE"] = pd.Series(middle, index=df.index)
    df["BB_LOWER"] = pd.Series(lower, index=df.index)

    # Add EMAs
    df["EMA_20"] = pd.Series(talib.EMA(close, timeperiod=20), index=df.index)
    df["EMA_50"] = pd.Series(talib.EMA(close, timeperiod=50), index=df.index)
    df["EMA_100"] = pd.Series(talib.EMA(close, timeperiod=100), index=df.index)
    df["EMA_200"] = pd.Series(talib.EMA(close, timeperiod=200), index=df.index)

    # Add SMAs
    df["SMA_20"] = pd.Series(talib.SMA(close, timeperiod=20), index=df.index)
    df["SMA_50"] = pd.Series(talib.SMA(close, timeperiod=50), index=df.index)
    df["SMA_100"] = pd.Series(talib.SMA(close, timeperiod=100), index=df.index)
    df["SMA_150"] = pd.Series(talib.SMA(close, timeperiod=150), index=df.index)
    df["SMA_200"] = pd.Series(talib.SMA(close, timeperiod=200), index=df.index)

    # Add High/Low-dependent indicators if available
    if "High" in df.columns and "Low" in df.columns:
        high = df["High"].astype("float64")
        low = df["Low"].astype("float64")

        df["ATR_14"] = pd.Series(
            talib.ATR(high, low, close, timeperiod=14), index=df.index
        )
        df["ADX_14"] = pd.Series(
            talib.ADX(high, low, close, timeperiod=14), index=df.index
        )
        df["PLUS_DI_14"] = pd.Series(
            talib.PLUS_DI(high, low, close, timeperiod=14), index=df.index
        )
        df["MINUS_DI_14"] = pd.Series(
            talib.MINUS_DI(high, low, close, timeperiod=14), index=df.index
        )
        df["CCI_14"] = pd.Series(
            talib.CCI(high, low, close, timeperiod=14), index=df.index
        )

        # Rolling High/Low Metrics
        df["20D_LOW"] = pd.Series(low.rolling(window=20).min(), index=df.index)
        df["126D_LOW"] = pd.Series(low.rolling(window=126).min(), index=df.index)
        df["200D_LOW"] = pd.Series(low.rolling(window=200).min(), index=df.index)
        df["55D_HIGH"] = pd.Series(high.rolling(window=55).max(), index=df.index)
        df["52W_HIGH"] = pd.Series(high.rolling(window=252).max(), index=df.index)
        df["52W_LOW"] = pd.Series(low.rolling(window=252).min(), index=df.index)

    # Add RSI and MACD Divergences
    df["RSI_Divergence"] = "None"
    df["MACD_Divergence"] = "None"

    lookback = 20
    if len(df) >= lookback:
        try:
            # RSI Divergence detection
            if "RSI_14" in df.columns:
                recent = df.tail(lookback)
                prices = recent["Close"].to_numpy(dtype=float)
                rsi_vals = recent["RSI_14"].to_numpy(dtype=float)
                
                p_min_idx = prices.argmin()
                p_max_idx = prices.argmax()
                
                if p_min_idx > lookback // 2:
                    prev_p = prices[:p_min_idx]
                    prev_rsi = rsi_vals[:p_min_idx]
                    if len(prev_p) > 0:
                        prev_min_idx = prev_p.argmin()
                        if prices[p_min_idx] < prev_p[prev_min_idx] and rsi_vals[p_min_idx] > prev_rsi[prev_min_idx]:
                            df.loc[df.index[-1], "RSI_Divergence"] = "Bullish"
                            
                if p_max_idx > lookback // 2:
                    prev_p = prices[:p_max_idx]
                    prev_rsi = rsi_vals[:p_max_idx]
                    if len(prev_p) > 0:
                        prev_max_idx = prev_p.argmax()
                        if prices[p_max_idx] > prev_p[prev_max_idx] and rsi_vals[p_max_idx] < prev_rsi[prev_max_idx]:
                            df.loc[df.index[-1], "RSI_Divergence"] = "Bearish"

            # MACD Divergence detection
            if "MACD_HIST" in df.columns:
                recent = df.tail(lookback)
                prices = recent["Close"].to_numpy(dtype=float)
                macd_hist = recent["MACD_HIST"].to_numpy(dtype=float)
                
                p_min_idx = prices.argmin()
                p_max_idx = prices.argmax()
                
                if p_min_idx > lookback // 2:
                    prev_p = prices[:p_min_idx]
                    prev_macd = macd_hist[:p_min_idx]
                    if len(prev_p) > 0:
                        prev_min_idx = prev_p.argmin()
                        if prices[p_min_idx] < prev_p[prev_min_idx] and macd_hist[p_min_idx] > prev_macd[prev_min_idx]:
                            df.loc[df.index[-1], "MACD_Divergence"] = "Bullish"
                            
                if p_max_idx > lookback // 2:
                    prev_p = prices[:p_max_idx]
                    prev_macd = macd_hist[:p_max_idx]
                    if len(prev_p) > 0:
                        prev_max_idx = prev_p.argmax()
                        if prices[p_max_idx] > prev_p[prev_max_idx] and macd_hist[p_max_idx] < prev_macd[prev_max_idx]:
                            df.loc[df.index[-1], "MACD_Divergence"] = "Bearish"
        except Exception as e:
            LOGGER.warning("Error calculating divergences: %s", e)

    return df


def calculate_technical_score(row: pd.Series) -> dict[str, Any]:
    """
    Calculate a unified technical score (0-100) and rating for a single stock row.

    Parameters:
        row (pd.Series): A Series (typically latest row) containing computed TA columns.

    Returns:
        dict[str, Any]: Dictionary containing 'score' (0-100) and 'rating' (str).

    Raises:
        None

    Complexity:
        Time: O(1) [Direct condition evaluations]
        Space: O(1) [Fixed output size]

    Example:
        >>> s = pd.Series({"Close": 150.0, "RSI_14": 55.0})
        >>> calculate_technical_score(s)
        {'score': 25, 'rating': 'SELL'}
    """
    # Initialize score out of 100
    score = 0

    # Ensure required columns are present and not NaN
    close = float(row.get("Close", 0.0))
    ema_20 = row.get("EMA_20")
    sma_50 = row.get("SMA_50")
    sma_200 = row.get("SMA_200")
    rsi = row.get("RSI_14")
    macd = row.get("MACD")
    macd_signal = row.get("MACD_SIGNAL")
    bb_upper = row.get("BB_UPPER")
    bb_middle = row.get("BB_MIDDLE")
    bb_lower = row.get("BB_LOWER")
    adx = row.get("ADX_14")

    # 1. Trend Analysis (Max 35 points)
    if not pd.isna(close) and not pd.isna(ema_20) and close > float(ema_20):
        score += 5
    if not pd.isna(close) and not pd.isna(sma_50) and close > float(sma_50):
        score += 10
    if not pd.isna(close) and not pd.isna(sma_200) and close > float(sma_200):
        score += 10
    if not pd.isna(ema_20) and not pd.isna(sma_50) and float(ema_20) > float(sma_50):
        score += 5
    if not pd.isna(sma_50) and not pd.isna(sma_200) and float(sma_50) > float(sma_200):
        score += 5

    # 2. RSI Momentum (Max 25 points)
    if not pd.isna(rsi):
        rsi_val = float(rsi)
        if 50.0 <= rsi_val <= 70.0:
            score += 25  # Healthy bullish momentum
        elif 40.0 <= rsi_val < 50.0:
            score += 15  # Neutral/positive
        elif 30.0 <= rsi_val < 40.0:
            score += 5  # Weak bearish momentum
        elif rsi_val > 70.0:
            score += 10  # Overbought (strong trend but warning)
        else:
            score += 0  # Oversold (<30) - bearish unless bouncing

    # 3. MACD Crossover (Max 20 points)
    if (
        not pd.isna(macd)
        and not pd.isna(macd_signal)
        and float(macd) > float(macd_signal)
    ):
        score += 20

    # 4. Bollinger Bands (Max 10 points)
    if not pd.isna(bb_middle) and not pd.isna(bb_upper) and not pd.isna(bb_lower):
        bb_mid_val = float(bb_middle)
        bb_up_val = float(bb_upper)
        bb_low_val = float(bb_lower)
        if bb_mid_val <= close <= bb_up_val:
            score += 10  # Trading in upper channel
        elif bb_low_val <= close < bb_mid_val:
            score += 5  # Trading in lower channel
        elif close > bb_up_val:
            score += 8  # Breakout (strong but stretched)

    # 5. Trend Strength / ADX (Max 10 points)
    if not pd.isna(adx):
        adx_val = float(adx)
        is_uptrend = not pd.isna(sma_50) and close > float(sma_50)
        if adx_val > 25.0:
            if is_uptrend:
                score += 10  # Strong bullish trend
            else:
                score += 0  # Strong bearish trend
        else:
            score += 5  # Sideways/weak trend

    # Determine Rating Category
    if score >= 80:
        rating = "STRONG BUY"
    elif score >= 60:
        rating = "BUY"
    elif score >= 40:
        rating = "NEUTRAL"
    elif score >= 20:
        rating = "SELL"
    else:
        rating = "STRONG SELL"

    return {"score": score, "rating": rating}
