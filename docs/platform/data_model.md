# NSE Platform Data Model Specification

**Status:** Proposed Dimensional Model  
**Target Engine:** DuckDB 1.0+ (`data/warehouse.duckdb`)  
**Design Methodology:** Kimball Star Schema with Slowly Changing Dimensions (SCD Type 2)  
**Scale Envelope:** ~2,700 Active & Inactive NSE Symbols, 20 Years (2006–2026), ~5,000 Trading Days, ~13.5M Daily Price/TA Rows.

---

## 1. Key Architectural Conventions

1. **Surrogate vs. Natural Keys:**
   - **Dimension Tables:** Use integer surrogate keys (`*_sk`, e.g., `symbol_sk`, `date_sk`, `index_sk`). Surrogate keys insulate fact tables from upstream upstream symbol renaming (e.g., `MINDTREE` -> `LTIM`, `TATAMOTORS_DVR` cancellation).
   - **Fact Tables:** Natural business keys (`symbol`, `trade_date`) are retained alongside the surrogate foreign keys (`symbol_sk`, `date_sk`) for instantaneous human inspection, fast partition pruning, and ease of export.
2. **Date Keys:**
   - `date_sk` is represented as an integer in `YYYYMMDD` format (e.g., `20261016`), enabling efficient range scans, partition pruning, and integer comparison arithmetic without timestamp conversion overhead.
3. **Idempotence & Deduplication:**
   - Fact tables enforce a strict composite unique constraint on `(symbol_sk, date_sk)` or `(symbol_sk, date_sk, strategy_sk)`.
   - Ingestion pipelines utilize DuckDB's transactional staging and `INSERT INTO ... ON CONFLICT (...) DO UPDATE` construct to guarantee idempotence.

---

## 2. Dimension Tables

### 2.1 `dim_symbol` (Slowly Changing Dimension Type 2)
Tracks complete ticker lifecycle, ISIN mapping, sector classification, and status transitions over time.

| Column Name | Data Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `symbol_sk` | `BIGINT` | NO | Generated Sequence | Primary Key (Surrogate) |
| `symbol` | `VARCHAR` | NO | — | NSE Trading Symbol (e.g. `TCS`, `RELIANCE`) |
| `isin` | `VARCHAR` | YES | NULL | International Securities Identification Number |
| `company_name` | `VARCHAR` | NO | — | Registered Entity Legal Name |
| `series` | `VARCHAR` | NO | `'EQ'` | Market series (`EQ`, `BE`, `SM`, `BZ`) |
| `sector` | `VARCHAR` | YES | NULL | Primary Industry / Sector Classification |
| `macro_sector` | `VARCHAR` | YES | NULL | Broad Sector (e.g. `IT`, `Financial Services`) |
| `is_active` | `BOOLEAN` | NO | `TRUE` | Whether currently actively traded |
| `classification` | `VARCHAR` | NO | `'HEALTHY'` | Health state (`HEALTHY`, `INACTIVE`, `DELISTED`) |
| `valid_from` | `DATE` | NO | `'1990-01-01'` | Start of record validity |
| `valid_to` | `DATE` | NO | `'9999-12-31'` | End of record validity |
| `is_current` | `BOOLEAN` | NO | `TRUE` | Flag for current active record version |

- **Primary Key:** `PRIMARY KEY (symbol_sk)`
- **Constraints:** `UNIQUE (symbol, isin, valid_from)`
- **Index:** `CREATE INDEX idx_dim_symbol_lookup ON dim_symbol (symbol, is_current);`
- **Estimated Row Count:** ~4,500 rows (reflecting active symbols plus historical renames and delisted entities).
- **As-Of Point-in-Time Join Query:**
  ```sql
  -- Reconcile trade price with historical symbol metadata on a specific date
  SELECT 
      f.trade_date,
      s.symbol,
      s.series,
      s.sector,
      f.close
  FROM fact_price_daily f
  JOIN dim_symbol s 
    ON f.symbol_sk = s.symbol_sk
   AND f.trade_date >= s.valid_from 
   AND f.trade_date <= s.valid_to
  WHERE s.symbol = 'TCS';
  ```

---

### 2.2 `dim_date` (Trading Calendar Dimension)
Populated from `config/holidays.json` and official NSE settlement holiday schedules.

