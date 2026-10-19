# NSE Platform Architecture Specification

**Status:** Proposed Architecture  
**Target Scale:** Single Operator, Single Linux Workstation, ~2,700 NSE Equities, ~20 Years Daily OHLCV + TA + Corporate Actions, On-Demand & Scheduled Batches (Non-24/7).  
**Core Objective:** Replace ad-hoc disk storage and fragmented CLI access paths with an institutional, 4-layer local-first data platform, preserving the battle-tested quantitative calculation engine (`src/engine/`).

---

## 1. Executive Summary & Problem Statement

The NSE Quantitative Platform previously grew by organic accretion:
- **30+ CLI subcommands** in `main.py` and `src/cli/actions.py` directly mutating disk files.
- **5+ Disconnected Storage Formats:**
  - `data/historical/1d/*.parquet` (per-symbol historical files mutated in-place by `HistoricalSync._save` and `bhavcopy_incremental.py`).
  - `data/historical/*.csv` (ad-hoc strategy dumps, e.g., `strategy_etf_shop_*.csv`, `top_250_*.csv`).
  - `data/processed/*.csv` (legacy screener snapshots from historical dates).
  - `user_data/stock_data/` (orphaned legacy downloads).
  - `data/smc_calls.sqlite` (isolated SQLite database written by `SMCDatabase`).
  - `logs/dq/*.jsonl` (`runs.jsonl`, `symbols.jsonl` tracking data quality gate audits).
- **Zero Unified Data Access Layer (DAL):** Every consumer (Streamlit views, CLI screeners, backtests) directly traverses filesystem paths using `glob.glob`, `pd.read_parquet`, or `pd.read_csv`, resulting in schema drift, untracked mutations, and silent failures when directories change.

This specification establishes a **Four-Layer Modern Data Stack** optimized for DuckDB and Parquet on local NVMe/SSD storage, introducing schema validation, atomic ingestion, surrogate-key dimensional modeling, scheduled analytical marts, and an authoritative Data Access Layer.

---

## 2. End-to-End Platform Data Flow

```text
====================================================================================================
1. LANDING LAYER (data/landing/) — Raw, Immutable Batches, Write-Once, Full Audit Lineage
====================================================================================================
 [NSE Bhavcopy API / Zips]   [Fyers API]   [NSE Indices / Master]   [Corporate Actions / Splits]
             │                    │                   │                         │
             ▼                    ▼                   ▼                         ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ data/landing/{source}/{YYYY-MM-DD}/{batch_id}/                                                │
 │   ├── raw_payload.zip | raw_data.json | raw_bars.parquet                                       │
 │   └── manifest.json  (source, row_count, sha256_checksum, ingested_at, schema_version)         │
 └────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼ (src/platform/orchestrator.py - Stage Step)
====================================================================================================
2. STAGING LAYER (data/staging/) — Canonical Typed Tables, Idempotent, Date-Partitioned
====================================================================================================
 ┌────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ Schemas: schemas/staging/*.yaml  (Strict Pandera / Arrow type enforcement & column mapping)     │
 │ Partitioning: data/staging/{entity}/dt=YYYY-MM-DD/part_{batch_id}.parquet                      │
 │ Entities:                                                                                      │
 │   • price_daily        • delivery_daily        • corporate_actions                            │
 │   • index_membership   • holiday_calendar                                                      │
 └────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼ (src/platform/orchestrator.py - Warehouse Step)
====================================================================================================
3. WAREHOUSE LAYER (data/warehouse.duckdb) — Dimensional Model (Kimball Star Schema + SCD2)
====================================================================================================
 ┌────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ Dimensions:                                                                                    │
 │   • dim_symbol (SCD2: symbol_sk, symbol, isin, series, status, valid_from, valid_to, is_current) │
 │   • dim_date (date_sk, calendar_date, is_trading_day, holiday_name, day_of_week)                  │
 │   • dim_index (index_sk, index_code, index_name, category)                                     │
 │   • dim_source (source_sk, source_code, api_endpoint, priority)                                │
 │ Facts:                                                                                         │
 │   • fact_price_daily    (symbol_sk, date_sk, open, high, low, close, volume, vwap, batch_id)     │
 │   • fact_ta_daily       (symbol_sk, date_sk, ema_50, ema_200, rsi_14, adx_14, weinstein_stage)  │
 │   • fact_delivery_daily (symbol_sk, date_sk, delivery_qty, delivery_pct, trade_count)           │
 │   • fact_signal_daily   (symbol_sk, date_sk, strategy_sk, signal_type, confidence, score)     │
 │   • fact_dq_run         (run_id, stage, total_symbols, failure_pct, halt_triggered, ts)        │
 └────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼ (src/platform/orchestrator.py - Marts Step)
====================================================================================================
4. MARTS LAYER (data/marts/ & DuckDB Views) — High-Performance Read-Optimized Serving Layer
====================================================================================================
 ┌────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ data/marts/{mart_name}/current.parquet & DuckDB Schema: marts.*                                │
 │   • marts.enriched_daily   (Denormalized wide table: Price + Key TA + Delivery + Symbol Meta)  │
 │   • marts.consensus_daily  (Multi-strategy ranker, scoring leaderboard, regime metrics)        │
 │   • marts.smc_calls        (Active and historical Smart Money setups, OB zones, targets)       │
 │   • marts.dq_summary       (Universe health, stale triage, coverage audit ledger)              │
 └────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼ (Authoritative DAL: src/platform/dal.py)
====================================================================================================
CONSUMERS: Streamlit Dashboard Views, CLI Screeners, Strategy Backtesters, LLM Dossier
====================================================================================================
```

