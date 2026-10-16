# Data Quality Gate — CI & Scheduler Integration

This document outlines the invocation modes, automation hooks, and exit-code contracts for the Data Quality Gate (`src/storage/dq_gate.py`).

---

## 1. Invocation Modes

The DQ gate can be executed in three operational environments:

### a) Manual Invocation
For ad-hoc verification by developers and operators:
```bash
./scripts/dq_gate.sh
```
Any optional CLI flags are passed directly through to `main.py dq-check`:
```bash
# Include inactive symbols in halt calculation:
./scripts/dq_gate.sh --include-inactive

# Override inactivity threshold (e.g. 180 days):
./scripts/dq_gate.sh --min-last-trade-days 180
```

### b) Cron / Headless Scheduler
For scheduled batch runners and automated daily operations without a TTY:
```crontab
# Runs at 02:00 IST (20:30 UTC), Monday through Friday, after the NSE evening sync window
30 20 * * 1-5 /path/to/learning/scripts/dq_gate_watch.sh
```
`scripts/dq_gate_watch.sh` appends all stdout and stderr to `logs/dq/dq_gate_cli.log`, prefixing each line with an ISO-8601 timestamp (using `ts` if installed, or falling back to a `sed` prefix).

### c) CI Runner (GitHub Actions)
Configured at `.github/workflows/dq-check.yml`:
- **Triggers:** `workflow_dispatch` (manual) and `schedule` (nightly at 20:30 UTC / 02:00 IST).
- **Behavior:** Syncs dependencies via `uv`, executes `./scripts/dq_gate.sh`, and archives `logs/dq/*.jsonl` audit records as workflow artifacts upon any halt or failure.
- **Note:** The workflow is intentionally not wired to `push` or `pull_request` triggers because standard ephemeral CI environments lack the on-disk historical dataset (`data/historical/1d/*.parquet`).

---

## 2. Post-Sync Hook vs. Standalone Verification

The data pipeline already enforces data quality internally:
- Ingestion pipelines (`bhavcopy-sync` / `bhavcopy_incremental.run` and `sync-history` / `historical_sync.sync`) automatically invoke the gate at the conclusion of their execution batch (Unit 17).
- Individual symbol mutations (`sync_one`) perform per-symbol audit logging without halting the entire batch.

`scripts/dq_gate.sh` is designed for **standalone disk-state verification** (e.g., pre-market readiness checks, post-maintenance sanity checks, and scheduled audit runs). It should **not** be wrapped as an unconditional post-command hook after sync commands, as doing so would cause redundant double-evaluation.

---

## 3. Exit Code Contract

All wrapper scripts strictly propagate exit codes according to the following contract:

| Exit Code | Meaning | Action Required |
|:---:|:---|:---|
| **`0`** | **Healthy** | Data universe is within operational tolerance (failure rate < configured threshold). |
| **`1`** | **Halt Condition Met** | Critical data quality breach detected; downstream consumption must stop. Check `logs/dq/symbols.jsonl`. |
| **`2`** | **Script Error** | Environmental or execution failure (e.g., `uv` missing from PATH, missing root directory). |
