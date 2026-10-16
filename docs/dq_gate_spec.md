# Data Quality Gate & Audit Log Specification (Unit 17)

## 1. Overview & Objectives

The Data Quality Gate (`DataQualityGate`) provides an automated, deterministic verification checkpoint between data ingestion/mutation stages and downstream quantitative consumers.

Its primary objectives:
1. Prevent corrupted, stale, or partially enriched Parquet data from reaching downstream screeners, SMC models, backtesters, and LLM dossiers.
2. Produce a durable, queryable, append-only JSONL audit trail under `logs/dq/` for observability and forensic debugging.
3. Enforce configurable halt-on-breach policies while allowing granular tolerance controls.

---

## 2. Gate Placement & Function Call Sites

The Gate must be invoked in the following three mutating pipeline methods:

### 1. `src/storage/historical_sync.py :: sync_one()` (Per-Symbol)
- **Call Context:** Called immediately after an individual symbol's Parquet file has been written to disk in `_save()`.
- **Target:** Single symbol (`symbol: str`).
- **Stage Identifier:** `"historical_sync.sync_one"`.
- **Behavior:** Evaluates assertions on the written Parquet. If failed, logs a structured warning and appends a record to `logs/dq/symbols.jsonl`. It does **not** halt execution mid-batch, ensuring other symbols continue processing.

### 2. `src/storage/historical_sync.py :: sync()` (Batch Summary)
- **Call Context:** Called at the completion of a multi-symbol historical backfill or update batch.
- **Target:** All symbols touched during the sync run (`symbols: list[str]`).
- **Stage Identifier:** `"historical_sync.sync"`.
- **Behavior:** Aggregates symbol results, computes batch breach rates, appends summary to `logs/dq/runs.jsonl`, and raises `DataQualityHalt` if the failure rate exceeds the configured threshold.

### 3. `src/storage/bhavcopy_incremental.py :: run()` (Batch Summary)
- **Call Context:** Called at the end of the daily incremental Bhavcopy batch run.
- **Target:** All symbols updated by the run (`symbols: list[str]`).
- **Stage Identifier:** `"bhavcopy_incremental.run"`.
- **Behavior:** Verifies that all newly appended Parquets are fresh and have non-NaN indicators, appends to `logs/dq/runs.jsonl`, and halts if failure threshold is breached.

---

## 3. Assertions per Symbol

For every symbol evaluated, the gate executes 6 atomic assertions, each returning a boolean pass/fail status and an explicit diagnostic reason code:

| Assertion | Check Predicate | Failure Reason Code | Failure Message Example |
| :--- | :--- | :--- | :--- |
| **1. `file_exists`** | `os.path.isfile(parquet_path)` | `FILE_MISSING` | `Parquet file does not exist at data/historical/1d/TCS.parquet` |
| **2. `first_bar_present`** | `len(df) > 0 and pd.notna(df.index[0])` | `FIRST_BAR_MISSING` | `Parquet dataframe is empty or missing valid DatetimeIndex` |
| **3. `recency`** | `last_bar_date >= last_trading_day - max_stale_days` | `DATA_STALE` | `Last bar 2026-06-08 is 90 days behind last trading day 2026-10-15` |
| **4. `coverage`** | `row_count >= min_coverage_pct * expected_rows` | `LOW_COVERAGE` | `Row count 150 < 85% of expected 250 trading days` |
| **5. `ohlcv_validity`** | `{"Open", "High", "Low", "Close", "Volume"}.issubset(df.columns)` and `not pd.isna(df[col].iloc[-1])` | `OHLCV_INVALID` | `Column 'Volume' has null value on latest bar 2026-10-15` |
| **6. `canonical_ta`** | `"RSI_14" in df.columns and not pd.isna(df["RSI_14"].iloc[-1])` | `STALE_TA` | `Canonical indicator RSI_14 is NaN on latest bar 2026-10-15` |

---

## 4. Configuration Specification (`config/dq_config.json`)

Configuration is managed declaratively via JSON with the following production defaults:

```json
{
  "min_coverage_pct": 0.85,
  "max_stale_days": 3,
  "fail_on_stale_ta": true,
  "halt_if_failure_pct": 0.05,
  "audit_dir": "logs/dq",
  "retention_days": 90
}
```

### Parameter Reference
- `min_coverage_pct` (float, default `0.85`): Minimum ratio of actual bars to expected trading days (derived from `SyncRegistry._estimate_trading_days` and `config/holidays.json`).
- `max_stale_days` (int, default `3`): Maximum allowed calendar days between the latest candle and the most recent market trading day.
- `fail_on_stale_ta` (bool, default `true`): When true, a trailing NaN on `RSI_14` causes a symbol failure.
- `halt_if_failure_pct` (float, default `0.05`): Ratio of failed symbols in a batch required to trigger an immediate pipeline halt (0.05 = 5%).
- `audit_dir` (str, default `"logs/dq"`): Target directory for JSONL audit trails.
- `retention_days` (int, default `90`): Rolling retention window for audit logs.

