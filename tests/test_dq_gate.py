"""
Tests for Data Quality Gate (Unit 17) using real historical market data.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.storage.dq_gate import DataQualityGate, DataQualityHalt

REAL_HIST_1D = Path("data/historical/1d")


def test_check_symbol_healthy(tmp_path: Path):
    """Real market Parquet file with fresh data and canonical TA passes gate."""
    sandbox = tmp_path / "1d"
    sandbox.mkdir(parents=True)
    shutil.copyfile(REAL_HIST_1D / "RELIANCE.parquet", sandbox / "RELIANCE.parquet")

    gate = DataQualityGate(audit_dir=str(tmp_path / "logs"))
    res = gate.check_symbol("RELIANCE", hist_dir=sandbox)

    assert res.passed is True
    assert res.failure_reason is None
    assert res.has_stale_ta is False
    assert res.row_count > 50


def test_check_symbol_stale_ta(tmp_path: Path):
    """Real market Parquet with stale TA triggers STALE_TA assertion failure."""
    sandbox = tmp_path / "1d"
    sandbox.mkdir(parents=True)

    df = pd.read_parquet(REAL_HIST_1D / "INFY.parquet")
    df.loc[df.index[-1], "RSI_14"] = np.nan
    df.to_parquet(sandbox / "INFY.parquet")

    gate = DataQualityGate(audit_dir=str(tmp_path / "logs"))
    res = gate.check_symbol("INFY", hist_dir=sandbox)

    assert res.passed is False
    assert res.failure_reason == "STALE_TA"
    assert res.has_stale_ta is True


def test_check_symbol_missing_file(tmp_path: Path):
    """Missing file triggers FILE_MISSING failure."""
    sandbox = tmp_path / "1d"
    sandbox.mkdir(parents=True)

    gate = DataQualityGate(audit_dir=str(tmp_path / "logs"))
    res = gate.check_symbol("NONEXISTENT", hist_dir=sandbox)

    assert res.passed is False
    assert res.failure_reason == "FILE_MISSING"


def test_check_symbol_low_coverage(tmp_path: Path):
    """Real market Parquet with low row coverage (<85%) triggers LOW_COVERAGE."""
    sandbox = tmp_path / "1d"
    sandbox.mkdir(parents=True)

    df = pd.read_parquet(REAL_HIST_1D / "SBIN.parquet")
    # Keep only 30 sparse bars while preserving multi-year span
    df_sparse = pd.concat([df.iloc[:15], df.iloc[-15:]])
    df_sparse.to_parquet(sandbox / "SBIN.parquet")

    gate = DataQualityGate(audit_dir=str(tmp_path / "logs"))
    res = gate.check_symbol("SBIN", hist_dir=sandbox)

    assert res.passed is False
    assert res.failure_reason == "LOW_COVERAGE"


def test_batch_halt_threshold(tmp_path: Path):
    """Batch of 10 real symbols with 1 failure breaches 5% threshold and halts."""
    sandbox = tmp_path / "1d"
    sandbox.mkdir(parents=True)

    healthy_symbols = [
        "RELIANCE", "INFY", "HDFCBANK", "ICICIBANK", "AXISBANK",
        "LT", "HINDUNILVR", "ITC", "BHARTIARTL"
    ]
    for sym in healthy_symbols:
        shutil.copyfile(REAL_HIST_1D / f"{sym}.parquet", sandbox / f"{sym}.parquet")

    # 10th symbol: real TCS with stale TA
    df_tcs = pd.read_parquet(REAL_HIST_1D / "TCS.parquet")
    df_tcs.loc[df_tcs.index[-1], "RSI_14"] = np.nan
    df_tcs.to_parquet(sandbox / "TCS.parquet")

    all_symbols = healthy_symbols + ["TCS"]
    gate = DataQualityGate(
        audit_dir=str(tmp_path / "logs"),
        halt_if_failure_pct=0.05,
    )

    with pytest.raises(DataQualityHalt) as exc_info:
        gate.check_batch(all_symbols, hist_dir=sandbox, stage="test_stage", halt_on_breach=True)

    assert "exceeding halt threshold" in str(exc_info.value)


def test_batch_warn_only(tmp_path: Path):
    """Batch with halt_if_failure_pct=1.0 logs warnings without raising DataQualityHalt."""
    sandbox = tmp_path / "1d"
    sandbox.mkdir(parents=True)

    healthy_symbols = [
        "RELIANCE", "INFY", "HDFCBANK", "ICICIBANK", "AXISBANK",
        "LT", "HINDUNILVR", "ITC", "BHARTIARTL"
    ]
    for sym in healthy_symbols:
        shutil.copyfile(REAL_HIST_1D / f"{sym}.parquet", sandbox / f"{sym}.parquet")

    df_tcs = pd.read_parquet(REAL_HIST_1D / "TCS.parquet")
    df_tcs.loc[df_tcs.index[-1], "RSI_14"] = np.nan
    df_tcs.to_parquet(sandbox / "TCS.parquet")

    all_symbols = healthy_symbols + ["TCS"]
    gate = DataQualityGate(
        audit_dir=str(tmp_path / "logs"),
        halt_if_failure_pct=1.0,
    )

    batch_res = gate.check_batch(all_symbols, hist_dir=sandbox, stage="test_stage", halt_on_breach=True)
    assert batch_res.halt_triggered is False
    assert batch_res.passed_count == 9
    assert batch_res.failed_count == 1


def test_audit_log_written(tmp_path: Path):
    """Audit log records written to runs.jsonl and symbols.jsonl using real market data."""
    sandbox = tmp_path / "1d"
    sandbox.mkdir(parents=True)

    shutil.copyfile(REAL_HIST_1D / "RELIANCE.parquet", sandbox / "RELIANCE.parquet")
    df_tcs = pd.read_parquet(REAL_HIST_1D / "TCS.parquet")
    df_tcs.loc[df_tcs.index[-1], "RSI_14"] = np.nan
    df_tcs.to_parquet(sandbox / "TCS.parquet")

    audit_dir = tmp_path / "logs" / "dq"
    gate = DataQualityGate(audit_dir=str(audit_dir), halt_if_failure_pct=1.0)
    batch_res = gate.check_batch(["RELIANCE", "TCS"], hist_dir=sandbox, stage="test_audit")

    runs_file = audit_dir / "runs.jsonl"
    symbols_file = audit_dir / "symbols.jsonl"

    assert runs_file.is_file()
    assert symbols_file.is_file()

    with open(runs_file, "r", encoding="utf-8") as rf:
        run_record = json.loads(rf.readline())

    assert run_record["run_id"] == batch_res.run_id
    assert run_record["total_symbols"] == 2
    assert run_record["failed_count"] == 1

    with open(symbols_file, "r", encoding="utf-8") as sf:
        symbol_records = [json.loads(line) for line in sf]

    assert len(symbol_records) == 2
    for s_rec in symbol_records:
        assert s_rec["run_id"] == run_record["run_id"]


def test_dq_check_cli_exit_codes(tmp_path: Path):
    """main.py dq-check exits 0 on healthy real sandbox and exits 1 on stale real sandbox."""
    # Healthy sandbox
    healthy_dir = tmp_path / "healthy" / "1d"
    healthy_dir.mkdir(parents=True)
    shutil.copyfile(REAL_HIST_1D / "RELIANCE.parquet", healthy_dir / "RELIANCE.parquet")

    cmd_healthy = [
        sys.executable,
        "main.py",
        "--hist-dir",
        str(healthy_dir.parent),
        "dq-check",
    ]
    res_healthy = subprocess.run(cmd_healthy, capture_output=True, text=True)
    assert res_healthy.returncode == 0
    assert "DQ: 1 symbols checked, 1 healthy" in res_healthy.stdout

    # Stale sandbox
    stale_dir = tmp_path / "stale" / "1d"
    stale_dir.mkdir(parents=True)
    df_tcs = pd.read_parquet(REAL_HIST_1D / "TCS.parquet")
    df_tcs.loc[df_tcs.index[-1], "RSI_14"] = np.nan
    df_tcs.to_parquet(stale_dir / "TCS.parquet")

    cmd_stale = [
        sys.executable,
        "main.py",
        "--hist-dir",
        str(stale_dir.parent),
        "dq-check",
    ]
    res_stale = subprocess.run(cmd_stale, capture_output=True, text=True)
    assert res_stale.returncode == 1
    assert "DQ: 1 symbols checked, 0 healthy, 0 stale, 1 missing TA" in res_stale.stdout
