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
    assert "DQ: 1 symbols checked | 1 healthy" in res_healthy.stdout

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
    assert "DQ: 1 symbols checked | 0 healthy" in res_stale.stdout
    assert "1 missing TA" in res_stale.stdout


def test_inactive_symbol_classified_as_inactive():
    """Real market Parquet with last bar >90 days old is classified as INACTIVE."""
    from datetime import date
    gate = DataQualityGate()
    res = gate.check_symbol("ABAN", REAL_HIST_1D, ref_date=date(2026, 10, 16))
    assert res.passed is False
    assert res.failure_reason == "DATA_STALE"
    assert res.classification == "INACTIVE"


def test_recently_stale_symbol_classified_as_stale_trading(tmp_path: Path):
    """Real market Parquet stalled recently (<90 days) is classified as STALE_TRADING."""
    from datetime import date
    sandbox = tmp_path / "1d"
    sandbox.mkdir(parents=True)

    df = pd.read_parquet(REAL_HIST_1D / "RELIANCE.parquet")
    # Slice to 8 days before 2026-10-16 reference date
    sliced = df[df.index <= "2026-10-08"]
    sliced.to_parquet(sandbox / "RELIANCE.parquet")

    gate = DataQualityGate()
    res = gate.check_symbol("RELIANCE", sandbox, ref_date=date(2026, 10, 16))
    assert res.passed is False
    assert res.failure_reason == "DATA_STALE"
    assert res.classification == "STALE_TRADING"


def test_batch_halt_ignores_inactive_by_default(tmp_path: Path):
    """Batch with inactive symbols does not count them in halt numerator by default."""
    from datetime import date
    sandbox = tmp_path / "1d"
    sandbox.mkdir(parents=True)

    healthy_symbols = [
        "RELIANCE", "INFY", "HDFCBANK", "ICICIBANK",
        "AXISBANK", "LT", "HINDUNILVR", "ITC"
    ]
    for sym in healthy_symbols:
        shutil.copyfile(REAL_HIST_1D / f"{sym}.parquet", sandbox / f"{sym}.parquet")

    # Inactive symbol: ABAN (last trade Feb 2026)
    shutil.copyfile(REAL_HIST_1D / "ABAN.parquet", sandbox / "ABAN.parquet")

    gate = DataQualityGate(audit_dir=str(tmp_path / "logs"), halt_if_failure_pct=0.08)
    batch_res = gate.check_batch(
        healthy_symbols + ["ABAN"],
        hist_dir=sandbox,
        stage="test_batch_inactive",
        ref_date=date(2026, 10, 16),
        halt_on_breach=True,
    )

    assert batch_res.halt_triggered is False
    assert batch_res.inactive_count == 1
    assert batch_res.failed_count == 0


def test_batch_halt_includes_inactive_when_flag_set(tmp_path: Path):
    """Batch with include_inactive=True counts inactive symbols in halt numerator."""
    from datetime import date
    sandbox = tmp_path / "1d"
    sandbox.mkdir(parents=True)

    healthy_symbols = [
        "RELIANCE", "INFY", "HDFCBANK", "ICICIBANK",
        "AXISBANK", "LT", "HINDUNILVR", "ITC"
    ]
    for sym in healthy_symbols:
        shutil.copyfile(REAL_HIST_1D / f"{sym}.parquet", sandbox / f"{sym}.parquet")

    shutil.copyfile(REAL_HIST_1D / "ABAN.parquet", sandbox / "ABAN.parquet")

    gate = DataQualityGate(audit_dir=str(tmp_path / "logs"), halt_if_failure_pct=0.08)

    with pytest.raises(DataQualityHalt) as exc_info:
        gate.check_batch(
            healthy_symbols + ["ABAN"],
            hist_dir=sandbox,
            stage="test_batch_inactive_flag",
            ref_date=date(2026, 10, 16),
            include_inactive=True,
            halt_on_breach=True,
        )

    assert "exceeding halt threshold" in str(exc_info.value)


def test_inactive_threshold_override():
    """Threshold override reclassifies symbol from INACTIVE to STALE_TRADING."""
    from datetime import date
    gate = DataQualityGate()
    # Default 90 days -> INACTIVE
    res_def = gate.check_symbol("ABAN", REAL_HIST_1D, ref_date=date(2026, 10, 16))
    assert res_def.classification == "INACTIVE"

    # Override 300 days -> STALE_TRADING
    res_over = gate.check_symbol("ABAN", REAL_HIST_1D, ref_date=date(2026, 10, 16), min_last_trade_days=300)
    assert res_over.classification == "STALE_TRADING"


def test_summary_line_reports_inactive_count(tmp_path: Path):
    """Summary line prints explicit inactive count and halt status."""
    sandbox = tmp_path / "1d"
    sandbox.mkdir(parents=True)
    shutil.copyfile(REAL_HIST_1D / "RELIANCE.parquet", sandbox / "RELIANCE.parquet")
    shutil.copyfile(REAL_HIST_1D / "ABAN.parquet", sandbox / "ABAN.parquet")

    cmd = [
        sys.executable,
        "main.py",
        "--hist-dir",
        str(sandbox.parent),
        "dq-check",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "inactive" in res.stdout
    assert "threshold 8.0%" in res.stdout


def test_inactive_snapshot_written(tmp_path: Path):
    """Artifact inactive_symbols.csv is written with expected schema."""
    import csv
    from datetime import date

    sandbox = tmp_path / "1d"
    sandbox.mkdir(parents=True)
    shutil.copyfile(REAL_HIST_1D / "ABAN.parquet", sandbox / "ABAN.parquet")

    gate = DataQualityGate(audit_dir=str(tmp_path / "logs"))
    gate.check_batch(["ABAN"], hist_dir=sandbox, ref_date=date(2026, 10, 16), write_audit=True)

    snapshot_path = tmp_path / "inactive_symbols.csv"
    assert snapshot_path.is_file()

    with open(snapshot_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == ["symbol", "last_bar_date", "days_since_last_trade", "classified_at"]
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0][0] == "ABAN"
        assert rows[0][1] == "2026-02-20"


def test_dq_check_cli_exits_zero_on_current_universe():
    """Unit 19A acceptance test: main.py dq-check exits 0 on current universe."""
    cmd = [sys.executable, "main.py", "dq-check"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Halt: NO" in res.stdout
    assert "inactive" in res.stdout
    assert "threshold 8.0%" in res.stdout

