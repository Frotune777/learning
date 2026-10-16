"""
Tests for repair-ta CLI command using real historical Parquet data.
"""

import argparse
import os
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.cli.actions import cmd_repair_ta

REAL_HIST_1D = Path("data/historical/1d")


def test_repair_ta_fixes_stale_parquet(capsys, tmp_path: Path):
    """Prove repair-ta repairs stale TA on real market Parquet and leaves healthy Parquet untouched."""
    sandbox = tmp_path / "repair_ta_test" / "1d"
    sandbox.mkdir(parents=True)

    stale_file = sandbox / "TCS.parquet"
    healthy_file = sandbox / "INFY.parquet"

    # Load real market data
    df_tcs = pd.read_parquet(REAL_HIST_1D / "TCS.parquet")
    df_infy = pd.read_parquet(REAL_HIST_1D / "INFY.parquet")

    # Reproduce the stale-TA bug: invalidate the last bar's RSI_14
    df_tcs.loc[df_tcs.index[-1], "RSI_14"] = np.nan
    df_tcs.to_parquet(stale_file)

    # Healthy file remains intact with complete real TA indicators
    df_infy.to_parquet(healthy_file)

    initial_mtime = os.path.getmtime(healthy_file)
    time.sleep(0.05)  # ensure mtime change would be detectable

    # Verify initial state: TCS has NaN RSI_14 on last bar
    df_stale_before = pd.read_parquet(stale_file)
    assert pd.isna(df_stale_before["RSI_14"].iloc[-1])

    # Run cmd_repair_ta
    args = argparse.Namespace(hist_dir=str(sandbox.parent))
    cmd_repair_ta(args)

    captured = capsys.readouterr().out
    assert "Checked: 2 files | Repaired: 1 files." in captured

    # Assert stale parquet's RSI_14.iloc[-1] is now recomputed and non-NaN
    df_stale_after = pd.read_parquet(stale_file)
    assert not pd.isna(df_stale_after["RSI_14"].iloc[-1])
    assert float(df_stale_after["RSI_14"].iloc[-1]) > 0

    # Assert healthy parquet was NOT modified
    assert os.path.getmtime(healthy_file) == initial_mtime


def test_repair_ta_noop_on_healthy_universe(capsys, tmp_path: Path):
    """Prove repair-ta is a complete no-op on healthy real Parquets."""
    sandbox = tmp_path / "repair_ta_healthy" / "1d"
    sandbox.mkdir(parents=True)

    symbols = ["TCS", "INFY", "RELIANCE"]
    files = []
    for sym in symbols:
        dest = sandbox / f"{sym}.parquet"
        shutil.copyfile(REAL_HIST_1D / f"{sym}.parquet", dest)
        files.append(dest)

    initial_mtimes = {f: os.path.getmtime(f) for f in files}
    time.sleep(0.05)

    args = argparse.Namespace(hist_dir=str(sandbox.parent))
    cmd_repair_ta(args)

    captured = capsys.readouterr().out
    assert "Checked: 3 files | Repaired: 0 files." in captured

    # Assert no files were modified
    for f in files:
        assert os.path.getmtime(f) == initial_mtimes[f]
