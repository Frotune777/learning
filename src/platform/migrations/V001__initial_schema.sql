-- V001__initial_schema.sql: Initial warehouse schema for NSE dimensional warehouse
-- Materialized dimensions and facts in DuckDB

-- Sequences for surrogate keys
CREATE SEQUENCE IF NOT EXISTS seq_symbol_sk START 1;
CREATE SEQUENCE IF NOT EXISTS seq_index_sk START 1;
CREATE SEQUENCE IF NOT EXISTS seq_source_sk START 1;
CREATE SEQUENCE IF NOT EXISTS seq_strategy_sk START 1;
CREATE SEQUENCE IF NOT EXISTS seq_signal_id START 1;
CREATE SEQUENCE IF NOT EXISTS seq_dq_symbol_id START 1;
CREATE SEQUENCE IF NOT EXISTS seq_membership_id START 1;
CREATE SEQUENCE IF NOT EXISTS seq_surveillance_id START 1;
CREATE SEQUENCE IF NOT EXISTS seq_health_id START 1;

-- -----------------------------------------------------------------------------
-- Dimensions
-- -----------------------------------------------------------------------------

-- 1. dim_symbol (SCD Type 2)
CREATE TABLE IF NOT EXISTS dim_symbol (
    symbol_sk BIGINT PRIMARY KEY DEFAULT nextval('seq_symbol_sk'),
    symbol VARCHAR NOT NULL,
    isin VARCHAR,
    company_name VARCHAR NOT NULL,
    series VARCHAR NOT NULL DEFAULT 'EQ',
    sector VARCHAR,
    macro_sector VARCHAR,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    classification VARCHAR NOT NULL DEFAULT 'HEALTHY',
    valid_from DATE NOT NULL DEFAULT DATE '1990-01-01',
    valid_to DATE NOT NULL DEFAULT DATE '9999-12-31',
    is_current BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_dim_symbol_lookup ON dim_symbol (symbol, is_current);

-- 2. dim_date
CREATE TABLE IF NOT EXISTS dim_date (
    date_sk INTEGER PRIMARY KEY, -- YYYYMMDD
    calendar_date DATE NOT NULL UNIQUE,
    year SMALLINT NOT NULL,
    quarter SMALLINT NOT NULL,
    month SMALLINT NOT NULL,
    week_of_year SMALLINT NOT NULL,
    day_of_week SMALLINT NOT NULL,
    is_weekday BOOLEAN NOT NULL,
    is_trading_day BOOLEAN NOT NULL,
    holiday_name VARCHAR,
    settlement_type VARCHAR DEFAULT 'T+1'
);
CREATE INDEX IF NOT EXISTS idx_dim_date_calendar ON dim_date (calendar_date);

-- 3. dim_index
CREATE TABLE IF NOT EXISTS dim_index (
    index_sk SMALLINT PRIMARY KEY DEFAULT nextval('seq_index_sk'),
    index_code VARCHAR NOT NULL UNIQUE,
    index_name VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    is_tradable_fo BOOLEAN NOT NULL DEFAULT FALSE
);

-- 4. dim_source
CREATE TABLE IF NOT EXISTS dim_source (
    source_sk SMALLINT PRIMARY KEY DEFAULT nextval('seq_source_sk'),
    source_code VARCHAR NOT NULL UNIQUE,
    source_name VARCHAR NOT NULL,
    description VARCHAR
);

-- 5. dim_strategy
CREATE TABLE IF NOT EXISTS dim_strategy (
    strategy_sk SMALLINT PRIMARY KEY DEFAULT nextval('seq_strategy_sk'),
    strategy_code VARCHAR NOT NULL UNIQUE,
    strategy_name VARCHAR NOT NULL,
    strategy_type VARCHAR NOT NULL
);

-- -----------------------------------------------------------------------------
-- Facts
-- -----------------------------------------------------------------------------

-- 6. fact_price_daily
CREATE TABLE IF NOT EXISTS fact_price_daily (
    symbol_sk BIGINT NOT NULL,
    date_sk INTEGER NOT NULL,
    symbol VARCHAR NOT NULL,
    trade_date DATE NOT NULL,
    series VARCHAR NOT NULL DEFAULT 'EQ',
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    last DOUBLE,
    prev_close DOUBLE,
    volume BIGINT,
    turnover DOUBLE,
    trades BIGINT,
    vwap DOUBLE,
    source_sk SMALLINT,
    batch_id VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol_sk, date_sk)
);
CREATE INDEX IF NOT EXISTS idx_price_daily_sym_date ON fact_price_daily (symbol, trade_date);

