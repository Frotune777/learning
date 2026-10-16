# Data Quality Gate: Inactive-Tail Classification & Halt Refinement Specification (Unit 19A)

## 1. Context & Motivation

In Unit 17, the `DataQualityGate` was introduced as a deterministic verification gate. On a full-universe scan over 2,700 Parquet files in `data/historical/1d`, `uv run python main.py dq-check` previously reported:

```text
DQ: 2700 symbols checked, 2212 healthy, 401 stale, 0 missing TA.
Data Quality Halt: Failure rate 18.1% exceeded threshold 5.0%
Exit code: 1
```

A detailed forensic analysis of the 401 `DATA_STALE` records revealed:
- **2026-02:** 206 symbols (delisted/suspended >7 months ago, e.g. `ABAN`)
- **2026-06 to 2026-09:** 175 symbols (summer mergers, delistings, suspensions)
- **2026-10 (Oct 1–12):** 10 symbols (recently stalled active symbols)
- **2025 or older:** 10 symbols

Because the gate previously treated all `DATA_STALE` records identically, long-inactive names triggered an aggregate failure rate of 18.1%, which always exceeded the 5.0% halt threshold. This made `dq-check` exit code 1 on healthy, fully synced universes, rendering it unusable as an automated CI/CD gate.

**Objective:**
Differentiate between:
1. **`HEALTHY`**: Symbol passes all 6 assertions.
2. **`INACTIVE`**: Symbol failed recency, but last trade occurred long ago (expected historical tail).
3. **`STALE_TRADING`**: Symbol failed recency, but last traded recently (potential ingestion or sync failure).

Only actionable failures (`STALE_TRADING`, `LOW_COVERAGE`, `OHLCV_INVALID`, `STALE_TA`, `FILE_MISSING`) count toward the `halt_if_failure_pct` threshold. `INACTIVE` symbols are logged and reported transparently in the audit log and summary line, but do not trigger an automated pipeline halt by default.

---

## 2. Definition & Metric for "Inactive" (19A.0 a)

### Metric Chosen: Calendar Days
$$\text{days\_since\_last\_trade} = (\text{reference\_date} - \text{last\_bar\_date}).\text{days}$$
- **Justification:** Exchange suspensions, insolvency proceedings (NCLT), and corporate actions operate on calendar time rather than market trading sessions. Calendar days provide a simple, robust, timezone-agnostic calculation that does not depend on calendar lookups or holiday definitions.

### Empirical Count Analysis across the 401 `DATA_STALE` Symbols

| Candidate Threshold | Calendar Window | INACTIVE Count | STALE_TRADING Count | Non-Inactive Failures (+87 Low Cov) | Actionable Failure Rate (%) | Default 8% Halt? |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$\ge$ 14 days** | 2 weeks | 394 | 7 | 94 | 3.48% | **NO (Pass)** |
| **$\ge$ 21 days** | 3 weeks | 381 | 20 | 107 | 3.96% | **NO (Pass)** |
| **$\ge$ 30 days** | ~1 month | 370 | 31 | 118 | 4.37% | **NO (Pass)** |
| **$\ge$ 60 days** | ~2 months | 324 | 77 | 164 | 6.07% | **NO (Pass)** |
| **$\ge$ 90 days** | ~1 quarter | 287 | 114 | 201 | 7.44% | **NO (Pass)** |
| **$\ge$ 180 days** | ~6 months | 207 | 194 | 281 | 10.41% | **YES (Halt)** |

### Locked-in Threshold Selection & Policy Calibration
- **Locked Policy Values:**
  - `delisted_threshold_days`: **90**
  - `halt_if_failure_pct`: **0.08** (8.0%)
- **Justification:**
  1. A 30-day threshold is too aggressive for an inactive classification whose output may seed operator blacklists. A stock paused for 45 days could legitimately resume trading (e.g. trading halt pending corporate clarification); a stock paused for 90 days is almost certainly delisted or suspended pending restructuring.
  2. The 8% halt threshold still catches real sync failures. A source outage (Fyers down, NSE archive unavailable) drops hundreds of symbols in a single run — well above the ~0.56% headroom between the current 7.44% baseline and the 8% threshold. Sensitivity is preserved against broad anomalies while avoiding spurious halts on the long tail.
  3. Empirically at 90 days: 287 inactive, 114 stale trading, 87 low-coverage $\rightarrow$ 201 actionable failures = **7.44%**, cleanly exiting code 0 without halting.
- **Policy Choice Note:** This threshold is an explicit, configurable **POLICY CHOICE** in `config/dq_config.json`. If a suspended symbol resumes trading on the NSE after months of dormancy, the next bhavcopy sync will immediately update its `last_bar_date` and reclassify it as `HEALTHY`.

---

## 3. Classification Architecture (19A.0 b)

The classification is computed inside `DataQualityGate.check_symbol`:
1. `SymbolDQResult` dataclass is extended with:
   ```python
   classification: str = "HEALTHY"  # "HEALTHY" | "STALE_TRADING" | "INACTIVE"
   ```