| Column Name | Data Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `date_sk` | `INTEGER` | NO | — | Primary Key in YYYYMMDD format (e.g., `20261016`) |
| `calendar_date` | `DATE` | NO | — | Natural Date (`YYYY-MM-DD`) |
| `year` | `SMALLINT` | NO | — | Calendar Year |
| `quarter` | `SMALLINT` | NO | — | Quarter (1–4) |
| `month` | `SMALLINT` | NO | — | Month (1–12) |
| `week_of_year` | `SMALLINT` | NO | — | ISO Week Number (1–53) |
| `day_of_week` | `SMALLINT` | NO | — | Day of week (1=Monday, 7=Sunday) |
| `is_weekday` | `BOOLEAN` | NO | — | True if Monday–Friday |
| `is_trading_day` | `BOOLEAN` | NO | — | True if NSE was open for normal trading |
| `holiday_name` | `VARCHAR` | YES | NULL | Name of holiday if market closed |
| `settlement_type`| `VARCHAR` | YES | `'T+1'` | Applicable settlement cycle |

- **Primary Key:** `PRIMARY KEY (date_sk)`
- **Constraints:** `UNIQUE (calendar_date)`
- **Index:** `CREATE INDEX idx_dim_date_calendar ON dim_date (calendar_date);`
- **Estimated Row Count:** ~11,000 rows (30 years: 1995 to 2025+).

---

### 2.3 `dim_index` (Benchmark & Sectoral Indices)
| Column Name | Data Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `index_sk` | `SMALLINT` | NO | Generated Sequence | Primary Key |
| `index_code` | `VARCHAR` | NO | — | Symbol identifier (`NIFTY50`, `NIFTY500`, `NIFTYBANK`) |
| `index_name` | `VARCHAR` | NO | — | Full display name |
| `category` | `VARCHAR` | NO | — | `BROAD_MARKET`, `SECTORAL`, `THEMATIC` |
| `is_tradable_fo`| `BOOLEAN` | NO | `FALSE` | Has active derivatives market |

- **Primary Key:** `PRIMARY KEY (index_sk)`
- **Constraints:** `UNIQUE (index_code)`
- **Estimated Row Count:** ~100 rows.

---

### 2.4 `dim_source` (Data Source Registry)
| Column Name | Data Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `source_sk` | `SMALLINT` | NO | Generated Sequence | Primary Key |
| `source_code` | `VARCHAR` | NO | — | Short code (`NSE_BHAVCOPY`, `FYERS_V3`, `NSE_PORTAL`) |
| `source_name` | `VARCHAR` | NO | — | Full provider name |
| `priority` | `SMALLINT` | NO | `1` | Source authority order (1=highest) |

- **Primary Key:** `PRIMARY KEY (source_sk)`
- **Constraints:** `UNIQUE (source_code)`
- **Estimated Row Count:** ~10 rows.

---

## 3. Fact Tables

### 3.1 `fact_price_daily` (Daily Unadjusted OHLCV)
- **Grain:** One row per symbol per trading date.

| Column Name | Data Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `symbol_sk` | `BIGINT` | NO | — | FK -> `dim_symbol.symbol_sk` |
| `date_sk` | `INTEGER` | NO | — | FK -> `dim_date.date_sk` |
| `symbol` | `VARCHAR` | NO | — | Natural symbol |
| `trade_date` | `DATE` | NO | — | Natural trade date |
| `open` | `DOUBLE` | NO | — | Day Open Price (₹) |
| `high` | `DOUBLE` | NO | — | Day High Price (₹) |
| `low` | `DOUBLE` | NO | — | Day Low Price (₹) |
| `close` | `DOUBLE` | NO | — | Day Close Price (₹) |
| `volume` | `BIGINT` | NO | — | Total Traded Volume (Shares) |
| `turnover` | `DOUBLE` | YES | NULL | Total Traded Value (₹ Lakhs) |
| `trades` | `BIGINT` | YES | NULL | Total Executed Transactions |
| `vwap` | `DOUBLE` | YES | NULL | Official Volume Weighted Average Price |
| `source_sk` | `SMALLINT` | NO | — | FK -> `dim_source.source_sk` |
| `batch_id` | `VARCHAR` | NO | — | Ingestion Batch Identifier (Lineage) |
| `price_semantics` | `VARCHAR(20)` | YES | `'unadjusted'` | Price adjustment model (`'unadjusted'`, `'split_only'`, `'total_return'`) |
| `source_ref` | `VARCHAR(50)` | YES | NULL | Specific raw archive source reference (e.g. `'sec_bhavdata_20261016'`) |
| `created_at` | `TIMESTAMP` | NO | `CURRENT_TIMESTAMP`| Ingestion timestamp |

