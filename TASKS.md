# Project Tasks

Last Updated: 2026-05-26 13:58 UTC
Overall Progress: 100%

## Phase 1: Local NSE Bhavcopy Migration - 100% Complete

### Task 1.1: Environment and Project Structure Setup

Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 1 hour
Actual: 0.5 hours

Description:
Initialize the uv project structure, define pyproject.toml with exact dependencies, create the project directories (src/nse_bhavcopy, tests, data/raw, data/processed), and define PROJECT_STRUCTURE.md.

Files Affected:
- pyproject.toml: Add metadata, exact dependencies, ruff and mypy configurations.
- PROJECT_STRUCTURE.md: Define directory tree and responsibilities.
- TASKS.md: Initialize tasks list.

Implementation Checklist:
- [x] Git repository initialized and feature branch created
- [x] pyproject.toml written with exact packages
- [x] PROJECT_STRUCTURE.md written
- [x] uv sync ran successfully and lock file updated

Dependencies:
- Blocked by: None
- Blocking: Task 1.2

Technical Notes:
Using Python 3.13.5 with uv package manager. Standardized to pandas==2.2.3 and requests==2.32.3 to fetch Python 3.13 Linux binary wheels instantly.

Questions:
None.

Completion Criteria:
- pyproject.toml exists and conforms to rules
- PROJECT_STRUCTURE.md exists
- `uv sync` command runs without errors and creates uv.lock

---

### Task 1.2: Core Code Refactoring

Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 2 hours
Actual: 1.5 hours

Description:
Implement the downloader and local processor module (src/nse_bhavcopy/downloader.py) in English with strict type hints, robust error handling, and file/function-level docstrings. Refactor lerarning.py to serve as the local execution entry point.

Files Affected:
- src/nse_bhavcopy/downloader.py: Core downloading and local processing logic.
- lerarning.py: Simple wrapper entry point scanning dates.

Implementation Checklist:
- [x] Implement downloader.py
- [x] Implement lerarning.py
- [x] Code complies with strict 88 char line length
- [x] Complete type hints for all parameters and return types
- [x] Detailed function docstrings with complexity and logic steps

Dependencies:
- Blocked by: Task 1.1
- Blocking: Task 1.3

Technical Notes:
Data is stored under data/raw/ and data/processed/.

Questions:
None.

Completion Criteria:
- Code runs successfully and processes local files

---

### Task 1.3: Testing & Code Coverage

Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 2 hours
Actual: 1.0 hours

Description:
Write unit tests using pytest for all components in tests/test_downloader.py and ensure 100% test coverage with mock responses.

Files Affected:
- tests/test_downloader.py: pytest file with robust mocks.

Implementation Checklist:
- [x] Unit tests for all downloader.py functions
- [x] 100% test coverage achieved
- [x] Mypy type checks pass with 0 errors

Dependencies:
- Blocked by: Task 1.2
- Blocking: Task 1.4

Completion Criteria:
- `pytest` executes successfully with 100% coverage
- mypy runs with 0 errors

---

### Task 1.4: Code Cleanup & Final Validation

Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 1 hour
Actual: 0.5 hours

Description:
Format and lint the codebase using Ruff, check import sorting, and verify the entire local execution script.

Files Affected:
- All python files.

Implementation Checklist:
- [x] Ruff check --select I --fix ran
- [x] Ruff format ran
- [x] Zero warnings or errors from Ruff
- [x] Walkthrough.md generated

Dependencies:
- Blocked by: Task 1.3
- Blocking: None

Completion Criteria:
- No ruff warnings
- Successfully ran final manual verification

---

## Phase 2: Stock Screener Hardening - 100% Complete

### Task 2.1: Data Normalization and ETF Exclusion
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 1.5 hours
Actual: 1.0 hours

Description:
Normalize older Lakhs-denominated turnover values (`TURNOVER_LACS`) to Rupees and apply high-precision ETF boundary filters to avoid false exclusions.

### Task 2.2: Local Parquet Caching and Robustness
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 3 hours
Actual: 2.0 hours

Description:
Implement high-performance local Parquet cache indexing under `data/processed/.yfcache/`, handle flat single-ticker yfinance columns, and implement lookback DMA guards for new/short-history IPOs.

### Task 2.3: Verification and Test Hardening
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 2 hours
Actual: 1.5 hours

Description:
Develop targeted test cases for new layers in `tests/test_screener.py` and `tests/test_downloader.py`, bringing the entire suite back to clean execution and high overall test coverage.