---

## 3. The Four-Layer Data Architecture

### Layer 1: Landing (`data/landing/`)
- **Immutability Principle:** Raw files written to landing are never modified, overwritten, or deleted during normal pipeline operations.
- **Partitioning Hierarchy:**
  ```text
  data/landing/{source}/{YYYY-MM-DD}/{batch_id}/
    ├── manifest.json
    └── payload.* (e.g. BhavCopy_NSE_CM_0_0_0_20261016_F_0000.csv.zip, fyers_daily.json)
  ```
- **Manifest Contract (`manifest.json`):**
  ```json
  {
    "batch_id": "bhavcopy_20261016_001",
    "source": "nse_bhavcopy",
    "ingested_at": "2026-10-16T13:30:15.123456Z",
    "schema_version": "1.0.0",
    "row_count": 2714,
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "source_uri": "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261016_F_0000.csv.zip",
    "metadata": {
      "trade_date": "2026-10-16",
      "market_segment": "CM"
    }
  }
  ```
- **Sources Supported:**
  1. `nse_bhavcopy`: Official daily Bhavcopy ZIPs (OHLCV + Delivery).
  2. `fyers`: Daily or intraday historical bar payload pulls from Fyers API v3.
  3. `nse_charts`: NSE public portal chart endpoints.
  4. `yfinance`: Fallback / secondary source for benchmark indices.
  5. `corporate_actions`: Official circulars, bonus/split announcements, dividend calendars.

### Layer 2: Staging (`data/staging/`)
- **Standardization & Typing:** Raw source payloads are parsed, cleansed, schema-validated, and mapped into uniform columnar Parquet format.
- **Partitioning Structure:**
  ```text
  data/staging/{entity}/dt=YYYY-MM-DD/part_{batch_id}.parquet
  ```
- **Canonical Entities:**
  1. `price_daily`: Symbol, trade date, unadjusted OHLCV, trades count.
  2. `delivery_daily`: Symbol, trade date, total traded volume, deliverable quantity, deliverable percentage.
  3. `corporate_actions`: Symbol, ex-date, action type (SPLIT, BONUS, DIVIDEND), split/bonus ratio, record date.
  4. `index_membership`: Index code (NIFTY50, NIFTY500, NIFTYBANK), symbol, weight, effective_date.
  5. `holiday_calendar`: Trade date, holiday reason, trading status (EQUITY, DERIVATIVE).

### Layer 3: Warehouse (`data/warehouse.duckdb`)
- Single local file database utilizing DuckDB's vectorized query execution and transactional storage.
- Implements a classic **Kimball Star Schema** with **Slowly Changing Dimensions (SCD Type 2)**:
  - Preserves point-in-time ticker metadata (e.g., symbol renaming, ISIN changes, index inclusion/exclusion).
  - Fact tables store granular event records keyed by integer surrogate keys (`symbol_sk`, `date_sk`).