- **Primary Key:** `PRIMARY KEY (symbol_sk, date_sk)`
- **Foreign Keys:**
  - `FOREIGN KEY (symbol_sk) REFERENCES dim_symbol (symbol_sk)`
  - `FOREIGN KEY (date_sk) REFERENCES dim_date (date_sk)`
  - `FOREIGN KEY (source_sk) REFERENCES dim_source (source_sk)`
- **Constraints:** `CHECK (high >= low)`, `CHECK (open > 0)`, `CHECK (close > 0)`, `CHECK (volume >= 0)`
- **Index Strategy:**
  - `CREATE INDEX idx_fact_price_symbol_date ON fact_price_daily (symbol_sk, date_sk);`
  - `CREATE INDEX idx_fact_price_date ON fact_price_daily (date_sk);`
- **Estimated Row Count:** ~13,500,000 rows (2,700 symbols × 5,000 days).
- **Exact Upsert SQL:**
  ```sql
  INSERT INTO fact_price_daily (
      symbol_sk, date_sk, symbol, trade_date,
      open, high, low, close, volume, turnover, trades, vwap,
      source_sk, batch_id, created_at
  )
  SELECT 
      stg.symbol_sk, stg.date_sk, stg.symbol, stg.trade_date,
      stg.open, stg.high, stg.low, stg.close, stg.volume, stg.turnover, stg.trades, stg.vwap,
      stg.source_sk, stg.batch_id, CURRENT_TIMESTAMP
  FROM staging_price_daily stg
  ON CONFLICT (symbol_sk, date_sk) DO UPDATE SET
      open       = EXCLUDED.open,
      high       = EXCLUDED.high,
      low        = EXCLUDED.low,
      close      = EXCLUDED.close,
      volume     = EXCLUDED.volume,
      turnover   = EXCLUDED.turnover,
      trades     = EXCLUDED.trades,
      vwap       = EXCLUDED.vwap,
      source_sk  = EXCLUDED.source_sk,
      batch_id   = EXCLUDED.batch_id,
      created_at = CURRENT_TIMESTAMP;
  ```

---

### 3.2 `fact_ta_daily` (Computed Technical Indicators)
- **Grain:** One row per symbol per trading date.
- Computations populated by `src/engine/ta_indicators.py`, `lux_weinstein.py`, `lux_nwe.py`.

| Column Name | Data Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `symbol_sk` | `BIGINT` | NO | — | FK -> `dim_symbol.symbol_sk` |
| `date_sk` | `INTEGER` | NO | — | FK -> `dim_date.date_sk` |
| `ema_20` | `DOUBLE` | YES | NULL | 20-period Exponential Moving Average |
| `ema_50` | `DOUBLE` | YES | NULL | 50-period Exponential Moving Average |
| `ema_200` | `DOUBLE` | YES | NULL | 200-period Exponential Moving Average |
| `rsi_14` | `DOUBLE` | YES | NULL | Relative Strength Index (14) |
| `adx_14` | `DOUBLE` | YES | NULL | Average Directional Index (14) |
| `atr_14` | `DOUBLE` | YES | NULL | Average True Range (14) |
| `weinstein_stage` | `SMALLINT` | YES | NULL | Stage (1=Base, 2=Advancing, 3=Top, 4=Declining) |
| `ma_10w` | `DOUBLE` | YES | NULL | 10-week (50-day equivalent) MA |
| `ma_10w_slope` | `DOUBLE` | YES | NULL | Slope of 10-week MA (%) |
| `nwe_upper` | `DOUBLE` | YES | NULL | Nadaraya-Watson Envelope Upper Band |
| `nwe_lower` | `DOUBLE` | YES | NULL | Nadaraya-Watson Envelope Lower Band |
| `vol_ratio_50` | `DOUBLE` | YES | NULL | Volume vs 50-day Volume Average Ratio |
| `batch_id` | `VARCHAR` | NO | — | Computation Batch ID |

