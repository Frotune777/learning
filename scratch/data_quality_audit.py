"""
File: scratch/data_quality_audit.py
Purpose: Audit historical price datasets and technical indicators.

Dependencies:
    External:
        - pandas>=2.2.3: DataFrame time-series calculations
        - numpy>=2.4.6: Numerical and NaN utilities
        - pyarrow>=19.0.1: Parquet loading
    Internal:
        - src.nse_bhavcopy.ta_indicators: [add_ta_indicators]

Key Components:
    Functions:
        - audit_parquet_files: Check Parquet data integrity.
        - validate_ta_indicators: Recalculate and compare with standard formulas.
        - scan_price_anomalies: Detect price boundaries and outliers.
        - run_full_audit: Run all audits and output summary.

Last Modified: 2026-06-17
Modified By: Fortune

Open Tasks:
    - [ ] [LOW] Add more detailed statistic metrics [2h]

Related Files:
    - src/nse_bhavcopy/ta_indicators.py: Source of TA-Lib functions.
"""

import glob
import os
from typing import Any

import numpy as np
import pandas as pd

from src.nse_bhavcopy.ta_indicators import add_ta_indicators


def pandas_sma(series: pd.Series, period: int = 20) -> pd.Series:
    """
    Calculate Simple Moving Average using Pandas rolling mean.

    Logic:
        Step 1: Compute rolling mean with given window size.

    Parameters:
        series (pd.Series): Input series (Close prices).
        period (int): Window period for SMA. | Default: 20

    Returns:
        pd.Series: SMA series.
    """
    return series.rolling(window=period).mean()


def pandas_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index using Wilder's smoothing.

    Logic:
        Step 1: Compute price changes.
        Step 2: Split gains and losses.
        Step 3: Apply exponential moving average smoothing.
        Step 4: Compute RS and RSI.

    Parameters:
        series (pd.Series): Input series (Close prices).
        period (int): Window period for RSI. | Default: 14

    Returns:
        pd.Series: RSI series.
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder's exponential smoothing
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()

    # Avoid division by zero
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # Replace NaN with 50 or boundary cases
    rsi = rsi.fillna(50)
    return rsi


def audit_parquet_files(hist_dir: str) -> dict[str, Any]:
    """
    Audit historical price Parquet files in data/historical/1d.

    Logic:
        Step 1: Locate all Parquet files in the specified directory.
        Step 2: Loop through each file and load the dataset.
        Step 3: Check for duplicate dates, nulls, inf values, and gap sizes.
        Step 4: Accumulate and return results.

    Parameters:
        hist_dir (str): Directory containing Parquet files.

    Returns:
        dict: Dict containing statistics on duplicates, nulls, inf, and continuity.
    """
    parquet_files = glob.glob(os.path.join(hist_dir, "1d", "*.parquet"))
    total_files = len(parquet_files)
    if total_files == 0:
        return {"error": "No Parquet files found"}

    results: dict[str, Any] = {
        "total_tickers": total_files,
        "duplicate_rows": 0,
        "null_counts": {"Open": 0, "High": 0, "Low": 0, "Close": 0, "Volume": 0},
        "inf_counts": {"Open": 0, "High": 0, "Low": 0, "Close": 0, "Volume": 0},
        "date_continuity": {
            "total_gaps_gt_5d": 0,
            "tickers_with_gaps": [],
            "date_range_mismatches": [],
        },
        "negative_or_zero_prices": 0,
        "mismatched_high_low": 0,
        "extreme_single_day_returns": 0,
    }

    dates_registry = {}

    for file_path in parquet_files:
        ticker = os.path.basename(file_path).replace(".parquet", "")
        df = pd.read_parquet(file_path)

        if df.empty:
            continue

        # Check duplicates
        if df.index.duplicated().any():
            results["duplicate_rows"] += df.index.duplicated().sum()

        # Check nulls/NaNs
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                results["null_counts"][col] += df[col].isna().sum()
                results["inf_counts"][col] += np.isinf(df[col]).sum()

        # Check negative/zero prices
        for col in ["Open", "High", "Low", "Close"]:
            if col in df.columns:
                results["negative_or_zero_prices"] += (df[col] <= 0).sum()

        # Check high/low bounds consistency
        if "High" in df.columns and "Low" in df.columns:
            results["mismatched_high_low"] += (df["High"] < df["Low"]).sum()
            results["mismatched_high_low"] += (df["Open"] > df["High"]).sum()
            results["mismatched_high_low"] += (df["Close"] > df["High"]).sum()
            results["mismatched_high_low"] += (df["Open"] < df["Low"]).sum()
            results["mismatched_high_low"] += (df["Close"] < df["Low"]).sum()

        # Check extreme single day returns (>50% move)
        if "Close" in df.columns:
            ret = df["Close"].pct_change().abs()
            results["extreme_single_day_returns"] += (ret > 0.50).sum()

        # Date continuity check
        dates = pd.to_datetime(df.index).sort_values()
        dates_registry[ticker] = (dates.min(), dates.max(), len(dates))

        # Check for gaps > 5 business days
        if len(dates) > 1:
            diffs = (dates[1:] - dates[:-1]).days
            gaps = (diffs > 7).sum()  # 7 calendar days covers 5 business days
            if gaps > 0:
                results["date_continuity"]["total_gaps_gt_5d"] += gaps
                results["date_continuity"]["tickers_with_gaps"].append(
                    (ticker, int(gaps))
                )

    return results