- Native atomic transactions (`BEGIN TRANSACTION ... COMMIT`) guarantee zero partial state during daily batch updates.

### Layer 4: Marts (`data/marts/` & `marts.*` in DuckDB)
- Read-only aggregated analytical tables built for instantaneous UI dashboard loading (< 50ms) and screener operations.
- Stored as both registered DuckDB views/tables and exported Parquet files for external zero-copy tools.
- **Default Universe Filtering:** All analytical marts in Phase C filter to `is_current = TRUE AND is_tradable = TRUE` by default. Delisted entities (`is_active = FALSE`) and SME series (`listing_board = 'SME'`) are excluded from operational marts unless an explicit backtesting context requests survivorship-bias-free full-history inclusion.
- **Marts defined:**
  1. `marts.enriched_daily`: Daily full-universe view uniting unadjusted & split-adjusted price, delivery percentages, and core indicators (Weinstein stage, 10W MA slope, SMC status, ADX, RSI, ATR).
  2. `marts.consensus_daily`: Pre-calculated scoring matrix across technical strategies (Buy Low, ETF Shop, Nifty Shop, RDX, Momentum).
  3. `marts.smc_calls`: Open, active, and historical Smart Money setups with order block levels, liquidity pool targets, and invalidation stops.
  4. `marts.dq_summary`: Universe integrity metrics, stale triage lists, and data quality check historical logs.

---

## 4. Cross-Cutting Platform Modules (`src/platform/`)

The platform layer isolates physical storage from analytical business logic:

1. `src/platform/schemas.py`:
   - Registry and schema loader for `schemas/landing/*.yaml`, `schemas/staging/*.yaml`, and `schemas/warehouse/*.yaml`.
   - Validates DataFrames using PyArrow / Pandera schemas before writing to staging or loading to warehouse.
2. `src/platform/dal.py` (Data Access Layer):
   - The **single authoritative entry point** for all analytical consumers.
   - Forbids raw SQL string injection and direct filesystem paths in UI views or screener engines.
   - Provides clean Pythonic methods: `dal.get_price_history(symbol, start_date, end_date)`, `dal.get_screener_universe(as_of_date)`, `dal.get_active_smc_calls()`.
3. `src/platform/repositories/`:
   - Typed repositories encapsulating DuckDB transactions:
     - `SymbolRepo`: Manages `dim_symbol` (SCD2 lookups, surrogate key generation, historical symbol resolution).
     - `PriceRepo`: Manages `fact_price_daily` (upserts, partition loading, as-of point-in-time queries).
     - `SignalRepo`: Manages `fact_signal_daily` and strategy execution runs.
     - `DQRepo`: Manages `fact_dq_run` and per-symbol quality assertion ledgers.
4. `src/platform/migrations/`:
   - Database versioning and DDL migration runner (`001_initial_schema.sql`, `002_add_vwap.sql`).
   - Maintains `schema_migrations` table inside `warehouse.duckdb`.
5. `src/platform/lineage.py`:
   - Enforces bidirectional lineage: every row in a fact table references `batch_id`, allowing any anomalous value to be traced back to its exact `manifest.json` and raw landing file.
6. `src/platform/orchestrator.py`:
   - Linear pipeline execution runner (`Ingest -> Stage -> Warehouse -> Build Marts -> DQ Gate -> Notify`).
   - Implements strict failure isolation: if stage fails, warehouse is not touched; if DQ gate triggers halt, marts are not promoted.
7. `src/platform/exceptions.py`:
   - Typed domain exceptions: `SchemaValidationError`, `LineageIntegrityError`, `WarehouseConstraintViolation`, `DataQualityHaltError`.

---

## 5. Scope Boundaries

### In Scope
- Standardization of all market data ingestion for NSE equities and benchmark indices.
- Local-first single-node storage in DuckDB + Parquet.
- Point-in-time point-of-truth symbol management (SCD Type 2).
- Complete historical delivery data reconciliation with Bhavcopy.
- Unified Data Access Layer (DAL) replacing direct filesystem globs across UI and CLI.
- Lineage tracking from raw downloaded byte payload to dashboard UI component.

