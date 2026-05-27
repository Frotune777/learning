"""
File: src/nse_bhavcopy/position_sizer.py
Purpose: Computes ATR-based position size, stop price, and risk amount per stock.
Last Modified: 2026-05-27
"""

import logging

import numpy as np
import pandas as pd

LOGGER: logging.Logger = logging.getLogger(__name__)

# Default risk parameters — override per call
DEFAULT_PORTFOLIO_SIZE: float = 500_000.0  # ₹5 Lakh
DEFAULT_RISK_PCT: float = 0.01  # 1% of portfolio per trade
DEFAULT_ATR_MULTIPLIER: float = 1.5  # Stop = 1.5 x ATR below CMP


def calculate_position_size(
    cmp: float,
    atr: float,
    portfolio_size: float = DEFAULT_PORTFOLIO_SIZE,
    risk_pct: float = DEFAULT_RISK_PCT,
    atr_multiplier: float = DEFAULT_ATR_MULTIPLIER,
) -> dict[str, float]:
    """
    Compute the optimal position size for one stock using the ATR-stop method.

    The stop distance is defined as atr_multiplier x ATR. The number of shares
    is floor(risk_amount / stop_distance), ensuring the maximum possible loss
    on a single trade never exceeds risk_pct x portfolio_size.

    Parameters:
        cmp (float): Current market price of the stock. | Must be > 0.
        atr (float): ATR (Average True Range) of the stock. | Must be > 0.
        portfolio_size (float): Total portfolio value in INR. | Default: 500_000
        risk_pct (float): Fraction of portfolio to risk per trade. |
            Default: 0.01 (1%)
        atr_multiplier (float): Multiplier applied to ATR for stop distance. |
            Default: 1.5

    Returns:
        dict[str, float]: Result dictionary with keys:
            - suggested_qty (int): Number of shares to buy (floored).
            - stop_price (float): Price level to place stop-loss order.
            - risk_amount (float): Max INR at risk for this trade.
            - position_value (float): Total capital deployed (qty x cmp).
            - stop_distance (float): ATR-based stop distance in INR.
            - risk_reward_target (float): 2x risk target price (R:R = 1:2).

    Raises:
        ValueError: If cmp ≤ 0 or atr ≤ 0.

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> result = calculate_position_size(cmp=250.0, atr=8.5)
        >>> print(result)
        {'suggested_qty': 392, 'stop_price': 237.25, 'risk_amount': 5000.0, ...}
    """
    if cmp <= 0:
        raise ValueError(f"CMP must be positive, got {cmp!r}")
    if atr <= 0:
        raise ValueError(f"ATR must be positive, got {atr!r}")

    risk_amount: float = portfolio_size * risk_pct
    stop_distance: float = atr_multiplier * atr
    stop_price: float = round(cmp - stop_distance, 2)

    suggested_qty: int = max(int(risk_amount / stop_distance), 0)
    position_value: float = round(suggested_qty * cmp, 2)
    rr_target: float = round(cmp + (2.0 * stop_distance), 2)

    return {
        "suggested_qty": float(suggested_qty),
        "stop_price": stop_price,
        "risk_amount": round(risk_amount, 2),
        "position_value": position_value,
        "stop_distance": round(stop_distance, 2),
        "risk_reward_target": rr_target,
    }


def _size_callout(qty: int, stop: float, risk: float, sym: str) -> str:
    """
    Build a user-facing position sizing callout string.

    Parameters:
        qty (int): Suggested share quantity.
        stop (float): Stop-loss price level.
        risk (float): Max INR at risk for the trade.
        sym (str): Stock symbol for context.

    Returns:
        str: Formatted callout string.

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> _size_callout(45, 542.30, 5000.0, "SUZLON")
        '📦 SUZLON: 45 shares | Stop ₹542.30 | Risk ₹5,000 (1% portfolio)'
    """
    return (
        f"📦 {sym}: {qty} shares | "
        f"Stop ₹{stop:,.2f} | "
        f"Risk ₹{risk:,.0f} (1% portfolio)"
    )


