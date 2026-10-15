"""
File: src/engine/smc_scanner.py
Purpose: Scans local OHLCV Parquet cache, runs SMC analysis, and persists calls.
"""

from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd

from src.engine.smc import calculate_smc
from src.engine.smc_decision import generate_smc_call, TradingCall
from src.storage.smc_db import SMCDatabase

LOGGER = logging.getLogger(__name__)

def run_smc_scan(
    hist_dir: str = "data/historical/1d",
    db_path: str = "data/smc_calls.sqlite",
    limit: int | None = None,
    symbols: list[str] | None = None,
) -> list[TradingCall]:
    """
    Scans parquet files in hist_dir and generates SMC calls.
    """
    hist_path = Path(hist_dir)
    if not hist_path.exists():
        raise FileNotFoundError(f"Historical directory not found: {hist_dir}")

    db = SMCDatabase(db_path=db_path)

    # Resolve target files
    if symbols:
        files = [hist_path / f"{sym}.parquet" for sym in symbols if (hist_path / f"{sym}.parquet").exists()]
    else:
        files = sorted(list(hist_path.glob("*.parquet")))

    if limit:
        files = files[:limit]

    generated_calls: list[TradingCall] = []

    for file_path in files:
        symbol = file_path.stem
        try:
            df = pd.read_parquet(file_path)
            if df.empty or len(df) < 50:
                continue

            # Standardize column naming
            df.columns = [c.lower() for c in df.columns]
            if not all(col in df.columns for col in ["open", "high", "low", "close"]):
                continue

            # Run SMC Engine
            smc_res = calculate_smc(df, swing_length=20, internal_length=5)

            # Check for setups
            call = generate_smc_call(symbol, smc_res, df)
            if call:
                db.create_call(call)
                generated_calls.append(call)

        except Exception as e:
            LOGGER.debug(f"Failed to scan {symbol}: {e}")
            continue

    return generated_calls
