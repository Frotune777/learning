"""
File: src/nse_bhavcopy/rsi_scanner.py
Purpose: Scan Nifty 50 + Next 50 universe for RSI < 35 daily buy signals.
Last Modified: 2026-05-29
"""

import logging
import os
from datetime import date

import numpy as np
import pandas as pd

from src.nse_bhavcopy.nifty_index_fetcher import get_nifty50, get_rsi_universe

LOGGER: logging.Logger = logging.getLogger(__name__)

RSI_ENTRY_THRESHOLD: float = 35.0
RSI_AVERAGING_STEPS: list[float] = [30.0, 25.0, 20.0, 15.0, 10.0, 5.0]
MIN_PRICE_DROP_PCT: float = 3.14


def _rsi_to_step_hint(rsi: float) -> str:
    """
    Map an RSI value to its Sharegenius averaging step label.

    Parameters:
        rsi (float): Current RSI(14) value. | 0 <= rsi <= 100.

    Returns:
        str: Human-readable label such as 'Step 1 (Entry < 35)'.

    Complexity:
        Time: O(1)  Space: O(1)

    Example:
        >>> _rsi_to_step_hint(28.5)
        'Step 2 (Average < 30)'
    """
    if pd.isna(rsi):
        return "Unknown"
    if rsi < 5.0:
        return "Step 7 (Average < 5)"
    if rsi < 10.0:
        return "Step 6 (Average < 10)"
    if rsi < 15.0:
        return "Step 5 (Average < 15)"
    if rsi < 20.0:
        return "Step 4 (Average < 20)"
    if rsi < 25.0:
        return "Step 3 (Average < 25)"
    if rsi < 30.0:
        return "Step 2 (Average < 30)"
    return "Step 1 (Entry < 35)"


def scan_rsi_signals(
    analyzed_csv_path: str,
    cache_dir: str = "data/indices",
    output_dir: str = "data/signals",
    force_index_refresh: bool = False,
) -> pd.DataFrame:
    """
    Identify RSI < 35 buy candidates within the Nifty 50 + Next 50 universe.

    Parameters:
        analyzed_csv_path (str): Path to top_250_analyzed_YYYYMMDD.csv. |
            Must contain SYMBOL and RSI_14 columns.
        cache_dir (str): Cache directory for index constituent JSON files. |
            Default: 'data/indices'.
        output_dir (str): Directory to write the output CSV. |
            Default: 'data/signals'.
        force_index_refresh (bool): Force re-fetch of index constituents. |
            Default: False.

    Returns:
        pd.DataFrame: RSI signal rows ranked by RSI ascending (most oversold
            first), with columns: NSE Code, RSI, CMP, Prev Close, AMO Price,
            Step Hint, In Nifty 50, Trend, Tech Score.

    Raises:
        FileNotFoundError: If analyzed_csv_path does not exist.

    Complexity:
        Time: O(N)  Space: O(N)

    Example:
        >>> df = scan_rsi_signals("data/processed/top_250_analyzed_20260529.csv")
        >>> df.columns.tolist()[0]
        'NSE Code'
    """
    if not os.path.isfile(analyzed_csv_path):
        raise FileNotFoundError(f"Analyzed CSV not found: {analyzed_csv_path}")

    df_all: pd.DataFrame = pd.read_csv(analyzed_csv_path)
    LOGGER.info("RSI scanner: loaded %d rows from %s", len(df_all), analyzed_csv_path)

    universe: list[str] = get_rsi_universe(
        cache_dir=cache_dir, force_refresh=force_index_refresh
    )

    if not universe:
        LOGGER.warning("RSI universe empty — falling back to full dataset.")
        df_universe = df_all.copy()
    else:
        df_universe = df_all[df_all["SYMBOL"].isin(universe)].copy()
        LOGGER.info(
            "RSI scanner: %d/%d symbols in universe", len(df_universe), len(universe)
        )

    if "RSI_14" not in df_universe.columns:
        LOGGER.error("RSI_14 column missing from analyzed CSV.")
        return pd.DataFrame()

    df_signals = df_universe[
        df_universe["RSI_14"].notna() & (df_universe["RSI_14"] < RSI_ENTRY_THRESHOLD)
    ].copy()

    if df_signals.empty:
        LOGGER.info(
            "RSI scanner: no stocks with RSI < %.1f found.", RSI_ENTRY_THRESHOLD
        )
        return pd.DataFrame()

    df_signals = df_signals.sort_values(by="RSI_14", ascending=True)

    if "PREVIOUS_CLOSE" in df_signals.columns:
        df_signals["AMO_PRICE"] = (df_signals["PREVIOUS_CLOSE"] - 0.01).round(2)
    else:
        df_signals["AMO_PRICE"] = np.nan

    df_signals["STEP_HINT"] = df_signals["RSI_14"].apply(_rsi_to_step_hint)

    try:
        n50 = set(get_nifty50(cache_dir=cache_dir))
    except Exception as exc:
        LOGGER.warning("Could not load Nifty50 list: %s", exc)
        n50 = set()
    df_signals["IN_NIFTY50"] = df_signals["SYMBOL"].isin(n50)

    keep_cols = [
        "SYMBOL",
        "RSI_14",
        "CMP",
        "PREVIOUS_CLOSE",
        "AMO_PRICE",
        "STEP_HINT",
        "IN_NIFTY50",
        "TREND_STATUS",
        "TECH_SCORE",
    ]
    df_out = df_signals[[c for c in keep_cols if c in df_signals.columns]].copy()
    df_out = df_out.rename(
        columns={
            "SYMBOL": "NSE Code",
            "RSI_14": "RSI",
            "CMP": "CMP",
            "PREVIOUS_CLOSE": "Prev Close",
            "AMO_PRICE": "AMO Price",
            "STEP_HINT": "Step Hint",
            "IN_NIFTY50": "In Nifty 50",
            "TREND_STATUS": "Trend",
            "TECH_SCORE": "Tech Score",
        }
    )

    os.makedirs(output_dir, exist_ok=True)
    date_str = date.today().strftime("%Y%m%d")
    out_path = os.path.join(output_dir, f"rsi_signals_{date_str}.csv")
    df_out.to_csv(out_path, index=False)
    LOGGER.info("RSI scanner: %d signals saved to %s", len(df_out), out_path)
    return df_out