---

## Phase 3: Resilient Pricing Fetcher & Incremental Cache CRUD - 100% Complete

### Task 3.1: Authoritative NSE Charting Fetcher
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 3 hours
Actual: 2.5 hours

Description:
Develop a modular `src/data/fetcher` package including a circuit breaker, user-agent session managers, official stock token resolver, and the authoritative `NSEChartFetcher` API client.

---

### Task 3.2: Authoritative Fallback and Incremental daily CRUD
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 3 hours
Actual: 2.0 hours

Description:
Refactor `StockScreener._fetch_history` to support target date overlays, perform local cache checks, execute incremental daily Close price CRUD updates directly from Bhavcopy CSV data, and implement transparent `yfinance` fallback logic.

---

### Task 3.3: yfinance 1.4.0 Major Version Upgrade
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 1 hour
Actual: 0.5 hours

Description:
Upgrade yfinance to 1.4.0 in pyproject.toml and regenerate lockfiles to permanently resolve rate-limiting and empty dataframe errors.

---

### Task 3.4: Connectivity Mocks & Test Suite Expansion
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 2 hours
Actual: 1.5 hours

Description:
Add standalone diagnostic scripts to `scratch/` and develop unit test suites verifying full circuit breaker transitions, cookie warm-ups, local token resolver mappings, and incremental Parquet file updates.

---

## Phase 4: Institutional Refactoring, Scoring, Portfolio, and Dashboard - 100% Complete

### Task 4.1: Quantitative Core & Strategy Fixes
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 4 hours
Actual: 1.5 hours

Description:
- Correct the inverted DMA crossover condition in `src/engine/strategies.py` [x]
- Update `src/nse_bhavcopy/ta_indicators.py` to calculate all SMA, EMA, and rolling metrics in one pass [x]
- Update `src/screener.py` to use precalculated indicators, enhance Bull Run filters (A & B) with `DMA20`, and implement correct textbook CAR logic [x]

---

### Task 4.2: Data Ingestion (Fyers Integration)
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 2 hours
Actual: 0.5 hours

Description:
- Modify `src/storage/historical_sync.py` to default to `FyersFetcher` with fallback disabled, utilizing Bhavcopy incremental sync for daily updates [x]

---

### Task 4.3: Scoring & Portfolio Engines (Simulated)
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 4 hours
Actual: 1.0 hours

Description:
- Create `src/scoring/scoring_engine.py` to implement the multi-factor weighted scoring and ranking model [x]
- Create `src/portfolio/portfolio_engine.py` for simulated cash, max position caps, sector limits, and ATR sizing [x]

---

### Task 4.4: Streamlit Dashboard Implementation
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 6 hours
Actual: 2.0 hours

Description:
- Add `streamlit` to `pyproject.toml` and sync dependencies [x]
- Create Streamlit main page and subpages for Daily Signals, Portfolio, and Backtest Explorer [x]

---

### Task 4.5: Test Suite & Verification
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 3 hours
Actual: 1.0 hours

Description:
- Update existing tests in `tests/test_screener.py` and create unit tests for scoring and portfolio engines. Verify linting and type check. [x]

---

## Phase 5: Data Quality, Auto-Healer & Resilient Fallbacks - 100% Complete

### Task 5.1: Selenium-Free Market Mood Index (MMI) Scraper
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 2 hours
Actual: 1.0 hours

Description:
- Query Tickertape directly via `requests` and parse Next.js raw state (`__NEXT_DATA__`) to fetch MMI (100x speedup).
- Retain Selenium as a robust, secondary automated fallback.

---

### Task 5.2: NSE Index API CSV Fallbacks
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 3 hours
Actual: 1.5 hours

Description:
- Upgrade `NseUtils.get_index_details` in `nse_utils.py` and `_fetch_from_nse` in `nifty_index_fetcher.py` to automatically intercept 404/403 blocks and load constituent lists from NSE's public CSV archives.

---

### Task 5.3: CLI Option 26 & Streamlit Quality KPI Card
Status: Complete
Priority: HIGH
Assigned: LLM
Estimated: 3 hours
Actual: 2.0 hours

Description:
- Build Option `26` (Data Quality & Auto-Healer) in `menus.py` to scan master lists and targeted-overwrite missing parquets using Fyers API.
- Add Data Quality status indicator card inside Streamlit Single-Stock Strategy Inspector page.
- Execute full 187/187 test suite validation check cleanly.