def validate_ta_indicators(hist_dir: str) -> dict[str, Any]:
    """
    Validate that calculated indicators match standard mathematical formulas.

    Logic:
        Step 1: Load a benchmark stock (e.g. RELIANCE or TCS).
        Step 2: Add indicators using the project's add_ta_indicators function.
        Step 3: Manually calculate SMA and RSI using pure pandas.
        Step 4: Measure differences (MAE) between manual and TA-Lib values.

    Parameters:
        hist_dir (str): Directory containing Parquet files.

    Returns:
        dict: Summary of differences for validation.
    """
    parquet_files = glob.glob(os.path.join(hist_dir, "1d", "*.parquet"))
    if not parquet_files:
        return {"error": "No Parquet files found"}

    # Use first available ticker as validation candidate
    test_file = parquet_files[0]
    ticker = os.path.basename(test_file).replace(".parquet", "")
    df = pd.read_parquet(test_file)

    if len(df) < 50:
        # Try to find a larger one
        for f in parquet_files:
            temp_df = pd.read_parquet(f)
            if len(temp_df) > 100:
                df = temp_df
                ticker = os.path.basename(f).replace(".parquet", "")
                break

    df_ta = add_ta_indicators(df)
    close_series = df["Close"].astype("float64")

    # Calculate via pandas
    pd_rsi = pandas_rsi(close_series, period=14)
    pd_sma = pandas_sma(close_series, period=20)

    # Align values (skip initial NaNs)
    valid_idx = 40
    diff_rsi = np.abs(df_ta["RSI_14"].iloc[valid_idx:] - pd_rsi.iloc[valid_idx:])
    diff_sma = np.abs(df_ta["SMA_20"].iloc[valid_idx:] - pd_sma.iloc[valid_idx:])

    # Verify ATR math manually: ATR_t = (ATR_{t-1} * 13 + TR_t) / 14
    # TR = max(H-L, abs(H-C_prev), abs(L-C_prev))
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    pd_atr = tr.ewm(alpha=1.0 / 14, adjust=False).mean()
    # Note: TA-Lib ATR uses Wilder's smoothing which matches
    # ewm(alpha=1/N, adjust=False) after initial SMA
    diff_atr = np.abs(df_ta["ATR_14"].iloc[valid_idx:] - pd_atr.iloc[valid_idx:])

    return {
        "ticker_validated": ticker,
        "data_points": len(df),
        "rsi_ta_lib_vs_pandas_mae": float(diff_rsi.mean()),
        "rsi_ta_lib_vs_pandas_max_diff": float(diff_rsi.max()),
        "sma_ta_lib_vs_pandas_mae": float(diff_sma.mean()),
        "sma_ta_lib_vs_pandas_max_diff": float(diff_sma.max()),
        "atr_ta_lib_vs_pandas_mae": float(diff_atr.mean()),
        "atr_ta_lib_vs_pandas_max_diff": float(diff_atr.max()),
    }