- **Primary Key:** `PRIMARY KEY (symbol_sk, date_sk)`
- **Foreign Keys:**
  - `FOREIGN KEY (symbol_sk) REFERENCES dim_symbol (symbol_sk)`
  - `FOREIGN KEY (date_sk) REFERENCES dim_date (date_sk)`
- **Estimated Row Count:** ~13,500,000 rows.
- **Exact Upsert SQL:**
  ```sql
  INSERT INTO fact_ta_daily (
      symbol_sk, date_sk,
      ema_20, ema_50, ema_200, rsi_14, adx_14, atr_14,
      weinstein_stage, ma_10w, ma_10w_slope, nwe_upper, nwe_lower, vol_ratio_50,
      batch_id
  )
  SELECT 
      symbol_sk, date_sk,
      ema_20, ema_50, ema_200, rsi_14, adx_14, atr_14,
      weinstein_stage, ma_10w, ma_10w_slope, nwe_upper, nwe_lower, vol_ratio_50,
      batch_id
  FROM staging_ta_daily
  ON CONFLICT (symbol_sk, date_sk) DO UPDATE SET
      ema_20          = EXCLUDED.ema_20,
      ema_50          = EXCLUDED.ema_50,
      ema_200         = EXCLUDED.ema_200,
      rsi_14          = EXCLUDED.rsi_14,
      adx_14          = EXCLUDED.adx_14,
      atr_14          = EXCLUDED.atr_14,
      weinstein_stage = EXCLUDED.weinstein_stage,
      ma_10w          = EXCLUDED.ma_10w,
      ma_10w_slope    = EXCLUDED.ma_10w_slope,
      nwe_upper       = EXCLUDED.nwe_upper,
      nwe_lower       = EXCLUDED.nwe_lower,
      vol_ratio_50    = EXCLUDED.vol_ratio_50,
      batch_id        = EXCLUDED.batch_id;
  ```

---

### 3.3 `fact_delivery_daily` (Security Delivery Position)
- **Grain:** One row per symbol per trading date (sourced from official NSE Bhavcopy delivery reports).

| Column Name | Data Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `symbol_sk` | `BIGINT` | NO | — | FK -> `dim_symbol.symbol_sk` |
| `date_sk` | `INTEGER` | NO | — | FK -> `dim_date.date_sk` |
| `traded_qty` | `BIGINT` | NO | — | Total Traded Quantity |
| `deliverable_qty`| `BIGINT` | NO | — | Deliverable Traded Quantity |
| `delivery_pct` | `DOUBLE` | NO | — | Delivery Percentage (0.00 to 100.00) |
| `source_sk` | `SMALLINT` | NO | — | FK -> `dim_source.source_sk` |
| `batch_id` | `VARCHAR` | NO | — | Ingestion Batch Identifier |

- **Primary Key:** `PRIMARY KEY (symbol_sk, date_sk)`
- **Constraints:** `CHECK (delivery_pct >= 0.0 AND delivery_pct <= 100.0)`
- **Coverage Scope:** Complete for 2020-01-01 onward (via `sec_bhavdata_full`). Pre-2020 delivery is NULL (MTO format deferred).
- **Estimated Row Count:** ~4,800,000 rows (2020+).

---

### 3.4 `fact_signal_daily` (Strategy & SMC Signals)
- **Grain:** One row per symbol per date per strategy.

| Column Name | Data Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `signal_id` | `BIGINT` | NO | Generated Sequence | Primary Key |
| `symbol_sk` | `BIGINT` | NO | — | FK -> `dim_symbol.symbol_sk` |
| `date_sk` | `INTEGER` | NO | — | FK -> `dim_date.date_sk` |
| `strategy_code`| `VARCHAR` | NO | — | Strategy Identifier (`BUY_LOW`, `SMC_SWEEP`, `ETF_SHOP`, `RDX`) |
| `direction` | `VARCHAR` | NO | — | `LONG`, `SHORT`, `NEUTRAL` |
| `score` | `DOUBLE` | YES | NULL | Numerical confidence or ranking score |
| `entry_price` | `DOUBLE` | YES | NULL | Recommended or triggered entry price |
| `stop_loss` | `DOUBLE` | YES | NULL | Invalidation price level |
| `target_price` | `DOUBLE` | YES | NULL | Target exit price level |
| `details_json` | `JSON` | YES | NULL | Additional metadata (order blocks, ratios) |
| `batch_id` | `VARCHAR` | NO | — | Screener Batch Run ID |

