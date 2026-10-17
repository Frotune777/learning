# NSE Platform CRUD Contract & DAL Specifications

**Status:** Authoritative Data Governance Contract  
**Purpose:** Formalize mutation, retrieval, and lifecycle boundaries for all data entities, establishing the `src/platform/dal.py` API and eliminating ad-hoc filesystem mutations.

---

## 1. Concurrency & Execution Model

- **Single-Writer Invariant:** The platform operates under a single-operator local execution model. Only one pipeline job may hold write access to `data/warehouse.duckdb` at any given millisecond.
- **Transactional Atomicity:** All writes use ACID transactions (`BEGIN TRANSACTION ... COMMIT`).
- **Parallel Workers:** CPU-bound indicator calculations (e.g., Savitzky-Golay, Weinstein stage, NWE envelopes in `src/engine/parallel_scanner.py`) run as stateless parallel workers across CPU cores, returning Arrow record batches or DataFrames in-memory to the single orchestrator process, which serializes the write into DuckDB.
- **Lock Management:** DuckDB provides internal file locking (`database is locked` error on concurrent writers). The `src/platform/orchestrator.py` provides process-level mutual exclusion using a PID file lock (`data/.warehouse.lock`).

---

## 2. Entity CRUD Contracts

### 2.1 Symbol (`dim_symbol`)
Represents equity security identity, ISIN mapping, series, and status.

- **Create Semantics:**
  - *Trigger:* Ingested from Bhavcopy headers or `NSEEquityMasterBuilder`.
  - *Idempotency Key:* `(symbol, isin, series)`.
  - If a new symbol is detected, a new row is created with `is_current = TRUE`, `valid_from = trade_date`, `valid_to = '9999-12-31'`.
- **Read Semantics:**
  - `DAL.get_symbol(symbol: str, as_of: date | None = None) -> SymbolDTO`: Returns current or point-in-time symbol metadata.
  - `DAL.get_active_universe() -> list[str]`: Returns all currently active equity symbols (`is_active = TRUE AND is_current = TRUE AND series = 'EQ'`).
  - `DAL.get_inactive_universe() -> pd.DataFrame`: Returns all inactive or delisted symbols with classification and last trade date.
- **Update Semantics:**
  - **SCD Type 2:** Direct in-place update of `company_name`, `isin`, or `series` is strictly forbidden.
  - When metadata changes, the existing row has `valid_to` set to `trade_date - 1` and `is_current` set to `FALSE`. A new row is inserted with updated values, `is_current = TRUE`, and `valid_from = trade_date`.
- **Delete Semantics:**
  - Hard deletes are **forbidden**.
  - Inactive/delisted symbols are soft-transitioned: `is_active` set to `FALSE`, `classification` set to `'INACTIVE'` or `'DELISTED'`.

---

### 2.2 Price (`fact_price_daily`)
Granular unadjusted daily OHLCV bar records.

- **Create Semantics:**
  - *Trigger:* Daily Bhavcopy sync or historical backfill.
  - *Idempotency Key:* `(symbol_sk, date_sk)`.
  - Written via staging Parquet files with validated schema.
- **Read Semantics:**
  - `DAL.get_price_history(symbol: str, start_date: date, end_date: date) -> pd.DataFrame`: Returns sorted time series with unadjusted OHLCV.
  - `DAL.get_latest_prices(trade_date: date) -> pd.DataFrame`: Returns full market snapshot for a given day.
- **Update Semantics:**
  - Mutable only via upsert: If an official NSE Bhavcopy revision occurs for a past trade date, re-ingestion with an updated `batch_id` updates prices in-place via `ON CONFLICT (symbol_sk, date_sk) DO UPDATE`.
- **Delete Semantics:**
  - Hard deletion is only permitted during a deliberate re-sync of a specific batch: `DELETE FROM fact_price_daily WHERE batch_id = ?`.

---

### 2.3 Technical Indicators (`fact_ta_daily`)
Computed technical indicator values derived from `src/engine/`.

