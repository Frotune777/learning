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

---

## Phase 6: Strategic Technical Audit & Quantitative Refinement

### Task 6.1: Strategic Technical Audit & Upgrade Plan
Status: Complete
Priority: HIGH
Assigned: LLM

Description:
Detailed quantitative audit of signal generation loops, look-ahead bias, KNN leakage, Hurst exponent calculations, unstandardized RS-Ratio, and a roadmap for architectural optimizations.

#### Architectural Map & Ingestion Pipeline
1. **Ingestion Layer**: BhavcopyDownloader + HistoricalSync fetches raw Bhavcopy files and writes raw daily data into Parquet files.
2. **Computation Loop**: StockScreener dynamically calculates technical indicators and evaluates 10+ distinct strategies.
3. **Consensus & Regime Layer**: consensus_engine.py aggregates strategy signals using custom weights and determines market states.

#### Code-Level Mathematical Correctness Audit
1. **Look-Ahead Bias in Backtesting**: In `MLClassifier.backtest_model` (ml_classifier.py), `X_test` indices are compared to `df_prices` using `split_idx + 1`. Because `X` has its first 20+ rows dropped, this creates an alignment offset of ~20 trading days. The backtest multiplies prediction for day $t$ with return for day $t-19$.
2. **In-Sample Target Leakage**: In `calc_lorentzian` KNN fallback (strategies.py), the target variable uses `shift(-1)`. After dropping NaNs, the last row of the valid dataset is index $N-2$. The KNN model is trained on the entire valid dataset and then queried with `valid.iloc[-1]` (which is index $N-2$). Due to distance-weighting, the model outputs `y[-1]` (whether the market went up today). This is 100% in-sample leakage.
3. **Data Quality Gatekeeper Skew**: In `MLDataGatekeeper.evaluate` (ml_gatekeeper.py), `combined_df` only includes the last row of `train_df` with `new_df` (length 2). Feature calculations (like 5-day rolling volume SMA) are computed over 2 rows instead of 5, causing a feature preparation skew between training and inference.
4. **Hurst Exponent Noise**: `calculate_hurst_exponent` (quant_metrics.py) is calculated over 20 days with `lags=5`. The linear regression fits `log_tau` vs `log_lags` on exactly 3 points ($lag = 2, 3, 4$). The output is statistical noise with no predictive power.

#### JdK RS-Ratio Quadrant Analysis Audit
The sector rotation module uses de Kempenaer's quadrant mapping but lacks the crucial volatility-standardization step:
- It computes $RS\_Ratio = \frac{RS}{SMA(RS, P)} \times 100$.
- True JdK RS-Ratio requires dividing the difference by the rolling standard deviation: $Z = \frac{RS - SMA(RS, P)}{Std(RS, P)}$.
- Without normalization, more volatile sectors (e.g. Realty) dominate the momentum and ratio axes.

#### Value & Capability Potential Analysis
1. **Factual Limits**: Currently acts as a batch downloader, parquet cache manager, technical indicator library, weighted consensus scanner, and dashboard visualizer.
2. **Hidden Alpha**: Volatility regimes (GARCH(1,1)) can scale trade sizing; standardized RS-Ratio can filter stock-level purchases to leading sectors; robust Hurst exponents can trigger a switch between momentum and mean-reverting strategies.
3. **Scalability**: Python loops and Pandas memory models will bottleneck if scaled to intraday ticks or 5000+ assets.

#### Strategic Upgrade Plan ("Few Tweaks" Roadmap)
1. **Architectural Tweaks**: Migrate core loops to Polars to speed up vector calculations, and transition feature matrices to contiguous NumPy arrays.
2. **Advanced Analysis Layer**: Standardize JdK RS-Ratio with volatility scaling. Adjust consensus thresholds dynamically based on sector quadrants (e.g., raise buy score requirement and tighten stop-losses when in Weakening or Lagging quadrants).
3. **Statistical Enhancements**: Correct indices alignment in `backtest_model`; exclude test points from KNN training; increase Hurst window to 100 days with `lags=20`; and add t-statistic and p-value generation to assess signal significance.
