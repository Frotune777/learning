"""
Data Quality Gate & Audit Log (Unit 17).

Provides automated quality checks for historical Parquet datasets across
individual symbol writes and batch pipelines.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.storage.sync_registry import SyncRegistry, _last_trading_day

LOGGER = logging.getLogger(__name__)


class DataQualityHalt(Exception):
    """Raised when batch data quality failure rate exceeds configured threshold."""


@dataclass
class SymbolDQResult:
    """Individual symbol verification result."""

    run_id: str
    timestamp: str
    symbol: str
    passed: bool
    failure_reason: str | None
    last_bar_date: str | None
    row_count: int
    coverage_pct: float
    has_stale_ta: bool


@dataclass
class BatchDQResult:
    """Batch verification summary."""

    run_id: str
    timestamp: str
    stage: str
    total_symbols: int
    passed_count: int
    failed_count: int
    failure_pct: float
    halt_triggered: bool
    duration_ms: float
    symbol_results: list[SymbolDQResult]


class DataQualityGate:
    """Configurable, logged Data Quality Gate with halt-or-warn policies."""

    DEFAULT_CONFIG: dict[str, Any] = {
        "min_coverage_pct": 0.85,
        "max_stale_days": 3,
        "fail_on_stale_ta": True,
        "halt_if_failure_pct": 0.05,
        "audit_dir": "logs/dq",
        "retention_days": 90,
    }

    def __init__(self, config_path: str | Path = "config/dq_config.json", **overrides: Any) -> None:
        self.config = dict(self.DEFAULT_CONFIG)
        cfg_path = Path(config_path)
        if cfg_path.is_file():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self.config.update(loaded)
            except Exception as exc:
                LOGGER.warning("Could not read %s, using defaults: %s", cfg_path, exc)
        self.config.update(overrides)

        self.min_coverage_pct = float(self.config["min_coverage_pct"])
        self.max_stale_days = int(self.config["max_stale_days"])
        self.fail_on_stale_ta = bool(self.config["fail_on_stale_ta"])
        self.halt_if_failure_pct = float(self.config["halt_if_failure_pct"])
        self.audit_dir = Path(self.config["audit_dir"])
        self.retention_days = int(self.config["retention_days"])

    def _resolve_file_path(self, symbol: str, hist_dir: str | Path) -> Path:
        base = Path(hist_dir)
        p1 = base / f"{symbol}.parquet"
        if p1.is_file():
            return p1
        p2 = base / "1d" / f"{symbol}.parquet"
        if p2.is_file():
            return p2
        return p1

    def check_symbol(
        self,
        symbol: str,
        hist_dir: str | Path,
        run_id: str | None = None,
        ref_date: date | None = None,
    ) -> SymbolDQResult:
        """Run the 6 core assertions against a symbol's Parquet file."""
        now_iso = datetime.now(timezone.utc).isoformat()
        rid = run_id or str(uuid.uuid4())
        sym = symbol.strip().upper()
        file_path = self._resolve_file_path(sym, hist_dir)

        # 1. file_exists
        if not file_path.is_file():
            return SymbolDQResult(
                run_id=rid,
                timestamp=now_iso,
                symbol=sym,
                passed=False,
                failure_reason="FILE_MISSING",
                last_bar_date=None,
                row_count=0,
                coverage_pct=0.0,
                has_stale_ta=False,
            )

        try:
            df = pd.read_parquet(file_path)
        except Exception as exc:
            return SymbolDQResult(
                run_id=rid,
                timestamp=now_iso,
                symbol=sym,
                passed=False,
                failure_reason=f"CORRUPT_FILE: {exc}",
                last_bar_date=None,
                row_count=0,
                coverage_pct=0.0,
                has_stale_ta=False,
            )

        # 2. first_bar_present
        if df.empty or not isinstance(df.index, pd.DatetimeIndex) or pd.isna(df.index[0]):
            return SymbolDQResult(
                run_id=rid,
                timestamp=now_iso,
                symbol=sym,
                passed=False,
                failure_reason="FIRST_BAR_MISSING",
                last_bar_date=None,
                row_count=len(df),
                coverage_pct=0.0,
                has_stale_ta=False,
            )

        row_count = len(df)
        first_date = df.index.min().date()
        last_date = df.index.max().date()
        last_date_str = last_date.isoformat()
        trading_day = _last_trading_day(ref_date)

        # 3. recency
        allowed_stale_cutoff = trading_day - timedelta(days=self.max_stale_days)
        if last_date < allowed_stale_cutoff:
            return SymbolDQResult(
                run_id=rid,
                timestamp=now_iso,
                symbol=sym,
                passed=False,
                failure_reason="DATA_STALE",
                last_bar_date=last_date_str,
                row_count=row_count,
                coverage_pct=0.0,
                has_stale_ta=False,
            )

        # 4. coverage
        expected_rows = SyncRegistry._estimate_trading_days(first_date, trading_day)
        coverage_pct = round(row_count / expected_rows, 4) if expected_rows > 0 else 1.0
        # Meaningful history threshold (50 trading days)
        if expected_rows > 50 and coverage_pct < self.min_coverage_pct:
            return SymbolDQResult(
                run_id=rid,
                timestamp=now_iso,
                symbol=sym,
                passed=False,
                failure_reason="LOW_COVERAGE",
                last_bar_date=last_date_str,
                row_count=row_count,
                coverage_pct=coverage_pct,
                has_stale_ta=False,
            )

        # 5. ohlcv_validity
        req_ohlcv = {"Open", "High", "Low", "Close", "Volume"}
        if not req_ohlcv.issubset(df.columns) or any(pd.isna(df[c].iloc[-1]) for c in req_ohlcv):
            return SymbolDQResult(
                run_id=rid,
                timestamp=now_iso,
                symbol=sym,
                passed=False,
                failure_reason="OHLCV_INVALID",
                last_bar_date=last_date_str,
                row_count=row_count,
                coverage_pct=coverage_pct,
                has_stale_ta=False,
            )

        # 6. canonical_ta (RSI_14)
        has_stale_ta = False
        if row_count >= 15:
            if "RSI_14" not in df.columns or pd.isna(df["RSI_14"].iloc[-1]):
                has_stale_ta = True
                if self.fail_on_stale_ta:
                    return SymbolDQResult(
                        run_id=rid,
                        timestamp=now_iso,
                        symbol=sym,
                        passed=False,
                        failure_reason="STALE_TA",
                        last_bar_date=last_date_str,
                        row_count=row_count,
                        coverage_pct=coverage_pct,
                        has_stale_ta=True,
                    )

        return SymbolDQResult(
            run_id=rid,
            timestamp=now_iso,
            symbol=sym,
            passed=True,
            failure_reason=None,
            last_bar_date=last_date_str,
            row_count=row_count,
            coverage_pct=coverage_pct,
            has_stale_ta=has_stale_ta,
        )

    def check_batch(
        self,
        symbols: list[str],
        hist_dir: str | Path,
        stage: str = "unknown",
        run_id: str | None = None,
        halt_on_breach: bool = True,
        write_audit: bool = True,
        ref_date: date | None = None,
    ) -> BatchDQResult:
        """Run assertion checks across a collection of symbols with audit logging."""
        t0 = time.perf_counter()
        rid = run_id or str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        results: list[SymbolDQResult] = []
        for s in symbols:
            res = self.check_symbol(s, hist_dir, run_id=rid, ref_date=ref_date)
            results.append(res)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        failure_pct = round(failed / total, 4) if total > 0 else 0.0
        halt_triggered = failure_pct > self.halt_if_failure_pct
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        batch_result = BatchDQResult(
            run_id=rid,
            timestamp=now_iso,
            stage=stage,
            total_symbols=total,
            passed_count=passed,
            failed_count=failed,
            failure_pct=failure_pct,
            halt_triggered=halt_triggered,
            duration_ms=duration_ms,
            symbol_results=results,
        )

        if write_audit:
            self._write_audit(batch_result)

        if halt_on_breach and halt_triggered:
            raise DataQualityHalt(
                f"Data Quality Gate breach in stage '{stage}': "
                f"{failed}/{total} symbols failed ({failure_pct:.1%}), "
                f"exceeding halt threshold of {self.halt_if_failure_pct:.1%}."
            )

        return batch_result

    def _write_audit(self, batch_result: BatchDQResult) -> None:
        """Append run and symbol records to logs/dq."""
        try:
            self.audit_dir.mkdir(parents=True, exist_ok=True)
            runs_file = self.audit_dir / "runs.jsonl"
            symbols_file = self.audit_dir / "symbols.jsonl"

            run_dict = {
                "run_id": batch_result.run_id,
                "timestamp": batch_result.timestamp,
                "stage": batch_result.stage,
                "total_symbols": batch_result.total_symbols,
                "passed_count": batch_result.passed_count,
                "failed_count": batch_result.failed_count,
                "failure_pct": batch_result.failure_pct,
                "halt_triggered": batch_result.halt_triggered,
                "duration_ms": batch_result.duration_ms,
            }

            with open(runs_file, "a", encoding="utf-8") as rf:
                rf.write(json.dumps(run_dict) + "\n")

            with open(symbols_file, "a", encoding="utf-8") as sf:
                for sym_res in batch_result.symbol_results:
                    s_dict = asdict(sym_res)
                    sf.write(json.dumps(s_dict) + "\n")
        except Exception as exc:
            LOGGER.warning("Failed to write Data Quality Gate audit logs: %s", exc)