- **Create Semantics:**
  - *Trigger:* Post-ingestion analytical calculation step in `orchestrator.py`.
  - *Idempotency Key:* `(symbol_sk, date_sk)`.
  - Generated purely deterministically from price history.
- **Read Semantics:**
  - `DAL.get_ta_history(symbol: str, start_date: date, end_date: date) -> pd.DataFrame`: Returns moving averages, Weinstein stages, NWE bands, ADX, RSI.
  - `DAL.get_enriched_bar(symbol: str, trade_date: date) -> EnrichedBarDTO`: Combines price + TA for a single symbol.
- **Update Semantics:**
  - Fully recomputable. If an indicator calculation formula in `src/engine/` is updated, the orchestrator re-runs calculations and overwrites `fact_ta_daily` via upsert.
- **Delete Semantics:**
  - Can be purged and recomputed at any time without data loss.

---

### 2.4 Delivery (`fact_delivery_daily`)
Official security delivery statistics from NSE settlement reports.

- **Create Semantics:**
  - *Trigger:* Evening Bhavcopy sync (`bhavcopy_incremental.py`).
  - *Idempotency Key:* `(symbol_sk, date_sk)`.
  - Delivery percentage must satisfy `0.0 <= delivery_pct <= 100.0`.
- **Read Semantics:**
  - `DAL.get_delivery_history(symbol: str, lookback_days: int = 50) -> pd.DataFrame`.
- **Update Semantics:**
  - In-place overwrite allowed only during formal settlement adjustments.
- **Delete Semantics:**
  - Soft retention permanent; hard delete forbidden.

---

### 2.5 Signal & SMC Setups (`fact_signal_daily`)
Trading strategy recommendations and Smart Money Concept (SMC) calls.

- **Create Semantics:**
  - *Trigger:* Daily screener run (`cmd_screen`) or SMC scanner (`cmd_smc_scan`).
  - *Idempotency Key:* `(symbol_sk, date_sk, strategy_code)`.
  - Carries entry price, invalidation stop, target, and `details_json`.
- **Read Semantics:**
  - `DAL.get_active_signals(strategy_code: str | None = None) -> pd.DataFrame`: Returns live actionable setups.
  - `DAL.get_smc_calls(status: str = 'ACTIVE') -> list[TradingCall]`: Returns SMC calls with full order block coordinates.
- **Update Semantics:**
  - Status updates (`ACTIVE` -> `TARGET_REACHED`, `STOPPED_OUT`, `EXPIRED`) occur via `SignalRepo.update_signal_status(signal_id, new_status, exit_price)`.
- **Delete Semantics:**
  - Historical signals are immutable and preserved for backtesting validation.

---

### 2.6 Data Quality Run (`fact_dq_run`)
Audit run logs from Data Quality Gate inspections.

- **Create Semantics:**
  - *Trigger:* Standalone `scripts/dq_gate.sh`, CLI `dq-check`, or post-sync gate assertion.
  - *Idempotency Key:* `run_id` (UUIDv4).
  - Write-once audit record.
- **Read Semantics:**
  - `DAL.get_latest_dq_run() -> DQRunDTO`: Returns the most recent full-universe run (`total_symbols >= 1000`).
  - `DAL.get_dq_run_history(limit: int = 20) -> pd.DataFrame`: Returns recent runs for UI history tables.
- **Update Semantics:**
  - **Strictly Immutable:** Audit records cannot be modified once written.
- **Delete Semantics:**
  - Hard delete forbidden. Retention indefinite.

---

### 2.7 Corporate Actions (`fact_corporate_action`)
Splits, bonus issues, dividends, rights offerings, and face value changes.

- **Create Semantics:**
  - *Trigger:* Circular ingestion from NSE corporate announcements.
  - *Idempotency Key:* `(symbol_sk, ex_date, action_type)`.
- **Read Semantics:**
  - `DAL.get_corporate_actions(symbol: str) -> list[CorporateActionDTO]`.
  - `DAL.get_adjustment_factor(symbol: str, as_of: date) -> float`: Calculates cumulative price multiplier.
