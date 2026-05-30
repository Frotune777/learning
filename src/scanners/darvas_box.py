"""
File: src/nse_bhavcopy/darvas_box.py
Purpose: Detect Darvas Box consolidation patterns and volume-confirmed breakouts.
Last Modified: 2026-05-29
"""

import logging
import os

import numpy as np
import pandas as pd

LOGGER: logging.Logger = logging.getLogger(__name__)

# Minimum sessions a stock must consolidate to form a valid box
MIN_BOX_DAYS: int = 5

# Volume spike multiplier required for a confirmed breakout
VOL_SPIKE_MULTIPLIER: float = 1.5

# Rolling window for box definition (4 weeks ~ 20 sessions)
BOX_WINDOW: int = 20

# Volume averaging window
VOL_AVG_WINDOW: int = 20


def detect_darvas_box(
    df: pd.DataFrame,
    box_window: int = BOX_WINDOW,
    min_box_days: int = MIN_BOX_DAYS,
    vol_spike_mult: float = VOL_SPIKE_MULTIPLIER,
) -> dict[str, object]:
    """
    Detect a Darvas Box pattern on a single stock OHLCV DataFrame.

    Uses a rolling-window variant: the box is defined by the 20-day
    rolling high (box_high) and 10-day rolling low (box_low) when the
    stock has been consolidating for at least min_box_days sessions
    (i.e., not making new 20-day highs).  Breakout is confirmed when
    today's close exceeds box_high with volume > vol_spike_mult x 20D avg.

    Parameters:
        df (pd.DataFrame): OHLCV DataFrame with columns: Open, High, Low,
            Close, Volume. Index may be DatetimeIndex. | min 25 rows.
        box_window (int): Rolling window for box_high calculation. |
            Default: 20 (4 trading weeks).
        min_box_days (int): Minimum consolidation sessions for valid box. |
            Default: 5.
        vol_spike_mult (float): Volume multiplier required for confirmation. |
            Default: 1.5x 20D average.

    Returns:
        dict[str, object]: Keys:
            'box_high' (float | nan): Top of current Darvas Box.
            'box_low' (float | nan): Bottom of current Darvas Box.
            'box_days' (int): Sessions in current consolidation phase.
            'breakout' (bool): True if today's close > box_high with vol conf.
            'breakdown' (bool): True if today's close < box_low with vol conf.
            'vol_confirmed' (bool): True if volume > vol_spike_mult x 20D avg.
            'signal' (str): Human-readable label.

    Complexity:
        Time: O(N) where N = len(df)
        Space: O(N)

    Example:
        >>> result = detect_darvas_box(df_ohlcv)
        >>> result['signal']
        'Breakout (Volume Confirmed)'
    """
    _empty = {
        "box_high": np.nan,
        "box_low": np.nan,
        "box_days": 0,
        "breakout": False,
        "breakdown": False,
        "vol_confirmed": False,
        "signal": "Insufficient Data",
    }

    required = {"High", "Low", "Close", "Volume"}
    if not required.issubset(df.columns):
        LOGGER.debug("Darvas: missing columns %s", required - set(df.columns))
        return _empty

    if len(df) < box_window + min_box_days:
        return _empty

    df = df.copy()
    half_window = max(box_window // 2, 5)

    df["_roll_high"] = df["High"].rolling(window=box_window).max()
    df["_roll_low"] = df["Low"].rolling(window=half_window).min()
    df["_vol_avg"] = df["Volume"].rolling(window=VOL_AVG_WINDOW).mean()

    # Count consecutive sessions where no new N-period high was made
    # (i.e. today's high <= rolling_high from box_window bars ago)
    df["_is_consolidating"] = df["High"] <= df["_roll_high"].shift(1)
    consol_streak_today = _count_trailing_true(df["_is_consolidating"])
    consol_streak_yesterday = _count_trailing_true(df["_is_consolidating"].iloc[:-1])

    latest = df.iloc[-1]
    prev_latest = df.iloc[-2] if len(df) > 1 else latest

    box_high = float(prev_latest.get("_roll_high", np.nan))
    box_low = float(latest.get("_roll_low", np.nan))
    vol_avg = float(latest.get("_vol_avg", np.nan))
    today_close = float(latest["Close"])
    today_vol = float(latest["Volume"])

    vol_confirmed = (
        not pd.isna(vol_avg) and vol_avg > 0 and today_vol >= vol_spike_mult * vol_avg
    )

    is_valid_box_breakout = consol_streak_yesterday >= min_box_days
    is_valid_box_today = consol_streak_today >= min_box_days

    breakout = (
        is_valid_box_breakout
        and not pd.isna(box_high)
        and today_close > box_high
        and vol_confirmed
    )
    breakdown = (
        is_valid_box_breakout
        and not pd.isna(box_low)
        and today_close < box_low
        and vol_confirmed
    )

    if breakout:
        signal = "Breakout (Volume Confirmed)"
        display_streak = consol_streak_yesterday
    elif breakdown:
        signal = "Breakdown (Volume Confirmed)"
        display_streak = consol_streak_yesterday
    elif is_valid_box_breakout and not pd.isna(box_high) and today_close > box_high:
        signal = "Breakout (No Volume Confirmation)"
        display_streak = consol_streak_yesterday
    elif is_valid_box_today:
        signal = f"Consolidating ({consol_streak_today} days)"
        display_streak = consol_streak_today
    else:
        signal = "No Pattern"
        display_streak = consol_streak_today

    return {
        "box_high": box_high,
        "box_low": box_low,
        "box_days": display_streak,
        "breakout": breakout,
        "breakdown": breakdown,
        "vol_confirmed": vol_confirmed,
        "signal": signal,
    }


def _count_trailing_true(series: pd.Series) -> int:
    """
    Count the number of consecutive True values at the end of a boolean Series.

    Parameters:
        series (pd.Series): Boolean Series. | Non-empty.

    Returns:
        int: Count of trailing True values. Returns 0 if last value is False.

    Complexity:
        Time: O(N)  Space: O(1)

    Example:
        >>> _count_trailing_true(pd.Series([True, False, True, True, True]))
        3
    """
    count = 0
    for val in reversed(series.tolist()):
        if val is True or val is np.bool_(True):
            count += 1
        else:
            break
    return count


def scan_darvas_breakouts(
    analyzed_df: pd.DataFrame,
    daily_dir: str = "data/historical/1d",
    output_dir: str = "data/signals",
    date_str: str = "",
) -> pd.DataFrame:
    """
    Run Darvas Box detection across all symbols in the analyzed DataFrame.

    Loads each symbol's Parquet history, runs detect_darvas_box(), and
    collects confirmed breakout/breakdown signals into a summary DataFrame.

    Parameters:
        analyzed_df (pd.DataFrame): Analyzed screener DataFrame. |
            Must contain a SYMBOL column.
        daily_dir (str): Directory containing per-symbol Parquet files. |
            Default: 'data/historical/1d'.
        output_dir (str): Directory to save the output CSV. |
            Default: 'data/signals'.
        date_str (str): Date suffix for output filename (YYYYMMDD). |
            Uses today if empty.

    Returns:
        pd.DataFrame: Darvas signals with columns: NSE Code, Signal,
            Box High, Box Low, Box Days, Vol Confirmed, CMP, Tech Score.
            Empty DataFrame if no confirmed signals.

    Complexity:
        Time: O(S x N) where S = symbols, N = avg parquet rows
        Space: O(S)

    Example:
        >>> df = scan_darvas_breakouts(df_analyzed, daily_dir="data/historical/1d")
        >>> "Breakout" in df["Signal"].iloc[0]
        True
    """
    if not date_str:
        from datetime import date as dt_date

        date_str = dt_date.today().strftime("%Y%m%d")

    if "SYMBOL" not in analyzed_df.columns:
        LOGGER.error("Darvas scanner: SYMBOL column missing.")
        return pd.DataFrame()

    if not os.path.isdir(daily_dir):
        LOGGER.warning(
            "Darvas scanner: daily_dir '%s' not found — skipping.", daily_dir
        )
        return pd.DataFrame()

    records = []
    for symbol in analyzed_df["SYMBOL"].dropna().unique():
        pq_path = os.path.join(daily_dir, f"{symbol}.parquet")
        if not os.path.isfile(pq_path):
            continue
        try:
            df_hist = pd.read_parquet(pq_path)
            result = detect_darvas_box(df_hist)
        except Exception as exc:
            LOGGER.debug("Darvas: failed for %s: %s", symbol, exc)
            continue

        if result["signal"] in (
            "Breakout (Volume Confirmed)",
            "Breakout (No Volume Confirmation)",
            "Breakdown (Volume Confirmed)",
        ):
            row_data = analyzed_df[analyzed_df["SYMBOL"] == symbol]
            cmp = float(row_data["CMP"].iloc[0]) if not row_data.empty else np.nan
            tech = (
                float(row_data["TECH_SCORE"].iloc[0]) if not row_data.empty else np.nan
            )
            records.append(
                {
                    "NSE Code": symbol,
                    "Signal": result["signal"],
                    "Box High": result["box_high"],
                    "Box Low": result["box_low"],
                    "Box Days": result["box_days"],
                    "Vol Confirmed": result["vol_confirmed"],
                    "CMP": cmp,
                    "Tech Score": tech,
                }
            )

    if not records:
        LOGGER.info("Darvas scanner: no breakout/breakdown signals today.")
        return pd.DataFrame()

    df_out = pd.DataFrame(records).sort_values(by="Vol Confirmed", ascending=False)

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"darvas_signals_{date_str}.csv")
    df_out.to_csv(out_path, index=False)
    LOGGER.info("Darvas scanner: %d signals saved to %s", len(df_out), out_path)
    return df_out
