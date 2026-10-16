# NSE Pipeline System Architecture & ETL Data Flow

## 1. Overview & Architectural Principle

The NSE Data Pipeline operates as a deterministic, batch-oriented, linear ETL (Extract, Transform, Load) system designed to maintain an institutional-grade universe of 2,600+ equities traded on the National Stock Exchange of India (NSE).

Previously, data health checks (`DataHealthCheck`, `TAValidator`, `SmartDataRepairer`, `SyncRegistry.coverage_pct`) operated as on-demand, interactive utilities in the CLI menu rather than automated, inline pipeline guards. The **Unit 17 Data Quality Gate** rectifies this by inserting an inline, non-bypassable checkpoint immediately after every mutating storage write.

---

## 2. Linear ETL Data Flow

```text
  +-----------------------------------------------------------------------------+
  |                             SOURCE ADAPTERS                                  |
  |             (Registered in src/core/data_sources.py & fetchers)             |
  |  - NSE Bhavcopy Downloader (Daily ZIP archive via direct HTTPS)             |
  |  - Fyers Broker API (Live Quotes, Multi-Timeframe Historical REST)          |
  |  - NSE Public Indices API (Nifty 50/100/500/Sectoral Constituents)          |
  +-----------------------------------------------------------------------------+
                                       |
                                       v
  +-----------------------------------------------------------------------------+
  |                           STAGE 1: RAW INGESTION                             |
  |                          Directory: data/raw/                               |
  |  - Raw Daily Bhavcopy ZIP archives: BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.zip|
  |  - Token and credential caches: .fyers_token, fyers_token.json              |
  |  - Cached raw master files: sec_list.csv, index_*.csv                       |
  +-----------------------------------------------------------------------------+
                                       |
                                       v
  +-----------------------------------------------------------------------------+
  |                     STAGE 2: EXTRACTION & INTERMEDIATE                      |
  |                       Directory: data/processed/                            |
  |  - Daily filtered trade universes: final_list_YYYYMMDD.csv                  |
  |  - Screener pre-analysis outputs: top_250_analyzed_YYYYMMDD.csv             |
  |  - Enriched multi-factor outputs: top_250_enriched_YYYYMMDD.csv             |
  +-----------------------------------------------------------------------------+
                                       |
                                       v
  +-----------------------------------------------------------------------------+
  |                STAGE 3: PARQUET STORAGE & TA ENRICHMENT                     |
  |                    Directory: data/historical/1d/                           |
  |  - Per-symbol OHLCV DatetimeIndex Parquet files: {SYMBOL}.parquet           |
  |  - Inline TA indicator columns (RSI_14, SMA_50, SMA_200, MACD, ATR, ADX)    |
  |  - Ingestion mechanisms:                                                    |
  |      * historical_sync.py (Initial backfill & deep symbol catch-up)         |
  |      * bhavcopy_incremental.py (Daily batch multi-symbol append)            |
  +-----------------------------------------------------------------------------+
                                       |
                   ========================================
                   ||      MANDATORY DATA QUALITY GATE   ||
                   ||    (src/storage/dq_gate.py)        ||
                   ========================================
                                       |
                +----------------------+----------------------+
                |                                             |
         [Checks Passed]                               [Halt Triggered]
                |                                             |
                v                                             v
  +---------------------------+                 +---------------------------+
  |    DOWNSTREAM CONSUMERS   |                 |       PIPELINE HALT       |
  | - Technical Screener      |                 | - Non-zero exit code (1)  |
  | - SMC Scanner Engine      |                 | - Execution aborted       |
  | - ML Anomaly & Classifier |                 | - Audit log in logs/dq/   |
  | - Streamlit Dashboard     |                 +---------------------------+
  | - LLM Dossier Generator   |
  +---------------------------+
```

---

## 3. Mandatory Checkpoints & Placement

The Data Quality Gate intercepts execution at the following three distinct mutation boundaries:

```text
Write Boundary                                     Gate Interception Point                Action on Breach
-------------------------------------------------  -------------------------------------  -------------------------
1. Per-Symbol Deep Sync                            historical_sync.sync_one()             Warn & Record in symbols.jsonl
   (Individual Parquet updated/created)

2. Batch Deep Sync                                 historical_sync.sync()                 Halt run if breach > threshold
   (Full backfill batch finishes)                                                         Record in runs.jsonl

3. Incremental Bhavcopy Append                     bhavcopy_incremental.run()            Halt run if breach > threshold
   (Daily batch appends across symbols finish)                                            Record in runs.jsonl
```

### Invalidation & Interception Guarantee
1. **Per-Symbol Check (`sync_one`):** Validates existence, bar freshness, row count relative to expected trading days, and non-NaN state of core TA indicators (`RSI_14`). Failures are logged and recorded in the audit trail without terminating single-symbol processing.
2. **Batch Check (`sync` and `run`):** Aggregates failure rates across the entire run. If the failure percentage exceeds `halt_if_failure_pct` (default `5%`), a `DataQualityHalt` exception is raised, triggering an immediate non-zero exit (`sys.exit(1)`).
3. **Audit Log:** Every execution appends structured JSONL events to `logs/dq/runs.jsonl` and `logs/dq/symbols.jsonl`, enabling SQL/DuckDB inspection and automated monitoring.