- **Update Semantics:**
  - Record date and ratio corrections updated via upsert.
- **Delete Semantics:**
  - Hard delete forbidden.

---

### 2.8 Index Membership (`fact_index_membership`)
Constituent lists for Nifty 50, Nifty Next 50, Nifty 500, Sectoral indices.

- **Create Semantics:**
  - *Trigger:* Semi-annual index rebalancing announcements.
  - *Idempotency Key:* `(index_sk, symbol_sk, effective_date)`.
- **Read Semantics:**
  - `DAL.get_index_constituents(index_code: str, as_of: date = CURRENT_DATE) -> list[str]`.
- **Update Semantics:**
  - Replaced upon periodic index rebalance.
- **Delete Semantics:**
  - Point-in-time membership history retained for survivorship-bias-free backtesting.

---

## 3. Anti-Patterns in the Current Codebase

The following code patterns directly violate this platform contract and must be refactored during migration:

1. **Ad-Hoc File Mutation Without Transactions:**
   - *Violation:* `src/storage/historical_sync.py:HistoricalSync._save` loads `df = pd.read_parquet(file_path)`, concatenates new rows, and writes back directly to disk using `to_parquet`.
   - *Risk:* Power failure, thread crash, or disk-full condition during `to_parquet` corrupts the entire symbol file irreversibly.
   - *Replacement:* Ingest into `data/staging/` and execute atomic DuckDB upsert.

2. **CSV Dumps as Analytical Interfaces:**
   - *Violation:* `src/engine/screener.py` and `src/cli/actions.py:cmd_screen` dump results into `data/historical/strategy_*.csv` and `data/historical/top_250_*.csv`.
   - *Risk:* No type enforcement, dates formatted as strings, no concurrency protection, and file locks cause silent read failures in Streamlit.
   - *Replacement:* Write directly to `fact_signal_daily` and query via `DAL.get_screener_results()`.

3. **Filesystem Globbing in Dashboard Views:**
   - *Violation:* `src/dashboard/views/screener_view.py` and `dossier_view.py` use `glob.glob("data/historical/1d/*.parquet")` and `glob.glob("data/historical/top_250_*.csv")` to discover symbols and data files.
   - *Risk:* High filesystem I/O latency, brittle coupling to folder naming, and exposure to partial sync artifacts.
   - *Replacement:* Replace all globbing with `DAL.get_available_symbols()` and `DAL.get_latest_screener_results()`.

4. **Isolated SQLite Silo for SMC Signals:**
   - *Violation:* `src/storage/smc_db.py` maintains an independent SQLite database at `data/smc_calls.sqlite` with its own connection logic and schema.
   - *Risk:* Cannot join SMC calls with corporate actions, universe metadata, or data quality gate statuses.
   - *Replacement:* Unify into `warehouse.duckdb:fact_signal_daily` and `marts.smc_calls`.

5. **Direct JSONL Parsing in UI Components:**
   - *Violation:* `src/dashboard/views/dq_view.py` reads `logs/dq/runs.jsonl` line-by-line in Python and manually sorts candidate dictionaries.
   - *Risk:* Memory bloat as JSONL grows, lack of indexes, and code duplication across CLI and UI.
   - *Replacement:* `DAL.get_latest_dq_run()` backed by indexed DuckDB queries.

---

## 4. Decisions Pending Operator Input

1. **DAL Return Format Standard:**
   - *Option A (Recommended):* Methods return strongly-typed Dataclasses / Pydantic models for single entities (`SymbolDTO`, `DQRunDTO`) and zero-copy Apache Arrow tables / Polars / Pandas DataFrames for large time-series.
   - *Option B:* Strict Pandas DataFrames for all returns (maximum legacy compatibility, higher memory footprint).
2. **Signal Retention Horizon:**
   - *Option A (Recommended):* Retain all generated strategy and screener signals permanently in `fact_signal_daily` (~500k rows/year, ~20MB compressed). Enables walk-forward strategy evaluation.
   - *Option B:* Retain only the last 365 days of signals, purging older records automatically.
