"""
File: src/nse_bhavcopy/nifty_ki_dukan.py
Purpose: Wrapper strategy for Strategy 1: Nifty Ki Dukan (DMA-DMA Method).
Last Modified: 2026-05-29
"""

import logging
import os
from datetime import date

import pandas as pd

LOGGER: logging.Logger = logging.getLogger(__name__)


def run_nifty_ki_dukan(
    analyzed_csv_path: str,
    output_dir: str = "data/signals",
    date_str: str = "",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run Strategy 1 (DMA-DMA Method) for both Variant A and Variant B.

    Reads the analyzed stock screener CSV file, applies the Cumulative Average
    Rule (CAR) filter ("Buy/Average Out"), and generates two sorted outputs:
    1. Variant A (No Stop Loss) list of Bull Run stocks, sorted by CMP ascending.
    2. Variant B (With Stop Loss) list of Bull Run stocks, sorted by CMP ascending.

    Parameters:
        analyzed_csv_path (str): Path to top_250_analyzed_YYYYMMDD.csv. |
            Must exist and contain TREND_STATUS, TREND_STATUS_SL, and CAR_RATING.
        output_dir (str): Directory where output CSV files will be stored. |
            Default: 'data/signals'.
        date_str (str): Date suffix for generated filenames (YYYYMMDD). |
            Uses today's date if empty.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: DataFrames for Variant A and
            Variant B bull lists, respectively.

    Raises:
        FileNotFoundError: If the analyzed CSV file is missing.

    Complexity:
        Time: O(N log N) where N = number of filtered stocks
        Space: O(N)

    Example:
        >>> df_a, df_b = run_nifty_ki_dukan(
        ...     "data/processed/top_250_analyzed_20260529.csv"
        ... )
        >>> len(df_a) >= 0
        True
    """
    if not os.path.isfile(analyzed_csv_path):
        raise FileNotFoundError(f"Analyzed CSV file not found: {analyzed_csv_path}")

    if not date_str:
        date_str = date.today().strftime("%Y%m%d")

    os.makedirs(output_dir, exist_ok=True)
    df_analyzed = pd.read_csv(analyzed_csv_path)

    # 1. Variant A (No Stop Loss)
    # Filter A: TREND_STATUS == "In Bull Run" AND CAR_RATING == "Buy/Average Out"
    df_var_a = pd.DataFrame()
    if "TREND_STATUS" in df_analyzed.columns and "CAR_RATING" in df_analyzed.columns:
        df_var_a = df_analyzed[
            (df_analyzed["TREND_STATUS"] == "In Bull Run")
            & (df_analyzed["CAR_RATING"] == "Buy/Average Out")
        ].copy()

    # Sort cheapest first (CMP ascending) — critical entry point discipline
    if not df_var_a.empty and "CMP" in df_var_a.columns:
        df_var_a = df_var_a.sort_values(by="CMP", ascending=True)

    # Clean columns for export
    export_cols = [
        "SYMBOL",
        "TURNOVER",
        "PREVIOUS_CLOSE",
        "CMP",
        "DIFF_200_DMA",
        "CAR_RATING",
    ]
    df_export_a = df_var_a[[c for c in export_cols if c in df_var_a.columns]].copy()
    df_export_a = df_export_a.rename(
        columns={
            "SYMBOL": "NSE Code",
            "TURNOVER": "Turnover",
            "PREVIOUS_CLOSE": "Previous Close",
            "CMP": "CMP",
            "DIFF_200_DMA": "%Diff 200 DMA",
            "CAR_RATING": "CAR",
        }
    )

    out_path_a = os.path.join(output_dir, f"dma_bull_nosl_{date_str}.csv")
    df_export_a.to_csv(out_path_a, index=False)
    LOGGER.info(
        "Nifty Ki Dukan (Variant A - No SL) saved: %s (%d records)",
        out_path_a,
        len(df_export_a),
    )

    # 2. Variant B (With Stop Loss / Reverse Trading)
    # Filter B: TREND_STATUS_SL == "In Bull Run (SL)" & CAR_RATING == "Buy/Average Out"
    df_var_b = pd.DataFrame()
    if "TREND_STATUS_SL" in df_analyzed.columns and "CAR_RATING" in df_analyzed.columns:
        df_var_b = df_analyzed[
            (df_analyzed["TREND_STATUS_SL"] == "In Bull Run (SL)")
            & (df_analyzed["CAR_RATING"] == "Buy/Average Out")
        ].copy()

    if not df_var_b.empty and "CMP" in df_var_b.columns:
        df_var_b = df_var_b.sort_values(by="CMP", ascending=True)

    df_export_b = df_var_b[[c for c in export_cols if c in df_var_b.columns]].copy()
    df_export_b = df_export_b.rename(
        columns={
            "SYMBOL": "NSE Code",
            "TURNOVER": "Turnover",
            "PREVIOUS_CLOSE": "Previous Close",
            "CMP": "CMP",
            "DIFF_200_DMA": "%Diff 200 DMA",
            "CAR_RATING": "CAR",
        }
    )

    out_path_b = os.path.join(output_dir, f"dma_bull_sl_{date_str}.csv")
    df_export_b.to_csv(out_path_b, index=False)
    LOGGER.info(
        "Nifty Ki Dukan (Variant B - With SL) saved: %s (%d records)",
        out_path_b,
        len(df_export_b),
    )

    return df_export_a, df_export_b
