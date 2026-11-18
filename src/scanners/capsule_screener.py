"""
File: src/scanners/capsule_screener.py
Purpose: Fast batch scanner for Capsule Academy 5-Star Framework, Train No. 920/130 & SMC.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.engine.capsule_engine import CapsuleAnalysisResult, analyze_capsule_strategy

LOGGER = logging.getLogger(__name__)


def run_capsule_screener(
    hist_dir: str = "data/historical/1d",
    symbols: list[str] | None = None,
    min_stars: int = 2,
    only_train_920130: bool = False,
    only_turnover_surge: bool = False,
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Scan stored Parquet files using Capsule Academy criteria and return results DataFrame.
    """
    p = Path(hist_dir)
    if not p.exists():
        LOGGER.error("Historical directory does not exist: %s", hist_dir)
        return pd.DataFrame()

    if symbols:
        target_files = [p / f"{s.strip().upper()}.parquet" for s in symbols if (p / f"{s.strip().upper()}.parquet").exists()]
    else:
        target_files = sorted(list(p.glob("*.parquet")))

    if limit:
        target_files = target_files[:limit]

    results: list[dict[str, Any]] = []
    lake_1h = p.parent / "1h" if p.name == "1d" else p / "1h"

    for f in target_files:
        sym = f.stem.strip().upper()
        try:
            df = pd.read_parquet(f)
            if df.empty or len(df) < 60:
                continue

            # Load 1H intraday bars if available
            df_hourly = None
            hourly_file = lake_1h / f"{sym}.parquet"
            if hourly_file.exists():
                try:
                    df_hourly = pd.read_parquet(hourly_file)
                except Exception as exc:
                    LOGGER.debug("Could not read 1h parquet for %s: %s", sym, exc)

            analysis = analyze_capsule_strategy(sym, df, df_hourly=df_hourly)
            if analysis is None:
                continue

            # Filtering
            if only_train_920130 and not analysis.train_920130_boarding:
                continue
            if only_turnover_surge and not analysis.star_turnover_surge:
                continue
            if not only_train_920130 and analysis.total_stars < min_stars:
                continue

            stars_str = "⭐" * analysis.total_stars
            results.append({
                "Symbol": analysis.symbol,
                "Close": analysis.close,
                "Stars": stars_str,
                "Star_Count": analysis.total_stars,
                "Monthly_Farms": "✔" if analysis.star_monthly_farms else "—",
                "Weekly_Sunflowers": "✔" if analysis.star_weekly_sunflowers else "—",
                "Daily_Seeds": "✔" if analysis.star_daily_seeds else "—",
                "Turnover_Surge": "✔" if analysis.star_turnover_surge else "—",
                "Train_920130": "🚂 BOARD" if analysis.train_920130_boarding else "—",
                "TF_Mode": analysis.tf_mode,
                "SMC_Setup": analysis.smc_ob_overlap,
                "Spring": "✔" if analysis.smc_spring else "—",
                "IFC": "✔" if analysis.smc_ifc_candle else "—",
                "RSI_D": round(analysis.rsi_daily, 1),
                "RSI_W": round(analysis.rsi_weekly, 1),
                "RSI_M": round(analysis.rsi_monthly, 1),
                "Action": analysis.recommended_action,
                "Stop_Loss": analysis.stop_loss,
                "Target": analysis.target_price,
                # Compatibility aliases for legacy reporters
                "SYMBOL": analysis.symbol,
                "CMP": analysis.close,
                "TREND_STATUS": f"{analysis.total_stars}★ Capsule",
                "CAR_RATING": "✔ Farms" if analysis.star_monthly_farms else "—",
                "CONSENSUS_SCORE": analysis.total_stars,
                "CONSENSUS_CALLOUT": f"{stars_str} | {analysis.recommended_action}",
                "TECH_SCORE": analysis.total_stars * 20.0,
                "RSI_14": round(analysis.rsi_daily, 1),
            })
        except Exception as exc:
            LOGGER.debug("Error screening %s: %s", sym, exc)
            continue

    if not results:
        return pd.DataFrame()

    res_df = pd.DataFrame(results).sort_values(by=["Train_920130", "Star_Count", "Close"], ascending=[False, False, False])
    return res_df