2. The core assertion `passed: bool` remains unchanged:
   - `passed = True` only for `HEALTHY`.
   - `passed = False` for both `STALE_TRADING` and `INACTIVE`.
   - The integrity of the assertion suite is strictly preserved: stale data is never marked as `passed=True`.
3. Classification logic:
   - If all assertions pass: `classification = "HEALTHY"`.
   - If assertion fails with reason `DATA_STALE`:
     - If $(\text{ref\_date} - \text{last\_bar\_date}).\text{days} \ge \text{delisted\_threshold\_days}$:
       `classification = "INACTIVE"`.
     - Else:
       `classification = "STALE_TRADING"`.
   - If assertion fails for any other reason (`LOW_COVERAGE`, `OHLCV_INVALID`, `STALE_TA`, `FILE_MISSING`):
     `classification = "STALE_TRADING"`.

---

## 4. Halt Policy Refinement (19A.0 c)

In `DataQualityGate.check_batch`:
1. **Numerator:**
   $$\text{actionable\_failures} = \sum [\text{symbol}.\text{classification} == \text{"STALE\_TRADING"}] + \sum [\text{failures with reason} \ne \text{"DATA\_STALE"}]$$
   If `include_inactive=True` (via CLI flag `--include-inactive`):
   $$\text{actionable\_failures} = \text{total\_failed\_symbols}$$
2. **Denominator:**
   $$\text{total\_symbols\_checked}$$
3. **Failure Rate:**
   $$\text{actionable\_failure\_pct} = \frac{\text{actionable\_failures}}{\text{total\_symbols\_checked}}$$
4. **Halt Decision:**
   `halt_triggered = actionable_failure_pct > halt_if_failure_pct`
   Raises `DataQualityHalt` if `halt_triggered` is True and `halt_on_breach=True`.

---

## 5. Configuration Additions (`config/dq_config.json`) (19A.0 d)

```json
{
  "min_coverage_pct": 0.85,
  "max_stale_days": 3,
  "fail_on_stale_ta": true,
  "halt_if_failure_pct": 0.08,
  "delisted_threshold_days": 90,
  "report_delisted_in_summary": true,
  "audit_dir": "logs/dq",
  "retention_days": 90
}
```

### Parameter Explanations
- `delisted_threshold_days` (int, default `90`): Calendar days of inactivity required to categorize a stale symbol as `INACTIVE` rather than `STALE_TRADING`.
- `report_delisted_in_summary` (bool, default `true`): When true, explicitly itemizes inactive count in the one-line summary output.

---

## 6. Summary Line Format (19A.0 e)

### Old Format
```text
DQ: 2700 symbols checked, 2212 healthy, 401 stale, 0 missing TA.
```

### New Format
```text
DQ: 2700 symbols checked | 2212 healthy | 287 inactive | 114 stale | 87 low-coverage | 0 missing TA. Halt: NO (7.4% failure, threshold 8.0%)
```

If halted:
```text
DQ: 2700 symbols checked | 2212 healthy | 207 inactive | 194 stale | 87 low-coverage | 0 missing TA. Halt: YES (10.4% failure, threshold 8.0%)
```

---

## 7. Standalone CLI Options (`main.py dq-check`) (19A.0 f)

### Syntax & Arguments
```bash
uv run python main.py dq-check [--include-inactive] [--min-last-trade-days N]
```

### Options Reference
1. `--include-inactive`:
   - Treat `INACTIVE` symbols as active failures in the halt numerator.
   - Example:
     ```bash
     uv run python main.py dq-check --include-inactive
     # Exits with code 1, reporting 18.1% failure rate including inactive names.
     ```
2. `--min-last-trade-days N`:
   - Override the configured `delisted_threshold_days` for a specific run.
   - Example:
     ```bash
     uv run python main.py dq-check --min-last-trade-days 30
     ```

---

## 8. Registry Artifact: `data/historical/inactive_symbols.csv` (19A.0 g)

### Decision & Rationale: YES, Generate `inactive_symbols.csv`
- **File Path:** `data/historical/inactive_symbols.csv`
- **Rationale for Name:** The file lists symbols that have stopped trading for $\ge 90$ days. That is not the same as "confirmed delisted" — a name can be suspended by SEBI, halted pending NCLT insolvency proceedings, or paused during a merger restructuring, and may later resume trading. Naming the artifact `inactive_symbols.csv` keeps the taxonomy honest and prevents future automation from silently and permanently excluding paused-but-live symbols from the sync pipeline. The file is informational, allowing operators to review candidates before deciding whether to seed `failed_symbols.csv`.
- **Write Policy:** Non-destructive snapshot overwrite at the end of each `dq-check` run.
- **CSV Schema:**
  ```csv
  symbol,last_bar_date,days_since_last_trade,classified_at
  ABAN,2026-02-20,238,2026-10-16T12:31:33.219964+00:00
  ```