- **Primary Key:** `PRIMARY KEY (signal_id)`
- **Constraints:** `UNIQUE (symbol_sk, date_sk, strategy_code)`
- **Estimated Row Count:** ~500,000 rows.

---

### 3.5 `fact_dq_run` (Data Quality Gate Audit Runs)
- **Grain:** One row per Data Quality Gate execution run.

| Column Name | Data Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `run_id` | `VARCHAR` | NO | — | Primary Key (UUIDv4) |
| `run_timestamp`| `TIMESTAMP` | NO | — | ISO-8601 Execution Timestamp |
| `stage` | `VARCHAR` | NO | — | Stage triggering run (`cli.dq-check`, `bhavcopy_incremental.run`) |
| `total_symbols`| `INTEGER` | NO | — | Total universe symbols inspected |
| `passed_count` | `INTEGER` | NO | — | Count of symbols passing all checks |
| `failed_count` | `INTEGER` | NO | — | Count of symbols failing gate |
| `failure_pct` | `DOUBLE` | NO | — | Failure fraction (e.g., `0.0744`) |
| `halt_triggered`| `BOOLEAN` | NO | — | True if gate halted execution |
| `halt_reason` | `VARCHAR` | YES | NULL | Text explanation of halt |
| `duration_ms` | `DOUBLE` | NO | — | Gate execution latency in milliseconds |
| `inactive_count`| `INTEGER` | NO | — | Delisted / inactive bucket count |
| `stale_count` | `INTEGER` | NO | — | Stale trading bucket count |
| `low_coverage_count`| `INTEGER` | NO | — | Low coverage bucket count |

- **Primary Key:** `PRIMARY KEY (run_id)`
- **Index:** `CREATE INDEX idx_dq_run_ts ON fact_dq_run (run_timestamp DESC);`
- **Estimated Row Count:** ~10,000 rows.

---

## 4. Analytical Marts

Marts are exposed directly in DuckDB under the `marts` schema and mirrored to `data/marts/{name}.parquet` for non-database consumers.

### 4.1 `marts.enriched_daily`
Wide denormalized table joining price, volume, delivery, and technical indicators for the screener and dashboard:
```sql
CREATE OR REPLACE VIEW marts.enriched_daily AS
SELECT
    f.trade_date,
    s.symbol,
    s.company_name,
    s.sector,
    f.open,
    f.high,
    f.low,
    f.close,
    f.volume,
    f.vwap,
    d.delivery_pct,
    ta.ema_20,
    ta.ema_50,
    ta.ema_200,
    ta.rsi_14,
    ta.adx_14,
    ta.atr_14,
    ta.weinstein_stage,
    ta.ma_10w_slope,
    ta.vol_ratio_50
FROM fact_price_daily f
JOIN dim_symbol s ON f.symbol_sk = s.symbol_sk AND s.is_current = TRUE
JOIN dim_date dt ON f.date_sk = dt.date_sk
LEFT JOIN fact_delivery_daily d ON f.symbol_sk = d.symbol_sk AND f.date_sk = d.date_sk
LEFT JOIN fact_ta_daily ta ON f.symbol_sk = ta.symbol_sk AND f.date_sk = ta.date_sk;
```

> [!NOTE]
> `DELIV_PCT` is populated from `fact_delivery_daily` for trade dates from 2020-01-01 onward. For pre-2020 dates, `DELIV_PCT` is `NULL`. Downstream analytical models, screeners, and composite scorers treat `NULL` as neutral (default 50) rather than penalizing historical records.

---

## 5. Decisions Pending Operator Input

1. **Parquet Fact Partitioning vs. Single DuckDB File:**
   - *Option A (Recommended):* Store historical facts directly inside `data/warehouse.duckdb`. DuckDB compresses 13.5M rows into ~1.2 GB and executes sub-second vector scans without opening separate files.
   - *Option B:* Dual storage: Keep historical facts in DuckDB *and* maintain year-partitioned Parquets (`data/warehouse/fact_price_daily/year=YYYY/*.parquet`).
2. **Surrogate Key Generation in DuckDB:**
   - *Option A (Recommended):* Use DuckDB Sequences (`CREATE SEQUENCE seq_symbol_sk START 1`).
   - *Option B:* Deterministic integer hashing (e.g., `hash(symbol || isin)` cast to `BIGINT`).
