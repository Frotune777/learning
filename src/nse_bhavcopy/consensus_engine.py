"""
File: src/nse_bhavcopy/consensus_engine.py
Purpose: Aggregates all strategy action signals into a unified consensus score and
    callout.
Last Modified: 2026-05-27
"""

import logging
from typing import Final

import pandas as pd

LOGGER: logging.Logger = logging.getLogger(__name__)

# Canonical buy signals across all STR_*_ACTION columns
_BUY_SIGNALS: Final[frozenset[str]] = frozenset(
    {
        "Buy",
        "Buy (55D Breakout)",
        "Buy on Support / Demand Level",
        "Breakout Buy",
        "Explosive Buy",
        "Level 1 Buy",
        "Level 2 Buy",
        "Level 3 Buy",
        "Super BO Buy",
        "150 DMA Breakout | CMP > 200 DMA",
        "50 DMA Breakout | CMP > 200 DMA",
    }
)

# Canonical sell signals across all STR_*_ACTION columns
_SELL_SIGNALS: Final[frozenset[str]] = frozenset({"Explosive Sell"})

# Ordered tuple of all 9 strategy action columns
_STRATEGY_COLUMNS: Final[tuple[str, ...]] = (
    "STR_NIFTY_SHOP_ACTION",
    "STR_BUY_LOW_ACTION",
    "STR_TURTLE_ACTION",
    "STR_RDX_ACTION",
    "STR_100SMA_ACTION",
    "STR_ETF_SHOP_ACTION",
    "STR_SUPER_BO_ACTION",
    "STR_DMA_REV_ACTION",
    "STR_DMA_NOSL_ACTION",
)

_NUM_STRATEGIES: Final[int] = len(_STRATEGY_COLUMNS)


def _score_action(action: object) -> int:
    """
    Map a single strategy action value to a score of +1, -1, or 0.

    Parameters:
        action (object): The action string from any STR_*_ACTION column.

    Returns:
        int: +1 for buy signal, -1 for sell signal, 0 for neutral/NaN.

    Complexity:
        Time: O(1) [Frozenset membership check]
        Space: O(1)

    Example:
        >>> _score_action("Breakout Buy")
        1
        >>> _score_action("Explosive Sell")
        -1
        >>> _score_action("Hold")
        0
    """
    if not isinstance(action, str):
        return 0
    if action in _BUY_SIGNALS:
        return 1
    if action in _SELL_SIGNALS:
        return -1
    return 0


def _build_callout(score: int, symbol: str) -> str:
    """
    Generate a human-readable consensus callout string for a given score.

    Parameters:
        score (int): Consensus score in range [-9, +9].
        symbol (str): Stock symbol for context in the callout message.

    Returns:
        str: Emoji-prefixed callout string describing conviction level.

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> _build_callout(7, "SUZLON")
        '⭐ 7/9 strategies agree: STRONG BUY on SUZLON'
        >>> _build_callout(-2, "TCS")
        '⚠️  2 sell signal(s) on TCS — use caution'
    """
    n = _NUM_STRATEGIES
    if score >= 7:
        return f"⭐ {score}/{n} strategies agree: STRONG BUY on {symbol}"
    if score >= 5:
        return f"✅ {score}/{n} strategies agree: HIGH CONVICTION BUY on {symbol}"
    if score >= 3:
        return f"📈 {score}/{n} strategies agree: MODERATE BUY on {symbol}"
    if score >= 1:
        return f"👀 {score}/{n} strategies signal: WEAK BUY on {symbol}"
    if score == 0:
        return f"⏸️  Neutral — no consensus on {symbol}"
    if score <= -3:
        return f"🔴 {abs(score)}/{n} strategies signal: SELL on {symbol}"
    return f"⚠️  {abs(score)} sell signal(s) on {symbol} — use caution"