### Out of Scope
- Distributed computing clusters (Spark, Dask, Ray, Kubernetes) — unnecessary for ~13.5M daily rows (< 5GB compressed).
- Complex cloud data lakehouses (Snowflake, Databricks, BigQuery) — zero cloud dependency required for local quantitative research.
- Real-time tick-by-tick order-book matching engine or HFT latency optimization.
- Rewriting the quantitative math in `src/engine/` (`lux_*.py`, `smc.py`, `ta_indicators.py`) — existing math and indicators are sound and remain untouched.

---

## 6. Deprecation & Retirement Ledger

| Current Artifact / Path | Current Usage / Producer | Modern Replacement | Migration Path |
| :--- | :--- | :--- | :--- |
| `data/historical/1d/*.parquet` | Direct per-symbol storage mutated by `historical_sync.py` and `bhavcopy_incremental.py` | `data/staging/price_daily/` + `warehouse.duckdb:fact_price_daily` | Bulk load existing Parquets into staging -> ingest into warehouse -> archive raw files to `data/archive/legacy_parquets/`. |
| `data/historical/*.csv` | Screener strategy dumps (`strategy_*.csv`, `top_250_*.csv`) | `data/marts/consensus_daily.parquet` and `marts.enriched_daily` | Replace CSV writer in `src/engine/screener.py` with `SignalRepo.save_signals()`. |
| `data/processed/*.csv` | Historical date-stamped screen results | `warehouse.duckdb:fact_signal_daily` | One-off migration of historical signal dates to warehouse; archive folder to `data/archive/processed/`. |
| `user_data/stock_data/` | Orphaned Fyers/yfinance downloads | `data/landing/fyers/` and `data/landing/yfinance/` | Purge duplicates, extract un-ingested bars to landing, delete directory. |
| `data/smc_calls.sqlite` | SQLite DB written by `src/storage/smc_db.py` | `warehouse.duckdb:fact_signal_daily` + `marts.smc_calls` | Dump SQLite records into `fact_signal_daily`, retire `smc_db.py`. |
| `logs/dq/*.jsonl` | Append-only text logs for DQ runs | `warehouse.duckdb:fact_dq_run` and `fact_dq_symbol_check` | Parse JSONL history into `fact_dq_run`. `src/storage/dq_gate.py` writes directly to DuckDB via `DQRepo`. |
| `data/nse_equity_master_*.csv` | Multiple timestamped CSV/Parquet master dumps | `warehouse.duckdb:dim_symbol` (SCD2) | Ingest into `dim_symbol` tracking historical symbol/series transitions. |

---

## 7. Decisions Pending Operator Input

1. **Staging Retention Policy:**
   - *Option A:* Keep all daily staging Parquet files indefinitely (~150 MB/year, ~3 GB for 20 years). Enables instant external DuckDB queries without touching the main warehouse file.
   - *Option B:* Purge staging Parquets older than 30 days after successful warehouse ingestion, keeping only `data/landing/` manifests and compressed payloads.
2. **Corporate Action Adjustment Strategy:**
   - *Option A (Recommended):* Store strictly **unadjusted raw OHLCV** in `fact_price_daily` and apply split/bonus multipliers dynamically in `marts.enriched_daily` or via DAL helper views. (Preserves audit integrity against official NSE Bhavcopy).
   - *Option B:* Store both unadjusted columns (`open`, `high`, `low`, `close`) and pre-adjusted columns (`adj_open`, `adj_high`, `adj_low`, `adj_close`) directly in `fact_price_daily`.

---

## 8. Known Data Gaps

### Pre-2020 Delivery Data

`fact_delivery_daily` covers 2020-01-01 onward via NSE `sec_bhavdata_full` archives. Pre-2020 delivery is available from NSE in a different format (`MTO_*.DAT`) and is not yet ingested. The mart (`mart_enriched_daily`) will return NULL for `DELIV_PCT` before 2020.

### Impact on Analytical Results

- Composite scores in `mart_enriched_daily` are 5% lower for pre-2020 rows where delivery is a factor.
- Backtests using `DELIV_PCT` as a filter or feature should restrict to post-2020 dates.
- The scoring engine's `_score_volume()` awards neutral 50 when `DELIV_PCT` is NULL (this protection was added in Phase 3F).

### Path Forward

MTO ingestion is tracked as a deferred phase (B.7 candidate). If specific analytical needs require pre-2020 delivery, MTO is a 3-4 hour addition.