-- 7. fact_ta_daily
CREATE TABLE IF NOT EXISTS fact_ta_daily (
    symbol_sk BIGINT NOT NULL,
    date_sk INTEGER NOT NULL,
    symbol VARCHAR NOT NULL,
    trade_date DATE NOT NULL,
    rsi_14 DOUBLE,
    macd DOUBLE,
    macd_signal DOUBLE,
    macd_hist DOUBLE,
    bb_upper DOUBLE,
    bb_middle DOUBLE,
    bb_lower DOUBLE,
    ema_20 DOUBLE,
    ema_50 DOUBLE,
    ema_100 DOUBLE,
    ema_200 DOUBLE,
    sma_20 DOUBLE,
    sma_50 DOUBLE,
    sma_100 DOUBLE,
    sma_150 DOUBLE,
    sma_200 DOUBLE,
    atr_14 DOUBLE,
    adx_14 DOUBLE,
    plus_di_14 DOUBLE,
    minus_di_14 DOUBLE,
    cci_14 DOUBLE,
    low_20d DOUBLE,
    low_126d DOUBLE,
    low_200d DOUBLE,
    high_55d DOUBLE,
    high_52w DOUBLE,
    low_52w DOUBLE,
    rsi_divergence VARCHAR,
    macd_divergence VARCHAR,
    weinstein_stage SMALLINT,
    ma_10w DOUBLE,
    ma_10w_slope DOUBLE,
    nwe_upper DOUBLE,
    nwe_lower DOUBLE,
    vol_ratio_50 DOUBLE,
    batch_id VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol_sk, date_sk)
);
CREATE INDEX IF NOT EXISTS idx_ta_daily_sym_date ON fact_ta_daily (symbol, trade_date);

-- 8. fact_delivery_daily
CREATE TABLE IF NOT EXISTS fact_delivery_daily (
    symbol_sk BIGINT NOT NULL,
    date_sk INTEGER NOT NULL,
    symbol VARCHAR NOT NULL,
    trade_date DATE NOT NULL,
    series VARCHAR NOT NULL DEFAULT 'EQ',
    traded_qty BIGINT,
    deliverable_qty BIGINT,
    delivery_pct DOUBLE,
    source_sk SMALLINT,
    batch_id VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol_sk, date_sk)
);

-- 9. fact_signal_daily
CREATE TABLE IF NOT EXISTS fact_signal_daily (
    signal_id BIGINT PRIMARY KEY DEFAULT nextval('seq_signal_id'),
    symbol_sk BIGINT NOT NULL,
    date_sk INTEGER NOT NULL,
    strategy_sk SMALLINT,
    strategy_code VARCHAR NOT NULL,
    direction VARCHAR NOT NULL,
    score DOUBLE,
    entry_price DOUBLE,
    stop_loss DOUBLE,
    target_price DOUBLE,
    details_json JSON,
    batch_id VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. fact_dq_run
CREATE TABLE IF NOT EXISTS fact_dq_run (
    run_id VARCHAR PRIMARY KEY,
    run_timestamp TIMESTAMP NOT NULL,
    stage VARCHAR NOT NULL,
    total_symbols INTEGER NOT NULL,
    passed_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL,
    failure_pct DOUBLE NOT NULL,
    halt_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    halt_reason VARCHAR,
    duration_ms DOUBLE NOT NULL,
    inactive_count INTEGER DEFAULT 0,
    stale_count INTEGER DEFAULT 0,
    low_coverage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_dq_run_ts ON fact_dq_run (run_timestamp DESC);

-- 11. fact_dq_symbol
CREATE TABLE IF NOT EXISTS fact_dq_symbol (
    dq_symbol_id BIGINT PRIMARY KEY DEFAULT nextval('seq_dq_symbol_id'),
    run_id VARCHAR NOT NULL,
    symbol_sk BIGINT,
    symbol VARCHAR NOT NULL,
    passed BOOLEAN NOT NULL,
    failure_reason VARCHAR,
    last_bar_date DATE,
    row_count INTEGER,
    coverage_pct DOUBLE,
    has_stale_ta BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 12. fact_index_membership
CREATE TABLE IF NOT EXISTS fact_index_membership (
    membership_id BIGINT PRIMARY KEY DEFAULT nextval('seq_membership_id'),
    index_sk SMALLINT NOT NULL,
    symbol_sk BIGINT NOT NULL,
    weight DOUBLE,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL DEFAULT DATE '9999-12-31',
    batch_id VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. fact_symbol_surveillance
CREATE TABLE IF NOT EXISTS fact_symbol_surveillance (
    surveillance_id BIGINT PRIMARY KEY DEFAULT nextval('seq_surveillance_id'),
    symbol_sk BIGINT NOT NULL,
    date_sk INTEGER NOT NULL,
    surveillance_type VARCHAR NOT NULL,
    stage VARCHAR,
    effective_date DATE NOT NULL,
    batch_id VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 14. fact_symbol_health
CREATE TABLE IF NOT EXISTS fact_symbol_health (
    health_id BIGINT PRIMARY KEY DEFAULT nextval('seq_health_id'),
    symbol_sk BIGINT NOT NULL,
    date_sk INTEGER NOT NULL,
    classification VARCHAR NOT NULL,
    days_quiet INTEGER DEFAULT 0,
    last_trade_date DATE,
    notes VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