def audit_signals_csv(csv_path: str) -> dict[str, Any]:
    """
    Profile the calculated signals and values in the enriched top 250 CSV file.

    Parameters:
        csv_path (str): Path to top_250_enriched_*.csv.

    Returns:
        dict: Summary metrics.
    """
    if not os.path.exists(csv_path):
        return {"error": "CSV file not found"}

    df = pd.read_csv(csv_path)
    total_records = len(df)

    results = {
        "total_records": total_records,
        "columns_present": list(df.columns),
        "null_counts": df.isna().sum().to_dict(),
        "rsi_stats": {
            "min": float(df["RSI_14"].min()) if "RSI_14" in df.columns else None,
            "max": float(df["RSI_14"].max()) if "RSI_14" in df.columns else None,
            "mean": float(df["RSI_14"].mean()) if "RSI_14" in df.columns else None,
            "nulls": int(df["RSI_14"].isna().sum()) if "RSI_14" in df.columns else 0,
        },
        "consensus_callout_distribution": df["CONSENSUS_CALLOUT"]
        .value_counts()
        .to_dict()
        if "CONSENSUS_CALLOUT" in df.columns
        else {},
        "trend_status_distribution": df["TREND_STATUS"].value_counts().to_dict()
        if "TREND_STATUS" in df.columns
        else {},
        "vol_regime_distribution": df["VOL_REGIME"].value_counts().to_dict()
        if "VOL_REGIME" in df.columns
        else {},
    }
    return results


def run_full_audit() -> None:
    """
    Orchestrate and print the full data quality and statistical audit report.
    """
    hist_dir = "data/historical"
    enriched_csv = glob.glob("data/processed/top_250_enriched_*.csv")

    print("====================================================")
    print("RUNNING QUANTITATIVE DATA QUALITY & STATISTICAL AUDIT")
    print("====================================================")

    # 1. Parquet integrity check
    print("\n--- 1. PARQUET PRICE DATASETS INTEGRITY CHECK ---")
    parquet_results = audit_parquet_files(hist_dir)
    for k, v in parquet_results.items():
        if k != "date_continuity":
            print(f"{k}: {v}")
        else:
            print(f"date_continuity - gaps > 5d: {v['total_gaps_gt_5d']}")
            print(f"date_continuity - tickers with gaps: {len(v['tickers_with_gaps'])}")

    # 2. Recalculation and validation against standard formulas
    print("\n--- 2. TECHNICAL INDICATORS MATHEMATICAL VALIDATION ---")
    ta_results = validate_ta_indicators(hist_dir)
    for k, v in ta_results.items():
        print(f"{k}: {v}")

    # 3. Calculated signals CSV profiling
    print("\n--- 3. CALCULATED SIGNALS CSV PROFILING ---")
    if enriched_csv:
        latest_csv = sorted(enriched_csv)[-1]
        print(f"Latest Enriched CSV: {latest_csv}")
        csv_results = audit_signals_csv(latest_csv)
        print(f"Total Rows: {csv_results['total_records']}")
        print(f"RSI Stats: {csv_results['rsi_stats']}")
        print(
            "Consensus Callout Distribution: "
            f"{csv_results['consensus_callout_distribution']}"
        )
        print(
            "Trend Status Distribution: " f"{csv_results['trend_status_distribution']}"
        )
        print(
            "Volatility Regime Distribution: "
            f"{csv_results['vol_regime_distribution']}"
        )
    else:
        print("No enriched CSV found in data/processed/")


if __name__ == "__main__":
    run_full_audit()