---

## 5. Explicit Failure Policy

### Per-Symbol Level
- If a single symbol fails any assertion, it is marked as `failed` in the audit log.
- `historical_sync.sync_one` records the failure and returns `SymbolDQResult(passed=False, ...)`. Single-symbol processing does not abort the broader batch.

### Batch Level
- At the end of `sync()` or `run()`, the gate calculates:
  $$\text{failure\_rate} = \frac{\text{failed\_symbols}}{\text{total\_symbols\_checked}}$$
- **Halt Condition:** If $\text{failure\_rate} > \text{halt\_if_failure\_pct}$, the gate raises `DataQualityHalt`.
- `main.py` catches `DataQualityHalt`, logs an alert, and exits with return code `1`.
- **Policy Control Flags:**
  - `halt_if_failure_pct = 0.0`: Strict Mode — halt on *any* single failure.
  - `halt_if_failure_pct = 0.05`: Default Balanced Mode — tolerate up to 5% failure (e.g., illiquid/suspended symbols) before halting.
  - `halt_if_failure_pct = 1.0`: Permissive Mode — warn only, never halt execution.

> **POLICY CHOICE NOTE:** The default of `0.05` (5%) is an explicit policy choice allowing minor market exceptions (e.g., suspended or newly listed stocks) without freezing automated pipelines, while reliably halting if systemic ingestion breaks (such as the Unit 15 stale-TA incident affecting 80%+ of files). Review and calibrate before production deployments.

---

## 6. Audit Log Format & JSON Schemas

The gate writes to two append-only JSONL files under `logs/dq/`:
1. `runs.jsonl`: One entry per gate execution.
2. `symbols.jsonl`: One entry per symbol inspected.

Every symbol record contains `run_id`, allowing joins in DuckDB:
```sql
SELECT r.stage, s.symbol, s.failure_reason
FROM read_json_auto('logs/dq/symbols.jsonl') s
JOIN read_json_auto('logs/dq/runs.jsonl') r ON s.run_id = r.run_id
WHERE s.passed = false;
```

### `runs.jsonl` Schema
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DQRunRecord",
  "type": "object",
  "required": [
    "run_id",
    "timestamp",
    "stage",
    "total_symbols",
    "passed_count",
    "failed_count",
    "failure_pct",
    "halt_triggered",
    "duration_ms"
  ],
  "properties": {
    "run_id": { "type": "string", "description": "UUID4 or timestamped run identifier" },
    "timestamp": { "type": "string", "format": "date-time" },
    "stage": { "type": "string", "enum": ["historical_sync.sync_one", "historical_sync.sync", "bhavcopy_incremental.run", "cli.dq-check"] },
    "total_symbols": { "type": "integer" },
    "passed_count": { "type": "integer" },
    "failed_count": { "type": "integer" },
    "failure_pct": { "type": "number" },
    "halt_triggered": { "type": "boolean" },
    "duration_ms": { "type": "number" }
  }
}
```

### `symbols.jsonl` Schema
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DQSymbolRecord",
  "type": "object",
  "required": [
    "run_id",
    "timestamp",
    "symbol",
    "passed",
    "failure_reason",
    "last_bar_date",
    "row_count",
    "coverage_pct",
    "has_stale_ta"
  ],
  "properties": {
    "run_id": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "symbol": { "type": "string" },
    "passed": { "type": "boolean" },
    "failure_reason": { "type": ["string", "null"] },
    "last_bar_date": { "type": ["string", "null"] },
    "row_count": { "type": "integer" },
    "coverage_pct": { "type": "number" },
    "has_stale_ta": { "type": "boolean" }
  }
}
```

---

## 7. Standalone CLI Specification (`dq-check`)

A standalone CLI command `dq-check` is provided to allow operators and cron jobs to audit historical storage on demand.

### Syntax
```bash
uv run python main.py [--hist-dir HIST_DIR] dq-check
```

### CLI Output & Exit Codes
- Scans all `{SYMBOL}.parquet` files in `data/historical/1d`.
- Evaluates the 6 assertions against each file.
- Appends run and symbol records to `logs/dq/`.
- Emits a concise one-line summary:
  ```text
  DQ: 2694 symbols checked, 2694 healthy, 0 stale, 0 missing TA. Log: logs/dq/runs.jsonl
  ```
- **Exit Code:**
  - `0`: Passed (failure percentage $\le$ `halt_if_failure_pct`).
  - `1`: Failed (failure percentage $>$ `halt_if_failure_pct`).
