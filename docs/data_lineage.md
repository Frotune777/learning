# NSE Pipeline Data Lineage & Artifact Mapping

## 1. Overview

This document defines the core data artifacts that establish identity, trading calendar bounds, synchronization state, and exchange token mappings across the NSE Data Pipeline.

Per architectural policy, these artifacts maintain distinct responsibilities and lifecycles. They are **not** to be prematurely consolidated.

---

## 2. Core Master Artifacts

### 1. Equity Master Table (`data/nse_equity_master_YYYYMMDD.parquet`)
- **Purpose:** Primary reference directory of all NSE equities, establishing index memberships (Nifty 50, Next 50, Midcap, Smallcap, Sectoral indices) and market capitalization classifications.
- **Producer:** `src/storage/equity_master.py` (`NSEEquityMasterBuilder.build_and_save()`, via CLI `build-master`).
- **Consumer(s):**
  - `src/screener.py` (`StockScreener` universe definition)
  - `src/storage/historical_sync.py` (`HistoricalSync` symbol universe)
  - `src/dashboard/` (Interactive filters and category breakdowns)
- **Update Cadence:** Weekly or on-demand when NSE publishes updated constituent lists.
- **Format:** Parquet + CSV mirrors (`data/nse_equity_master_*.csv`).
- **Schema Keys:**
  - `Symbol` (str, primary key)
  - `Series` (str, e.g. "EQ", "BE")
  - `SecurityName` (str)
  - `Band` (int / float)
  - Index membership flags: `is_nifty_50`, `is_nifty_100`, `is_nifty_200`, `is_nifty_500`, `is_nifty_bank`, `is_nifty_it`, etc. (bool)
  - `market_cap_category` (str: "Large", "Mid", "Small", "Other")
  - `last_price`, `ffmc`, `total_traded_value`, `total_traded_volume` (float)
  - `updated_at` (str / ISO timestamp)

---

### 2. NSE Trading Calendar (`config/holidays.json`)
- **Purpose:** Authoritative source of truth for official NSE market holidays (trading closures on weekdays). Used to compute expected trading days, calendar continuity, and detect genuine data gaps.
- **Producer:** Maintained in project config; initialized from `TAValidator._get_fallback_holidays()` during Unit 15.
- **Consumer(s):**
  - `src/data/health.py` (`DataHealthCheck`)
  - `src/analysis/TAValidator.py` (`TAValidator`)
  - `src/storage/sync_registry.py` (`SyncRegistry._estimate_trading_days`)
  - `src/storage/dq_gate.py` (`DataQualityGate`)
- **Update Cadence:** Annual (updated whenever NSE releases the official holiday circular).
- **Format:** JSON Array of ISO 8601 date strings.
- **Schema Keys:** `["YYYY-MM-DD", ...]` (e.g., `["2026-01-26", "2026-03-03", "2026-03-20", ...]`).

---

### 3. NSE Charting Token Cache (`data/metadata/nse_tokens.json`)
- **Purpose:** Maps standard ticker symbols to numerical security tokens required by NSE web APIs for historical charting and live market depth resolution.
- **Producer:** `src/data/fetcher/symbols/resolver.py` (`SymbolResolver`).
- **Consumer(s):**
  - `SymbolResolver`
  - `NSEChartFetcher`
  - `NSEQuoteFetcher`
- **Update Cadence:** On-demand; populated once per newly discovered symbol or refreshed when token resolution fails.
- **Format:** JSON dictionary keyed by uppercase symbol.
- **Schema Keys:**
  ```json
  {
    "TCS": {
      "token": "11536",
      "symbol": "TCS",
      "identifier": "TCSEQN",
      "updated_at": "2026-10-15T10:00:00"
    }
  }
  ```

---

