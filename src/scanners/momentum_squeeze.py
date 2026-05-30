"""
File: src/nse_bhavcopy/momentum_squeeze.py
Purpose: Calculates the Momentum Squeeze Indicator using Bollinger and Keltner Channels.
Last Modified: 2026-05-27
"""

import numpy as np
import pandas as pd
import yfinance as yf


def _rolling_linreg(series: pd.Series, length: int) -> pd.Series:
    """
    Replicates TradingView's linreg(series, length, 0) function.

    Parameters:
        series (pd.Series): The input data series.
        length (int): The lookback window for the regression.

    Returns:
        pd.Series: Series of rolling linear regression end-point values.
    """
    x = np.arange(length)

    def linreg_calc(y: np.ndarray) -> float:
        """Calculate the linear regression endpoint for a window of values."""
        if np.any(np.isnan(y)):
            return np.nan
        slope, intercept = np.polyfit(x, y, 1)
        return float(intercept + slope * (length - 1))

    return series.rolling(length).apply(linreg_calc, raw=True)


def momentum_squeeze(
    symbol: str,
    interval: str = "1d",
    period: str = "6mo",
    bb_length: int = 20,
    kc_length: int = 20,
    kc_mult: float = 1.5,
) -> pd.DataFrame:
    """
    Calculates the Momentum Squeeze Indicator for a given symbol.

    Parameters:
        symbol (str): Yahoo Finance ticker symbol.
        interval (str): Candle interval (e.g., '1d', '1h', '5m').
        period (str): Lookback data period (e.g., '6mo', '1y').
        bb_length (int): Bollinger Band window length.
        kc_length (int): Keltner Channel window length.
        kc_mult (float): Keltner Channel multiplier.

    Returns:
        pd.DataFrame: DataFrame with Momentum, Squeeze state, and color signals.

    Raises:
        ValueError: If downloaded data is empty.
    """
    raw: pd.DataFrame = yf.download(
        symbol,
        interval=interval,
        period=period,
        progress=False,
        multi_level_index=False,
    )

    if raw.empty:
        raise ValueError(f"No data returned for symbol '{symbol}'.")

    raw.dropna(inplace=True)

    high = raw["High"].squeeze()
    low = raw["Low"].squeeze()
    close = raw["Close"].squeeze()

    # ── Bollinger Bands ─────────────────────────────────────────────────────
    basis = close.rolling(bb_length).mean()
    dev = kc_mult * close.rolling(bb_length).std()
    upper_bb = basis + dev
    lower_bb = basis - dev

    # ── Keltner Channels ────────────────────────────────────────────────────
    ma = close.rolling(kc_length).mean()

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    rangema = tr.rolling(kc_length).mean()
    upper_kc = ma + rangema * kc_mult
    lower_kc = ma - rangema * kc_mult

    # ── Squeeze Conditions ───────────────────────────────────────────────────
    sqz_on = (lower_bb > lower_kc) & (upper_bb < upper_kc)
    sqz_off = (lower_bb < lower_kc) & (upper_bb > upper_kc)
    no_sqz = (~sqz_on) & (~sqz_off)

    # ── Momentum Value ───────────────────────────────────────────────────────
    highest_high = high.rolling(kc_length).max()
    lowest_low = low.rolling(kc_length).min()

    mid1 = (highest_high + lowest_low) / 2
    mid2 = (mid1 + close.rolling(kc_length).mean()) / 2
    momentum_source = close - mid2

    val = _rolling_linreg(momentum_source, kc_length)
    val_prev = val.shift(1).fillna(0)

    # ── Bar / Signal Colors ──────────────────────────────────────────────────
    bcolor = np.where(
        val > 0,
        np.where(val > val_prev, "lime", "green"),
        np.where(val < val_prev, "red", "maroon"),
    )

    scolor = np.where(no_sqz, "blue", np.where(sqz_on, "black", "gray"))

    result = pd.DataFrame(
        {
            "Close": close,
            "Momentum": val,
            "SqueezeOn": sqz_on,
            "SqueezeOff": sqz_off,
            "NoSqueeze": no_sqz,
            "HistColor": bcolor,
            "ZeroLineColor": scolor,
        }
    )
    result.dropna(inplace=True)
    return result


from src.core.signal import Signal
from src.scanners.registry import register_scanner


@register_scanner
def run_squeeze_cli(
    symbol: str = "^NSEI",
    interval: str = "1d",
    period: str = "6mo",
) -> list[Signal]:
    """
    CLI wrapper to compute and return the latest Momentum Squeeze summary.

    Parameters:
        symbol (str): The symbol to analyse.
        interval (str): Candle interval (default daily).
        period (str): Data lookback period (default 6 months).

    Returns:
        list[Signal]: Signal objects for the last 10 periods.
    """
    try:
        result = momentum_squeeze(symbol, interval, period)
    except ValueError as e:
        print(f"  Error: {e}")
        return []

    if result.empty:
        return []

    tail = result.tail(10).copy()

    def _map_action(mom_color: str) -> int:
        if mom_color in ["lime", "green"]:
            return 1
        elif mom_color in ["red", "maroon"]:
            return -1
        return 0

    signals = []
    # Ensure index is datetime for timestamp
    if not isinstance(tail.index, pd.DatetimeIndex):
        try:
            tail.index = pd.to_datetime(tail.index)
        except Exception:
            pass

    from datetime import datetime

    for dt, row in tail.iterrows():
        mom = row["HistColor"]
        sqz_on = row["SqueezeOn"]
        sqz_off = row["SqueezeOff"]
        action = _map_action(mom)

        # Conviction: if squeeze is on, it's building up (0.5), if it's off it fired (1.0).
        # We also look at strong vs weak momentum for conviction.
        conviction = 1.0 if mom in ["lime", "red"] else 0.5

        sqz_str = "SQUEEZE" if sqz_on else ("release" if sqz_off else "---")
        direction_str = {
            "lime": "⬆ Strong Bullish",
            "green": "↑ Bullish",
            "red": "⬇ Strong Bearish",
            "maroon": "↓ Bearish",
        }.get(str(mom), "?")

        timestamp = dt if isinstance(dt, datetime) else datetime.now()

        sig = Signal(
            symbol=symbol,
            strategy_name="momentum_squeeze",
            action=action,
            conviction=conviction,
            timestamp=timestamp,
            meta={
                "close": row["Close"],
                "momentum": row["Momentum"],
                "squeeze_on": sqz_on,
                "raw_signal": f"{sqz_str} | {direction_str}",
            },
        )
        signals.append(sig)

    return signals