def add_position_sizing(
    df: pd.DataFrame,
    portfolio_size: float = DEFAULT_PORTFOLIO_SIZE,
    risk_pct: float = DEFAULT_RISK_PCT,
    atr_multiplier: float = DEFAULT_ATR_MULTIPLIER,
    cmp_col: str = "CMP",
    atr_col: str = "ATR_14",
    symbol_col: str = "SYMBOL",
) -> pd.DataFrame:
    """
    Append position-sizing columns to the analyzed screener DataFrame.

    For each row, derives suggested quantity, stop price, and risk exposure
    from the stock's current price and ATR. Rows where CMP or ATR_14 are
    NaN or non-positive receive NaN in all sizing columns.

    Parameters:
        df (pd.DataFrame): Analyzed screener DataFrame with CMP and ATR_14.
        portfolio_size (float): Total portfolio capital in INR. | Default: 500_000
        risk_pct (float): Fraction of portfolio risked per trade. | Default: 0.01
        atr_multiplier (float): ATR multiplier for stop distance. | Default: 1.5
        cmp_col (str): Column name for current market price. | Default: "CMP"
        atr_col (str): Column name for ATR indicator. | Default: "ATR_14"
        symbol_col (str): Column name for stock symbol. | Default: "SYMBOL"

    Returns:
        pd.DataFrame: Copy of input DataFrame with new columns:
            - SUGGESTED_QTY (int): Shares to buy for 1% risk.
            - STOP_PRICE (float): ATR-derived stop-loss level.
            - RISK_AMOUNT (float): Max INR loss for this position.
            - POSITION_VALUE (float): Total capital to deploy.
            - RR_TARGET (float): 1:2 risk-reward target price.
            - SIZING_CALLOUT (str): Human-readable position summary.

    Raises:
        KeyError: If cmp_col or atr_col are not present in df.columns.

    Complexity:
        Time: O(N) [Row-wise scalar arithmetic]
        Space: O(N) [Six new Series]

    Example:
        >>> df = pd.read_csv("data/historical/top_250_analyzed_20260527.csv")
        >>> sized = add_position_sizing(df, portfolio_size=500_000)
        >>> print(sized[["SYMBOL", "CMP", "SUGGESTED_QTY", "STOP_PRICE"]].head(5))
    """
    for col in (cmp_col, atr_col):
        if col not in df.columns:
            raise KeyError(
                f"Required column '{col}' not found in DataFrame. "
                f"Available: {df.columns.tolist()}"
            )

    df = df.copy()

    qty_list: list[float] = []
    stop_list: list[float] = []
    risk_list: list[float] = []
    pval_list: list[float] = []
    rr_list: list[float] = []
    callout_list: list[str] = []

    sym_col_present = symbol_col in df.columns

    for _, row in df.iterrows():
        cmp = row.get(cmp_col)
        atr = row.get(atr_col)
        sym = str(row.get(symbol_col, "Stock")) if sym_col_present else "Stock"

        if (
            cmp is None
            or atr is None
            or pd.isna(cmp)
            or pd.isna(atr)
            or float(cmp) <= 0
            or float(atr) <= 0
        ):
            qty_list.append(np.nan)
            stop_list.append(np.nan)
            risk_list.append(np.nan)
            pval_list.append(np.nan)
            rr_list.append(np.nan)
            callout_list.append("⚠️  Sizing unavailable — invalid CMP or ATR")
            continue

        sizes = calculate_position_size(
            cmp=float(cmp),
            atr=float(atr),
            portfolio_size=portfolio_size,
            risk_pct=risk_pct,
            atr_multiplier=atr_multiplier,
        )
        qty_list.append(sizes["suggested_qty"])
        stop_list.append(sizes["stop_price"])
        risk_list.append(sizes["risk_amount"])
        pval_list.append(sizes["position_value"])
        rr_list.append(sizes["risk_reward_target"])
        callout_list.append(
            _size_callout(
                int(sizes["suggested_qty"]),
                sizes["stop_price"],
                sizes["risk_amount"],
                sym,
            )
        )

    df["SUGGESTED_QTY"] = qty_list
    df["STOP_PRICE"] = stop_list
    df["RISK_AMOUNT"] = risk_list
    df["POSITION_VALUE"] = pval_list
    df["RR_TARGET"] = rr_list
    df["SIZING_CALLOUT"] = callout_list

    valid = int(df["SUGGESTED_QTY"].notna().sum())
    LOGGER.info(
        "Position sizing complete: %d/%d stocks sized "
        "(portfolio=₹%,.0f, risk=%.0f%%, ATRx%.1f).",
        valid,
        len(df),
        portfolio_size,
        risk_pct * 100,
        atr_multiplier,
    )
    return df