def add_consensus_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append CONSENSUS_SCORE and CONSENSUS_CALLOUT columns to the screener DataFrame.

    Score ranges from -9 (all sell) to +9 (all buy). Each of the 9 strategy
    action columns contributes +1 (buy), -1 (sell), or 0 (neutral/hold).

    Parameters:
        df (pd.DataFrame): Analyzed screener DataFrame containing STR_*_ACTION
            columns. At least one strategy column must be present.

    Returns:
        pd.DataFrame: Copy of input with two new columns:
            - CONSENSUS_SCORE (int): Aggregated signal score [-9, +9].
            - CONSENSUS_CALLOUT (str): Human-readable interpretation string.

    Raises:
        ValueError: If none of the 9 expected strategy columns are present.

    Complexity:
        Time: O(N x 9) where N = number of rows (vectorized via pandas.map)
        Space: O(N) [Two new Series]

    Example:
        >>> import pandas as pd
        >>> df = pd.read_csv("data/historical/top_250_analyzed_20260527.csv")
        >>> enriched = add_consensus_score(df)
        >>> print(enriched[["SYMBOL", "CONSENSUS_SCORE"]].head(3))
    """
    present = [c for c in _STRATEGY_COLUMNS if c in df.columns]
    if not present:
        raise ValueError(
            "No strategy action columns found. " f"Expected one of: {_STRATEGY_COLUMNS}"
        )

    missing = [c for c in _STRATEGY_COLUMNS if c not in df.columns]
    if missing:
        LOGGER.warning(
            "Consensus engine: %d column(s) absent, skipping: %s",
            len(missing),
            missing,
        )

    score_matrix = df[present].apply(lambda col: col.map(_score_action))

    df = df.copy()
    df["CONSENSUS_SCORE"] = score_matrix.sum(axis=1).astype(int)

    sym_col = "SYMBOL" if "SYMBOL" in df.columns else "NSE Code"
    if sym_col in df.columns:
        df["CONSENSUS_CALLOUT"] = df.apply(
            lambda row: _build_callout(int(row["CONSENSUS_SCORE"]), str(row[sym_col])),
            axis=1,
        )
    else:
        df["CONSENSUS_CALLOUT"] = df["CONSENSUS_SCORE"].map(
            lambda s: _build_callout(int(s), "Stock")
        )

    LOGGER.info(
        "Consensus engine: %d stocks scored | top=%d | mean=%.2f",
        len(df),
        int(df["CONSENSUS_SCORE"].max()),
        float(df["CONSENSUS_SCORE"].mean()),
    )
    return df


def get_consensus_ranked(
    df: pd.DataFrame,
    min_score: int = 1,
    secondary_sort_col: str = "TURNOVER",
) -> pd.DataFrame:
    """
    Filter and sort the analyzed DataFrame by CONSENSUS_SCORE descending.

    Parameters:
        df (pd.DataFrame): DataFrame already enriched by add_consensus_score().
        min_score (int): Minimum inclusive score to include in output. | Default: 1
        secondary_sort_col (str): Tiebreaker column for equal scores. |
            Default: "TURNOVER"

    Returns:
        pd.DataFrame: Filtered, sorted DataFrame — highest consensus stocks first.

    Raises:
        KeyError: If CONSENSUS_SCORE column is absent (run add_consensus_score first).

    Complexity:
        Time: O(N log N) [Sort dominates]
        Space: O(N) [Filtered copy]

    Example:
        >>> enriched = add_consensus_score(df)
        >>> ranked = get_consensus_ranked(enriched, min_score=3)
        >>> print(ranked[["SYMBOL", "CONSENSUS_SCORE", "CONSENSUS_CALLOUT"]].head(5))
    """
    if "CONSENSUS_SCORE" not in df.columns:
        raise KeyError("CONSENSUS_SCORE not found. Run add_consensus_score() first.")

    sort_cols = ["CONSENSUS_SCORE"]
    ascending = [False]
    if secondary_sort_col in df.columns:
        sort_cols.append(secondary_sort_col)
        ascending.append(False)

    filtered = df[df["CONSENSUS_SCORE"] >= min_score].copy()
    result = filtered.sort_values(by=sort_cols, ascending=ascending)

    LOGGER.info(
        "Consensus ranked: %d stocks with score ≥ %d",
        len(result),
        min_score,
    )
    return result.reset_index(drop=True)