### 4. Kite Instrument Registry (`user_data/instruments.csv`)
- **Purpose:** Legacy instrument catalog dump from Zerodha Kite Connect API containing historical security IDs, segment codes, and trading symbols.
- **Producer:** External download / legacy extraction from Kite Connect API endpoint (`https://api.kite.trade/instruments`).
- **Consumer(s):**
  - `src/analysis/validator.py` (`SymbolValidator.load_instruments()`)
  - `src/data/fetchers.py` (`Fetcher._get_token()`)
- **Update Cadence:** Static / legacy fallback (read-only in current pipeline).
- **Format:** CSV with headers.
- **Schema Keys:**
  - `instrument_token` (int)
  - `exchange_token` (int)
  - `tradingsymbol` (str)
  - `name` (str)
  - `last_price` (float)
  - `tick_size` (float)
  - `lot_size` (int)
  - `instrument_type` (str: "EQ", "FUT", "CE", "PE")
  - `segment` (str: "NSE", "NFO")
  - `exchange` (str)

---

### 5. Historical Sync Registry (`data/historical/sync_registry_1d.parquet`)
- **Purpose:** Durable state ledger recording the coverage, date boundaries, bar counts, and health status of all local Parquets. Enables high-speed incremental sync skipping.
- **Producer:** `src/storage/sync_registry.py` (`SyncRegistry`, updated during `HistoricalSync` and `BhavcopyIncrementalSync`).
- **Consumer(s):**
  - `src/storage/historical_sync.py` (determines `--resume` eligibility)
  - `src/storage/bhavcopy_incremental.py` (determines `detect_missing_days`)
  - `src/storage/dq_gate.py` (evaluates `row_count` against `expected_rows`)
  - CLI Interactive Menu `[7]` (Data Health & Quality Report)
- **Update Cadence:** Mutated on every sync batch and incremental execution.
- **Format:** Parquet.
- **Schema Keys:**
  - `symbol` (str, primary key)
  - `status` (str: "ok", "stale", "empty", "corrupted")
  - `first_bar_date` (datetime64[ns])
  - `last_bar_date` (datetime64[ns])
  - `row_count` (int)
  - `timeframe` (str, e.g. "1d")
  - `last_synced_at` (datetime64[ns])
  - `fail_count` (int)
  - `expected_rows` (int)
  - `last_full_refresh_at` (datetime64[ns] / nullable)

---

### 6. Sync Failure Blacklist (`data/historical/failed_symbols.csv`)
- **Purpose:** Blacklist ledger tracking symbols that failed historical ingestion repeatedly (e.g. suspended, delisted, non-trading series), preventing infinite retry cycles across sync batches.
- **Producer:** `src/storage/historical_sync.py` (`HistoricalSync._record_failed_symbol()`).
- **Consumer(s):**
  - `src/storage/historical_sync.py` (filters out blacklisted symbols during `sync()`)
  - CLI Interactive Menu `[7]` (Option `F` to inspect and clear blacklist)
- **Update Cadence:** Appended upon 3 consecutive network/parse failures for a symbol; pruned when manual reset is invoked.
- **Format:** CSV.
- **Schema Keys:**
  - `symbol` (str)
  - `failed_at` (str, ISO timestamp)
  - `reason` (str)
  - `consecutive_failures` (int)

---

## 3. Lineage Relationship Graph

```text
  [ config/holidays.json ]
            |
            v
  +--------------------+         [ NSE Public Indices ]
  |   SyncRegistry     |                    |
  |  (Coverage math)   |                    v
  +--------------------+       [ data/nse_equity_master_*.parquet ]
            |                               |
            |                               v
            |                   [ Master Symbol Universe ]
            |                               |
            +---------------+---------------+
                            |
                            v
       +-----------------------------------------+
       |   HistoricalSync / BhavcopyIncremental   |
       +-----------------------------------------+
             |                     |         |
             | (3x failures)       |         | (updates state)
             v                     |         v
     [ failed_symbols.csv ]        |   [ sync_registry_1d.parquet ]
                                   v
                      [ data/historical/1d/*.parquet ]
                                   |
                                   v
                      [ MANDATORY DATA QUALITY GATE ]
```