def get_todays_buy(df_signals: pd.DataFrame) -> pd.Series | None:
    """
    Return the single highest-priority RSI buy for today (lowest RSI).

    Parameters:
        df_signals (pd.DataFrame): Output from scan_rsi_signals(). |
            Must be non-empty and already sorted by RSI ascending.

    Returns:
        pd.Series | None: Top-priority row, or None if DataFrame is empty.

    Complexity:
        Time: O(1)  Space: O(1)

    Example:
        >>> buy = get_todays_buy(df)
        >>> buy is not None
        True
    """
    if df_signals.empty:
        return None
    return df_signals.iloc[0]


def check_averaging_eligible(
    last_buy_price: float,
    current_price: float,
    current_rsi: float,
    last_rsi_step: int,
) -> dict[str, bool | str | int | None]:
    """
    Check whether a holding is eligible for the next RSI averaging step.

    Parameters:
        last_buy_price (float): Price at which last lot was purchased. | > 0.
        current_price (float): Today's closing price. | > 0.
        current_rsi (float): Today's RSI(14) value. | 0 <= rsi <= 100.
        last_rsi_step (int): Step number of last buy (1-7). | 1 <= n <= 7.

    Returns:
        dict[str, bool | str | int | None]: Keys: 'eligible', 'reason', 'next_step'.

    Complexity:
        Time: O(1)  Space: O(1)

    Example:
        >>> check_averaging_eligible(612.50, 580.00, 28.5, 1)
        {'eligible': True, 'reason': '...', 'next_step': 2}
    """
    if last_rsi_step >= 7:
        return {
            "eligible": False,
            "reason": "Maximum averaging steps (7) already reached.",
            "next_step": None,
        }

    next_step = last_rsi_step + 1
    next_threshold = RSI_AVERAGING_STEPS[last_rsi_step - 1]
    rsi_crossed = current_rsi < next_threshold

    price_drop_pct = 0.0
    if last_buy_price > 0:
        price_drop_pct = ((last_buy_price - current_price) / last_buy_price) * 100.0

    price_eligible = price_drop_pct >= MIN_PRICE_DROP_PCT
    eligible = rsi_crossed and price_eligible

    if eligible:
        reason = (
            f"RSI < {next_threshold:.0f} and price dropped "
            f"{price_drop_pct:.2f}% (>={MIN_PRICE_DROP_PCT}%)"
        )
    elif not rsi_crossed:
        reason = f"RSI {current_rsi:.2f} not yet below {next_threshold:.0f}"
    else:
        reason = f"Price drop {price_drop_pct:.2f}% < {MIN_PRICE_DROP_PCT}% required"

    return {
        "eligible": eligible,
        "reason": reason,
        "next_step": next_step if eligible else None,
    }
