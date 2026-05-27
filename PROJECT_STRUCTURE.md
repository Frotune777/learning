# Project Structure

Last Updated: 2026-05-27
## Directory Tree

```
.
├── data
│   ├── processed
│   └── raw
├── lerarning.py
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
│   └── nse_bhavcopy
│       ├── downloader.py
│       ├── __init__.py
│       └── screener.py
├── TASKS.md
└── tests
    ├── __init__.py
    ├── test_downloader.py
    ├── test_nse_charts.py
    └── test_screener.py
```

## Module Responsibilities

### src/data/fetcher

**Purpose:** Modular market data acquisition engine querying official NSE charting APIs with stateful isolation and cookie emulation layers.
**Key Files:**
- `circuit_breaker.py`: Stateful CLOSED/OPEN/HALF-OPEN circuit breaker defending remote endpoints.
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

**Purpose:** Core package containing the logic for downloading, cleaning, extracting, and technically screening Top 250 EQ stocks by turnover from the NSE Bhavcopy market file.
**Key Files:**
- `downloader.py`: Houses the `BhavcopyDownloader` class responsible for sending HTTP requests to the NSE archive, downloading raw zip bytes, saving them locally, cleaning data, filtering for series 'EQ' and discarding ETFs, and exporting the top 250 records to CSV.
- `screener.py`: Houses the `StockScreener` class responsible for calculating stock statistics (DMA 50/100/200, Bull/Bear Status, and Cumulative Average Rule CAR rating) offline using pandas, NSEChartFetcher, and YFinance fallback.
- `__init__.py`: Package entry point.

**Dependencies:**
- `pandas`
- `requests`
- `yfinance`
- `src/data/fetcher`

**Used By:**
- `lerarning.py` (Main entry point)
- `tests/test_downloader.py` (Unit tests)
- `tests/test_screener.py` (Unit tests)

---

### tests

**Purpose:** Houses all pytest unit tests to verify logic correctness and maintain 100% test coverage.
**Key Files:**
- `test_downloader.py`: Contains test suites mocking network responses and verifying raw/processed folder savings.
- `test_screener.py`: Contains test suites mocking Yahoo Finance APIs and verifying technical indicators calculations.
- `test_nse_charts.py`: Verifies stateful circuit breaker, managers, sessions warmup, and charting API retrievals.

---

### Root Directory

**Purpose:** Orchestration, environment settings, and task tracking.
**Key Files:**
- `lerarning.py`: Script executing the downloader across date offsets until a successful day is found.
- `TASKS.md`: Project-level task checklist and status details.
- `pyproject.toml`: Project dependencies and configuration settings.
