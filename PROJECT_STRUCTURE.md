# Project Structure

Last Updated: 2026-05-27

## Directory Tree

```
.
├── data
│   ├── processed
│   └── raw
├── main.py
├── PROJECT_STRUCTURE.md
├── pyproject.toml
├── src
│   ├── data
│   │   └── fetcher
│   │       ├── circuit_breaker.py
│   │       ├── prices
│   │       │   ├── base.py
│   │       │   └── nse_charts.py
│   │       ├── session
│   │       │   ├── manager.py
│   │       │   └── nse_session.py
│   │       └── symbols
│   │           └── resolver.py
│   ├── nse_bhavcopy
│   │   ├── backtester.py
│   │   ├── downloader.py
│   │   ├── fo_ban.py
│   │   ├── ml_classifier.py
│   │   ├── query_engine.py
│   │   ├── consensus_engine.py
│   │   ├── position_sizer.py
│   │   ├── mtf_confirmation.py
│   │   ├── quant_metrics.py
│   │   └── screener.py
│   └── nse_live
│       ├── nse_utils.py
│       └── options.py
├── TASKS.md
└── tests
    ├── __init__.py
    ├── test_backtester.py
    ├── test_downloader.py
    ├── test_fo_ban.py
    ├── test_historical_sync.py
    ├── test_ml_classifier.py
    ├── test_nse_charts.py
    ├── test_query_engine.py
    └── test_screener.py
```

## Module Responsibilities

### src/data/fetcher

**Purpose:** Modular market data acquisition engine querying official NSE charting APIs with stateful isolation and cookie emulation layers.
**Key Files:**
- `circuit_breaker.py`: Stateful CLOSED/OPEN/HALF-OPEN circuit breaker defending remote remote endpoints.
- `session/manager.py`: Coordinates persistent HTTP sessions, User-Agent browser headers, and rate pacing.
- `session/nse_session.py`: Warms up landing page connection cookies.
- `symbols/resolver.py`: Local JSON symbol-to-charting-token resolver registry.
- `prices/base.py`: Defines AbstractPriceFetcher schema.
- `prices/nse_charts.py`: Standardizes primary symbolsHistoricalData acquisitions.

**Dependencies:**
- `pandas`
- `requests`

**Used By:**
- `src/nse_bhavcopy/screener.py` (StockScreener analytics pipeline)
- `tests/test_nse_charts.py` (Unit tests)

---

### src/nse_bhavcopy

**Purpose:** Core package containing the logic for downloading, cleaning, extracting, and technically screening Top 250 EQ stocks by turnover from the NSE Bhavcopy market file, together with ML classifiers, backtesters, and a DuckDB query engine.
**Key Files:**
- `downloader.py`: Houses the `BhavcopyDownloader` class responsible for sending HTTP requests to the NSE archive, downloading raw zip bytes, saving them locally, cleaning data, filtering for series 'EQ' and discarding ETFs, and exporting the top 250 records to CSV.
- `screener.py`: Houses the `StockScreener` class responsible for calculating stock statistics (DMA 50/100/200, Bull/Bear Status, and Cumulative Average Rule CAR rating) offline using pandas, NSEChartFetcher, and YFinance fallback.
- `query_engine.py`: High-performance DuckDB query engine for time-series aggregation directly over local Parquet price files.
- `ml_classifier.py`: Random Forest binary direction classifier incorporating technical indicators, volatility features, and delivery percentage signals.
- `backtester.py`: Backtesting wrappers supporting vectorized (`VectorBT`) and event-driven simulated trading (`NSEEventBacktester`) with NSE transaction costs, daily circuit limit checks, and T+1 settlement cycles.
- `fo_ban.py`: Downloader and manager for the active F&O ban securities list.
- `consensus_engine.py`: Multi-methodology ranking consensus aggregator.
- `position_sizer.py`: ATR and risk-percent allocation position size calculator.
- `mtf_confirmation.py`: Multi-timeframe trend verification rules.
- `quant_metrics.py`: Quantitative performance analytics calculator.

**Dependencies:**
- `pandas`
- `requests`
- `yfinance`
- `duckdb`
- `scikit-learn`
- `vectorbt`
- `src/data/fetcher`

**Used By:**
- `main.py` (Main entry point)
- `tests/` (Unit tests)

---

### tests

**Purpose:** Houses all pytest unit tests to verify logic correctness and maintain high test coverage.
**Key Files:**
- `test_downloader.py`: Contains test suites mocking network responses and verifying raw/processed folder savings.
- `test_screener.py`: Contains test suites mocking Yahoo Finance APIs and verifying technical indicators calculations.
- `test_nse_charts.py`: Verifies stateful circuit breaker, managers, sessions warmup, and charting API retrievals.
- `test_query_engine.py`: Verifies DuckDB query construction and in-memory Parquet schema matching.
- `test_ml_classifier.py`: Validates Random Forest walk-forward splits, feature engineering, and predictions.
- `test_backtester.py`: Verifies T+1 cash settlement cycles, transaction costs (STT, stamp duty), and Upper Circuit locks.
- `test_fo_ban.py`: Verifies parsing and caching for active F&O ban CSVs.

---

### Root Directory

**Purpose:** Orchestration, environment settings, and task tracking.
**Key Files:**
- `main.py`: Interactive CLI REPL and subcommand orchestrator.
- `TASKS.md`: Project-level task checklist and status details.
- `pyproject.toml`: Project dependencies and configuration settings.
