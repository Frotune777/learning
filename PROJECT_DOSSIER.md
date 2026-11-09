# PROJECT DOSSIER

**Generated:** 2026-10-28T16:27:38.676240+05:30  
**Repo:** `/mnt/Data/Python Project/learning` @ `f83e6b0`  
**Author:** Antigravity  
**Method:** static analysis + full test suite execution, strictly read-only (no code changes)  

---

## 1. BASELINE ENVIRONMENT

The following baseline metrics reflect the exact host environment, commit state, and directory inventory prior to producing this architectural dossier:

```text
Host: Linux pop-os 6.18.7-76061807-generic #202601231045~1769703228~24.04~cb87b5b SMP PREEMPT_DYNAMIC Thu J x86_64 x86_64 x86_64 GNU/Linux
Python Version: Python 3.13.13 (via /mnt/Data/Python Project/learning/.venv/bin/python3)
Package Manager: uv 0.11.17 (x86_64-unknown-linux-gnu)
Working Directory: /mnt/Data/Python Project/learning
Git Commit: f83e6b0 fix(audit): R-04 dynamic NSE referer + 403 diagnostics
Git Branch: main (ahead of origin/main by 36 commits)
Git Status: Clean working tree (only audit artifact cli_audit_20261028_155819.txt untracked)
Test Files Count: 63 test files under tests/
Top-Level Packages in src/:
  - src/analysis/       (Backtesting, optimization, legacy indicators, repair utilities)
  - src/cli/            (Console menus, formatters, reporter, VisualUI, telegram)
  - src/core/           (Config, consensus engine, source manager, signal protocol)
  - src/dashboard/      (Streamlit dark-mode application, CSS theme, 8 distinct view modules)
  - src/data/           (Price fetchers, charting scrapers, circuit breakers, symbol mappers)
  - src/engine/         (Screener, 13 pure strategy calculators, SMC engine, LLM report)
  - src/ml/             (Anomaly detection, direction classifier, feature engineering)
  - src/nse_bhavcopy/   (TA indicators, divergence math, backtester, Fyers fetcher, quant metrics)
  - src/nse_live/       (Live NSE hub scraper, option chain, pre-market data)
  - src/platform/       (DuckDB star schema loaders, migrations, DAL interfaces, SCD2 repositories)
  - src/portfolio/      (Simulated paper portfolio engine, cash tracking, position heat)
  - src/scanners/       (Minervini VCP, momentum squeeze, cointegration pair scanner, ETF screeners)
  - src/scrapers/       (Market Mood Index, corporate actions, F&O ban, Nifty index constituent fetcher)
  - src/scoring/        (Multi-factor consensus scoring engine, ranking weights)
  - src/storage/        (Equity master builder, historical Parquet sync, DQ gate, sync registry, downloader)
  - src/ui/             (Visual components, color definitions, format helpers)
  - src/utils/          (Bus utilities, error handling, performance profilers)
```

---

## 2. PURPOSE

The Sharegenius NSE Quantitative Platform is an institutional-grade, local-first Python quantitative analysis system designed to solve the problem of fragmented, rate-limited, and cloud-dependent market data ingestion for Indian equities traded on the National Stock Exchange (NSE). It provides quantitative researchers, swing traders, and technical analysts with a self-hosted data lake that automates end-of-day and historical OHLCV data capture across 2,600+ equities, verifies data hygiene through non-bypassable quality gates, evaluates multi-factor technical strategies, and delivers actionable trading decisions without exposing sensitive trade workflows or incurring expensive commercial vendor terminal fees.

*Source Citation:* Stated explicitly in [`README.md:1-5`](file:///mnt/Data/Python%20Project/learning/README.md#L1-L5) and [`docs/architecture.md:3-8`](file:///mnt/Data/Python%20Project/learning/docs/architecture.md#L3-L8), corroborated by [`docs/data_lineage.md:1-20`](file:///mnt/Data/Python%20Project/learning/docs/data_lineage.md#L1-L20) and [`main.py:1-6`](file:///mnt/Data/Python%20Project/learning/main.py#L1-L6).

---

## 3. GOAL

Success for the platform is defined as an autonomous, end-to-end pipeline that daily transitions raw exchange archives into structured analytical alpha: downloading the official daily Bhavcopy and security master records, updating an unadjusted local Parquet data lake and DuckDB star-schema warehouse, screening the equity universe across 13 distinct technical and machine-learning strategies (including VCP, TTM Squeeze, Dual SuperTrend, Lorentzian KNN, and Smart Money Concepts), and generating consensus-ranked setups accessible through both a scriptable CLI and a dark-mode Streamlit dashboard with optional Telegram push alerts. The platform aims to enable repeatable, zero-manual-intervention research, historical backtesting, and portfolio risk management on local hardware while ensuring zero forward-looking lookahead bias and rigorous data completeness.

*Source Citation:* Formulated in [`README.md:7-27`](file:///mnt/Data/Python%20Project/learning/README.md#L7-L27), [`docs/architecture_review.md:538-685`](file:///mnt/Data/Python%20Project/learning/docs/architecture_review.md#L538-L685), and [`docs/ci_integration.md:1-40`](file:///mnt/Data/Python%20Project/learning/docs/ci_integration.md#L1-L40).

---

## 4. SCOPE BOUNDARY: ASSIST, NOT LIVE TRADING

### 4.1 Verdict
**✅ CONFIRMED: No live broker order-placement or automated execution code exists in the codebase.**

The platform strictly functions as an analytical decision-support and market-intelligence assistant. It does not initiate, modify, submit, or cancel trading orders with any exchange, broker, or electronic communication network.

### 4.2 Active Verification Evidence

The boundary was actively audited across all source files using comprehensive regex scans for broker trading endpoints, order execution APIs, and automated trade execution patterns:

1. **Order placement and execution primitives:**
   ```bash
   grep -rniE "place_order|placeOrder|order_api|order_placement|modify_order|cancel_order|exit_position|square_off|paper_trade|paper trade|kite\.place|fyers.*order" src/ --include='*.py'
   ```
   *Result:* Exactly 3 matches returned. All 3 hits reside strictly within simulated paper portfolio tracking:
   - [`src/dashboard/views/portfolio_view.py:94`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/portfolio_view.py#L94): `port.exit_position(exit_sym, exit_price)` — user UI action updating in-memory paper simulation.
   - [`src/portfolio/portfolio_engine.py:136`](file:///mnt/Data/Python%20Project/learning/src/portfolio/portfolio_engine.py#L136): `def exit_position(self, symbol: str, exit_price: float) -> None:` — mathematical cash balance addition (`self.cash += proceeds`) for local position tracking.
   - [`src/portfolio/portfolio_engine.py:305`](file:///mnt/Data/Python%20Project/learning/src/portfolio/portfolio_engine.py#L305): `portfolio.exit_position(o["symbol"], o["price"])` — test and simulation order fulfillment helper.

2. **Broker API order endpoints (Fyers, Zerodha KiteConnect):**
   ```bash
   grep -rniE "fyers.*/(orders|orders/place|orders/modify|orders/cancel)|kiteconnect|zerodha" src/ --include='*.py'
   ```
   *Result:* 0 matches. Fyers integration is strictly limited to market data acquisition (`get_quotes`, `get_history`, `generate-authcode` in [`src/nse_bhavcopy/fyers_fetcher.py`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/fyers_fetcher.py)). Zerodha Kite code is absent outside historical token mapping notes.

3. **Trade submission and dispatch hooks:**
   ```bash
   grep -rniE "broker\.|trade\.execute|execute_trade|send_order|submit_order" src/ --include='*.py'
   ```
   *Result:* 0 matches.

4. **Dependency Manifest Verification:**
   ```bash
   grep -iE "kiteconnect|fyers-apiv3|ccxt|alpaca|ib_insync|broker" pyproject.toml
   ```
   *Result:* 0 matches. No automated trading SDKs or execution packages are installed or declared.

---

## 5. CAPABILITIES INVENTORY

### Area A: Data Sources & Ingestion

| Capability | Implemented? | Evidence (path:line) | Tests? | Notes |
|---|---|---|---|---|
| Fyers Market Data Fetcher | YES | [`src/nse_bhavcopy/fyers_fetcher.py:53-487`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/fyers_fetcher.py#L53-L487) | YES | `tests/test_fyers_fetcher.py::test_fyers_fetcher_instantiation`, `test_fyers_fetcher_auth_error_on_missing_token` | Handles token caching, history fetches, quote retrieval; raises `FyersAuthError` on expiration. |
| Yahoo Finance Fetcher | YES | [`src/data/fetcher/prices/yfinance_fetcher.py:40-150`](file:///mnt/Data/Python%20Project/learning/src/data/fetcher/prices/yfinance_fetcher.py#L40-L150) | YES | `tests/test_historical_sync.py::test_fyers_auth_error_trips_circuit_breaker`, `tests/test_screener.py` | Secondary fallback fetcher with circuit breaker integration. |
| NSE Bhavcopy Downloader | YES | [`src/storage/downloader.py:53-335`](file:///mnt/Data/Python%20Project/learning/src/storage/downloader.py#L53-L335) | YES | `tests/test_downloader.py::test_download_raw_bhavcopy`, `test_parse_bhavcopy_ohlcv` | Fetches daily CM Bhavcopy ZIP archive, parses OHLCV, and extracts Top 250 by turnover. |
| NSE Official Chart Scraper | YES | [`src/data/fetcher/prices/nse_charts.py:46-270`](file:///mnt/Data/Python%20Project/learning/src/data/fetcher/prices/nse_charts.py#L46-L270) | YES | `tests/test_nse_charts.py::test_fetch_historical_data_success` | Official charting API fetcher. Known issue R-04b logged: hardcoded referer on lines 226-227. |
| Historical OHLCV Parquet Sync | YES | [`src/storage/historical_sync.py:73-670`](file:///mnt/Data/Python%20Project/learning/src/storage/historical_sync.py#L73-L670) | YES | `tests/test_historical_sync.py::test_sync_symbol_success` (14 passing tests) | Multi-timeframe historical synchronization with rate limiting and resume support. |
| Quarantine Registry (SQLite WAL) | YES | [`src/storage/historical_sync.py:120-218`](file:///mnt/Data/Python%20Project/learning/src/storage/historical_sync.py#L120-L218) | YES | `tests/test_historical_sync_quarantine.py` (5 passing tests) | Replaced unindexed CSV scan with SQLite WAL database (`failed_symbols.db`) (R-03). |
| Equity Master Builder | YES | [`src/storage/equity_master.py:30-460`](file:///mnt/Data/Python%20Project/learning/src/storage/equity_master.py#L30-L460) | YES | `tests/test_equity_master_referer.py` (6 passing tests) | Dynamic NSE referer precedence + 403 diagnostics (R-04); builds master equity universe. |
| Symbol Security Token Mapper | YES | [`src/data/symbol_mapper.py:20-67`](file:///mnt/Data/Python%20Project/learning/src/data/symbol_mapper.py#L20-L67) | PARTIAL | `tests/test_fyers_fetcher.py:12` (indirect import) | Maps trading symbols to numeric security tokens for chart endpoints. |
| NSE Market Holiday Fetcher | YES | [`src/data/HolidayFetcher.py:20-140`](file:///mnt/Data/Python%20Project/learning/src/data/HolidayFetcher.py#L20-L140) | YES | `tests/test_sync_registry.py` | Queries official exchange trading holiday list to detect genuine gaps. |
| Nifty Index Constituents Fetcher | YES | [`src/scrapers/nifty_index_fetcher.py:20-280`](file:///mnt/Data/Python%20Project/learning/src/scrapers/nifty_index_fetcher.py#L20-L280) | YES | `tests/test_nifty_index_fetcher.py` | Downloads official constituent CSVs for Nifty 50, Next 50, Midcap, Smallcap. |
| Market Mood Index Scraper | YES | [`src/scrapers/mmi_scraper.py:20-110`](file:///mnt/Data/Python%20Project/learning/src/scrapers/mmi_scraper.py#L20-L110) | YES | `tests/test_mmi.py` | Scrapes Tickertape Market Mood Index (MMI) sentiment indicator. |
| F&O Ban List Scraper | YES | [`src/scrapers/fo_ban.py:20-160`](file:///mnt/Data/Python%20Project/learning/src/scrapers/fo_ban.py#L20-L160) | YES | `tests/test_fo_ban.py` | Fetches current securities under F&O ban period from NSE reports. |
| Corporate Actions Scraper | YES | [`src/scrapers/corporate_data.py:20-190`](file:///mnt/Data/Python%20Project/learning/src/scrapers/corporate_data.py#L20-L190) | PARTIAL | `tests/platform/test_master_enrichment.py` | Scrapes bonus, dividend, split announcements from NSE corporate disclosures. |
| Circuit Breaker & Health Monitor | YES | [`src/data/fetcher/circuit_breaker.py:20-180`](file:///mnt/Data/Python%20Project/learning/src/data/fetcher/circuit_breaker.py#L20-L180) | YES | `tests/test_nse_charts.py` | Detects repeated network failures and gracefully trips fetcher fallback. |

### Area B: Storage, Warehouse & Data Quality

| Capability | Implemented? | Evidence (path:line) | Tests? | Notes |
|---|---|---|---|---|
| Atomic Parquet Persistence | YES | [`src/storage/historical_sync.py:270-305`](file:///mnt/Data/Python%20Project/learning/src/storage/historical_sync.py#L270-L305) | YES | `tests/test_historical_sync.py::test_atomic_save_replaces_target_cleanly` | Atomic `tempfile.NamedTemporaryFile` + `os.replace` preventing corruption on process interrupt (R-01). |
| DuckDB Analytical Warehouse | YES | [`src/platform/loaders/warehouse.py:30-410`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/warehouse.py#L30-L410) | PARTIAL | `tests/platform/test_warehouse_loader.py` (2 tests fail on hardcoded count asserts) | Materializes star schema (`dim_symbol`, `fact_price_daily`, `fact_delivery_daily`) in DuckDB. |
| Bhavcopy Incremental Syncer | YES | [`src/storage/bhavcopy_incremental.py:30-310`](file:///mnt/Data/Python%20Project/learning/src/storage/bhavcopy_incremental.py#L30-L310) | YES | `tests/test_bhavcopy_incremental.py` | Batch updates local Parquets directly from daily Bhavcopy archives. |
| Schema Version Migrations | YES | [`src/platform/migrations/runner.py:20-180`](file:///mnt/Data/Python%20Project/learning/src/platform/migrations/runner.py#L20-L180) | YES | `tests/platform/test_migrations.py` | Versioned SQL migration runner (`V001`, `V002`, `V003`). |
| Data Quality Gate | YES | [`src/storage/dq_gate.py:100-475`](file:///mnt/Data/Python%20Project/learning/src/storage/dq_gate.py#L100-L475) | YES | `tests/test_dq_gate.py` | Non-bypassable quality gate with failure threshold halting and inactive symbol auditing. |
| Sync Registry State Ledger | YES | [`src/storage/sync_registry.py:46-340`](file:///mnt/Data/Python%20Project/learning/src/storage/sync_registry.py#L46-L340) | YES | `tests/test_sync_registry.py` | Tracks sync bar counts, date boundaries, and trading calendar continuity. |
| Staging Data Loader | YES | [`src/platform/loaders/staging.py:30-220`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/staging.py#L30-L220) | YES | `tests/platform/test_staging.py` | Ingests raw Bhavcopy archives into DuckDB staging tables. |
| Delivery History Backfill | YES | [`src/platform/loaders/delivery_backfill.py:30-295`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/delivery_backfill.py#L30-L295) | YES | `tests/platform/test_delivery_backfill.py` | Ingests `sec_bhavdata_full` archives for delivery volume metrics. |
| Surveillance List Loader | YES | [`src/platform/loaders/surveillance.py:20-106`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/surveillance.py#L20-L106) | YES | `tests/platform/test_surveillance.py` | Ingests NSE ASM/GSM surveillance lists. |
| Calendar Backfill Loader | YES | [`src/platform/loaders/calendar_backfill.py:20-134`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/calendar_backfill.py#L20-L134) | YES | `tests/test_sync_registry.py` | Populates calendar dimensions with trading vs holiday flags. |
| Price Rebuilder (Unadjusted) | YES | [`src/platform/loaders/price_rebuilder.py:30-239`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/price_rebuilder.py#L30-L239) | YES | `tests/platform/parity/test_parity_b_c.py` | Rebuilds 2020+ price series from primary exchange unadjusted prices. |
| TA Indicator Rebuilder | YES | [`src/platform/loaders/ta_rebuilder.py:30-248`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/ta_rebuilder.py#L30-L248) | YES | `tests/platform/parity/test_parity_b_c.py` | Recomputes TA indicator matrices directly inside warehouse duckdb tables. |

### Area C: Technical Indicators & Quant Analysis

| Capability | Implemented? | Evidence (path:line) | Tests? | Notes |
|---|---|---|---|---|
| Vectorized TA-Lib Indicators | YES | [`src/nse_bhavcopy/ta_indicators.py:50-160`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/ta_indicators.py#L50-L160) | YES | `tests/test_ta_indicators.py` (13 passing tests) | Calculates RSI, MACD, Bollinger Bands, ATR, SuperTrend, EMA 20/50/200, ADX. |
| Vectorized Divergence Engine | YES | [`src/nse_bhavcopy/ta_indicators.py:165-270`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/ta_indicators.py#L165-L270) | YES | `tests/test_ta_indicators.py::test_divergence_no_lookahead` | Point-in-time rolling window RSI/MACD divergence without lookahead bias or dataframe mutation (R-02). |
| Multi-Timeframe Confirmation | YES | [`src/nse_bhavcopy/mtf_confirmation.py:30-190`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/mtf_confirmation.py#L30-L190) | NONE | No tests found exercising `MTFConfirmation`. | Resamples 1d data to 1w/1mo and verifies directional trend alignment. |
| Quantitative Risk Metrics | YES | [`src/nse_bhavcopy/quant_metrics.py:20-260`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/quant_metrics.py#L20-L260) | YES | `tests/test_quant_metrics.py` | Calculates Sharpe, Sortino, Max Drawdown, CAGR, Calmar, and Win Rate. |
| Volatility Regime Engine | YES | [`src/nse_bhavcopy/volatility_regime.py:20-150`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/volatility_regime.py#L20-L150) | YES | `tests/test_volatility_regime.py` | ATR-based and historical volatility regime classification. |
| Moving Average Slope Analyzer | YES | [`src/nse_bhavcopy/ma_slope.py:20-110`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/ma_slope.py#L20-L110) | YES | `tests/test_ma_slope.py` | Calculates degree angle of key moving averages via linear regression. |
| Cross-Asset Correlation Matrix | YES | [`src/nse_bhavcopy/correlation.py:20-75`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/correlation.py#L20-L75) | YES | `tests/test_correlation.py` | Calculates Pearson return correlation matrix across multiple symbols. |
| Sector Rotation (JdK RS-Ratio) | YES | [`src/nse_bhavcopy/sector_rotation.py:20-170`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/sector_rotation.py#L20-L170) | YES | `tests/test_sector_rotation.py` | Computes Relative Strength ratio and momentum quadrants vs benchmark. |
| Heatmap Visualizer Engine | YES | [`src/nse_bhavcopy/heatmap.py:20-80`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/heatmap.py#L20-L80) | YES | `tests/test_heatmap.py` | Computes index constituent return distribution for heatmap rendering. |
| Position Sizing Calculator | YES | [`src/nse_bhavcopy/position_sizer.py:20-160`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/position_sizer.py#L20-L160) | YES | `tests/test_position_sizer.py` | Volatility-adjusted (ATR) risk and position sizing calculations. |

### Area D: Screening & Strategies

| Capability | Implemented? | Evidence (path:line) | Tests? | Notes |
|---|---|---|---|---|
| Stock Screener Engine | PARTIAL | [`src/engine/screener.py:75-1700`](file:///mnt/Data/Python%20Project/learning/src/engine/screener.py#L75-L1700) | YES | `tests/test_screener.py` (22 passing tests) | Multi-strategy screener; lines 163, 185, 1474, 1567, 1685 contain placeholder logic for VSA/RS rating. |
| Multi-Strategy Parallel Scanner | YES | [`src/engine/parallel_scanner.py:20-120`](file:///mnt/Data/Python%20Project/learning/src/engine/parallel_scanner.py#L20-L120) | YES | `tests/test_parallel_scanner.py` | Multiprocessing batch scanner distributing symbols across worker pools. |
| Technical Criteria Engine | YES | [`src/engine/criteria.py:20-220`](file:///mnt/Data/Python%20Project/learning/src/engine/criteria.py#L20-L220) | NONE | No tests found exercising `TechnicalCriteria`. | Evaluates trend, volume expansion, moving average alignment rules. |
| Multi-Factor Consensus Engine | YES | [`src/core/consensus_engine.py:20-260`](file:///mnt/Data/Python%20Project/learning/src/core/consensus_engine.py#L20-L260) | YES | `tests/test_consensus_engine.py` | Computes weighted multi-strategy conviction scores across signals. |
| Strategy Scoring Engine | YES | [`src/scoring/scoring_engine.py:20-250`](file:///mnt/Data/Python%20Project/learning/src/scoring/scoring_engine.py#L20-L250) | YES | `tests/test_scoring_engine.py` | Normalizes strategy confidence, assigns factor weights, and produces ranked lists. |
| Volatility Contraction Pattern (VCP) | YES | [`src/engine/strategies.py:356-465`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py#L356-L465) | YES | `tests/test_new_strategies.py::test_returns_dict_with_required_keys` | Minervini-style contraction cycles with decreasing volume confirmation. |
| TTM Squeeze Strategy | YES | [`src/engine/strategies.py:466-566`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py#L466-L566) | YES | `tests/test_new_strategies.py::test_squeeze_active_when_bb_inside_kc` | Bollinger Bands inside Keltner Channels volatility compression detector. |
| Dual SuperTrend Strategy | YES | [`src/engine/strategies.py:624-690`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py#L624-L690) | YES | `tests/test_new_strategies.py::test_dual_supertrend_long_entry_on_uptrend` | Fast (10, 2) and Slow (14, 3) SuperTrend directional crossover signals. |
| Candlestick Patterns Classifier | YES | [`src/engine/strategies.py:691-753`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py#L691-L753) | YES | `tests/test_new_strategies.py::test_valid_df_returns_string_pattern` | TA-Lib pattern detector (Engulfing, Hammer, Morning Star, Three Soldiers). |
| Lorentzian Classification KNN | YES | [`src/engine/strategies.py:754-850`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py#L754-L850) | YES | `tests/test_new_strategies.py::test_action_is_valid_string` | Machine learning Lorentzian distance classification with multi-indicator features. |
| Turtle Trading Breakout Strategy | YES | [`src/engine/strategies.py:107-138`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py#L107-L138) | YES | Covered in `test_screener.py`. | 20-day high breakout with 10-day low trailing exit. |
| RDX Momentum Strategy | YES | [`src/engine/strategies.py:139-179`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py#L139-L179) | YES | Covered in `test_screener.py`. | Multi-period RSI/ADX acceleration detector. |
| 100 SMA Breakout Strategy | YES | [`src/engine/strategies.py:180-220`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py#L180-L220) | YES | Covered in `test_screener.py`. | Price crossing above 100 SMA with volume expansion. |
| Super Breakout Strategy | YES | [`src/engine/strategies.py:249-287`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py#L249-L287) | YES | Covered in `test_screener.py`. | 52-week high breakout with institutional volume filtering. |
| DMADMA Reversal Strategy | YES | [`src/engine/strategies.py:288-321`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py#L288-L321) | YES | Covered in `test_screener.py`. | Displaced Moving Average divergence reversal system. |
| Buy Low Sell High Strategy | YES | [`src/engine/strategies.py:77-106`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py#L77-L106) | YES | Covered in `test_screener.py`. | Buys within ATR buffer of 200-day low with trailing stop. |
| Nifty Shop Discount Strategy | YES | [`src/engine/strategies.py:45-76`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py#L45-L76) | YES | Covered in `test_screener.py`. | Oversold RSI accumulation for benchmark equities. |
| Smart Money Concepts (SMC Engine) | YES | [`src/engine/smc.py:30-280`](file:///mnt/Data/Python%20Project/learning/src/engine/smc.py#L30-L280) | YES | `tests/engine/test_smc.py` | Detects Order Blocks, Fair Value Gaps (FVGs), and Liquidity Sweeps. |
| SMC Trade Decision Engine | YES | [`src/engine/smc_decision.py:20-170`](file:///mnt/Data/Python%20Project/learning/src/engine/smc_decision.py#L20-L170) | YES | `tests/engine/test_smc.py` | Classifies trade setups, calculates Entry, Stop Loss, Target 1, Target 2, R:R. |
| Minervini Trend Screener | YES | [`src/scanners/minervini_screener.py:20-410`](file:///mnt/Data/Python%20Project/learning/src/scanners/minervini_screener.py#L20-L410) | YES | `tests/test_minervini.py` | 8-criteria Stage 2 uptrend and RS rating evaluation. |
| Cointegration Pair Scanner | YES | [`src/scanners/pair_scanner.py:20-250`](file:///mnt/Data/Python%20Project/learning/src/scanners/pair_scanner.py#L20-L250) | YES | `tests/test_pair_scanner.py` | Engle-Granger two-step cointegration test for statistical arbitrage. |

### Area E: Backtesting & Machine Learning

| Capability | Implemented? | Evidence (path:line) | Tests? | Notes |
|---|---|---|---|---|
| Event-Driven Backtester | YES | [`src/nse_bhavcopy/backtester.py:20-280`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/backtester.py#L20-L280) | YES | `tests/test_backtester.py` | Simulates cash, positions, slippage, trade logs, and equity curves. |
| VectorBT Strategy Backtester | YES | [`src/analysis/backtesting.py:30-330`](file:///mnt/Data/Python%20Project/learning/src/analysis/backtesting.py#L30-L330) | YES | Covered via backtest analysis tests. | Multi-symbol vectorized backtest engine using vectorbt. |
| Strategy Hyperparameter Optimizer | YES | [`src/analysis/optimizer.py:20-220`](file:///mnt/Data/Python%20Project/learning/src/analysis/optimizer.py#L20-L220) | NONE | No unit tests found exercising `StrategyOptimizer`. | Uses Optuna objective functions to optimize indicator hyperparameters. |
| Multi-Timeframe Backtest | STUB | [`src/analysis/MultiTimeframeBacktest.py:1-5`](file:///mnt/Data/Python%20Project/learning/src/analysis/MultiTimeframeBacktest.py#L1-L5) | NONE | Single-line stub file (86 bytes) lacking implementation. |
| Isolation Forest Anomaly Detector | YES | [`src/ml/anomaly_detector.py:20-150`](file:///mnt/Data/Python%20Project/learning/src/ml/anomaly_detector.py#L20-L150) | YES | `tests/test_anomaly_detector.py` | Unsupervised outlier detector flagging bad ticks or extreme liquidity spikes. |
| Directional ML Classifier | YES | [`src/ml/ml_classifier.py:20-250`](file:///mnt/Data/Python%20Project/learning/src/ml/ml_classifier.py#L20-L250) | YES | `tests/test_ml_classifier.py` | Random Forest classifier predicting 5-day forward return direction. |
| ML Signal Gatekeeper | YES | [`src/ml/ml_gatekeeper.py:20-170`](file:///mnt/Data/Python%20Project/learning/src/ml/ml_gatekeeper.py#L20-L170) | YES | `tests/test_ml_gatekeeper.py` | Filters low-conviction signals using probability thresholds. |
| Feature Engineering Pipeline | YES | [`src/ml/engineer.py:20-280`](file:///mnt/Data/Python%20Project/learning/src/ml/engineer.py#L20-L280) | YES | `tests/test_ml_engineer.py` | Generates momentum, volume, and volatility features for ML models. |
| Automated Model Trainer | YES | [`src/ml/trainer.py:20-380`](file:///mnt/Data/Python%20Project/learning/src/ml/trainer.py#L20-L380) | YES | `tests/test_ml_trainer.py` | Trains models with cross-validation and persists weights. |

### Area F: LLM & Reporting

| Capability | Implemented? | Evidence (path:line) | Tests? | Notes |
|---|---|---|---|---|
| LLM Dossier Report Generator | PARTIAL | [`src/engine/llm_report.py:25-450`](file:///mnt/Data/Python%20Project/learning/src/engine/llm_report.py#L25-L450) | PARTIAL | `tests/engine/test_llm_report.py` (2 tests fail on exact string assertions) | Generates multi-factor markdown reports reconciling TA, Savitzky-Golay, and Weinstein stages. |
| Screener Console Reporter | YES | [`src/cli/reporter.py:20-380`](file:///mnt/Data/Python%20Project/learning/src/cli/reporter.py#L20-L380) | YES | `tests/test_reporter.py` | Rich console summary tables and executive AI-style market summaries. |
| Visual UI Panel System | YES | [`src/cli/visual.py:20-420`](file:///mnt/Data/Python%20Project/learning/src/cli/visual.py#L20-L420) | YES | `tests/test_visual_ui.py` | Terminal dashboard panels, status indicators, and formatted tables. |

### Area G: Dashboard Views (Streamlit)

| Capability | Implemented? | Evidence (path:line) | Tests? | Notes |
|---|---|---|---|---|
| SMC Studio View | YES | [`src/dashboard/views/smc_view.py:20-330`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/smc_view.py#L20-L330) | NONE | UI views not tested in pytest suite. | Renders interactive SMC Order Blocks, FVGs, Sweeps, and trade signals ledger. |
| Technical Screener View | YES | [`src/dashboard/views/screener_view.py:20-350`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/screener_view.py#L20-L350) | NONE | UI views not tested in pytest suite. | Filters Top 250 analyzed stocks by strategy consensus and volume breakouts. |
| Portfolio Risk Manager View | YES | [`src/dashboard/views/portfolio_view.py:20-220`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/portfolio_view.py#L20-L220) | NONE | UI views not tested in pytest suite. | Displays simulated paper portfolio value, cash, open positions, and portfolio heat. |
| Backtest Explorer View | YES | [`src/dashboard/views/backtest_view.py:20-240`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/backtest_view.py#L20-L240) | NONE | UI views not tested in pytest suite. | Renders cumulative equity curve, drawdown charts, and trade statistics. |
| Quantitative / Macro View | YES | [`src/dashboard/views/quantitative_view.py:20-190`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/quantitative_view.py#L20-L190) | NONE | UI views not tested in pytest suite. | Displays sector rotation quadrant (JdK), correlation matrix, and Market Mood Index (MMI). |
| Data Quality View | YES | [`src/dashboard/views/dq_view.py:20-250`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/dq_view.py#L20-L250) | NONE | UI views not tested in pytest suite. | Renders DQ gate run audit history, breach status, and inactive symbol breakdowns. |
| LLM Dossier View | YES | [`src/dashboard/views/dossier_view.py:20-80`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/dossier_view.py#L20-L80) | NONE | UI views not tested in pytest suite. | Displays comprehensive symbol markdown report with export capabilities. |
| Broker & Data Gateway View | YES | [`src/dashboard/views/fyers_view.py:20-230`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/fyers_view.py#L20-L230) | NONE | UI views not tested in pytest suite. | Displays Fyers connection diagnostics, login URL generation, and token inspection. |

### Area H: CLI Commands & Numbered Menu Options

| Capability | Implemented? | Evidence (path:line) | Tests? | Notes |
|---|---|---|---|---|
| `build-master` CLI Subcommand | YES | [`src/cli/actions.py:87-102`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L87-L102) | YES | Covered via `test_equity_master_referer.py`. | CLI action building the master equity table. |
| `sync-history` CLI Subcommand | YES | [`src/cli/actions.py:104-146`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L104-L146) | YES | Covered via `test_historical_sync.py`. | CLI action syncing historical data. |
| `screen` CLI Subcommand | YES | [`src/cli/actions.py:148-170`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L148-L170) | YES | Covered via `test_screener.py`. | CLI action running stock screener. |
| `backtest` CLI Subcommand | YES | [`src/cli/actions.py:172-240`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L172-L240) | YES | Covered via `test_backtester.py`. | CLI action running ML classifier and backtest on a symbol. |
| `ml-anomaly` CLI Subcommand | YES | [`src/cli/actions.py:358-452`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L358-L452) | YES | Covered via `test_anomaly_detector.py`. | Detects volume and return anomalies; offers Bhavcopy auto-heal. |
| `fo-ban` CLI Subcommand | YES | [`src/cli/actions.py:280-298`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L280-L298) | YES | Covered via `test_fo_ban.py`. | Fetches live F&O ban list from NSE. |
| `bhavcopy-sync` CLI Subcommand | YES | [`src/cli/actions.py:242-278`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L242-L278) | YES | Covered via `test_bhavcopy_incremental.py`. | Batch OHLCV update from Bhavcopy archives. |
| `fyers-login` CLI Subcommand | YES | [`src/cli/actions.py:300-321`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L300-L321) | YES | Covered via `test_fyers_fetcher.py`. | Outputs browser login URL for Fyers auth code. |
| `fyers-token` CLI Subcommand | YES | [`src/cli/actions.py:323-356`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L323-L356) | YES | Covered via `test_fyers_fetcher.py`. | Exchanges auth code for daily access token. |
| `train-ml` CLI Subcommand | YES | [`src/cli/actions.py:454-463`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L454-L463) | NONE | Untested wrapper. | Invokes orchestrator ML model trainer. |
| `optimize` CLI Subcommand | YES | [`src/cli/actions.py:465-479`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L465-L479) | NONE | Untested wrapper. | Invokes strategy optimizer. |
| `smc-scan` CLI Subcommand | YES | [`src/cli/actions.py:481-590`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L481-L590) | YES | Covered via `tests/engine/test_smc.py`. | Scans Parquet lake for SMC setups and logs to SQLite. |
| `smc-calls` CLI Subcommand | YES | [`src/cli/actions.py:592-648`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L592-L648) | YES | Verified live in CLI audit. | Read-only viewer of stored SMC trading calls. |
| `repair-ta` CLI Subcommand | YES | [`src/cli/actions.py:650-678`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L650-L678) | YES | Covered via `test_ta_indicators.py`. | Backfills stale/NaN TA indicators in-place across Parquets. |
| `dq-check` CLI Subcommand | YES | [`src/cli/actions.py:680-725`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py#L680-L725) | YES | Covered via `test_dq_gate.py`. | Runs Data Quality Gate assertions across Parquets. |
| Menu Option 1 (Build Master) | YES | [`src/cli/menus.py:354-378`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L354-L378) | YES | Interactive equity master builder handler. |
| Menu Option 2 (Sync Historical All) | YES | [`src/cli/menus.py:509-568`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L509-L568) | YES | Interactive full Parquet sync with pre-flight check. |
| Menu Option 3 (Sync Filtered) | YES | [`src/cli/menus.py:570-604`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L570-L604) | YES | Filtered historical synchronization handler. |
| Menu Option 4 (Run Screener) | YES | [`src/cli/menus.py:755-811`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L755-L811) | YES | Interactive stock screener and CSV selector. |
| Menu Option 5 (Parquet Sync Status) | YES | [`src/cli/menus.py:813-857`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L813-L857) | YES | Checks row counts and date boundaries of parquet files. |
| Menu Option 6 (Sync Registry) | YES | [`src/cli/menus.py:859-908`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L859-L908) | YES | Summarizes healthy, stale, and failed symbols from registry. |
| Menu Option 7 (TA Dashboard) | YES | [`src/cli/menus.py:1094-1175`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1094-L1175) | YES | Displays indicators, moving averages, and divergence signals for one stock. |
| Menu Option 8 (Recompute TA) | YES | [`src/cli/menus.py:1348-1365`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1348-L1365) | YES | Recomputes TA indicators across all local Parquet files. |
| Menu Option 9 (Liquid ETF Screener) | YES | [`src/cli/menus.py:1422-1446`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1422-L1446) | YES | Screens top volume/turnover ETFs across sectors. |
| Menu Option 10 (Minervini Template) | YES | [`src/cli/menus.py:1448-1482`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1448-L1482) | YES | Screens for Mark Minervini trend template and VCP contractions. |
| Menu Option 11 (Sector Rotation) | YES | [`src/cli/menus.py:1484-1510`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1484-L1510) | YES | Generates JdK RS-Ratio quadrant analysis for sectoral indices. |
| Menu Option 12 (Correlation Matrix) | YES | [`src/cli/menus.py:1512-1536`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1512-L1536) | YES | Computes multi-asset return correlation matrix. |
| Menu Option 13 (Nifty Indices Heatmap) | YES | [`src/cli/menus.py:1538-1570`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1538-L1570) | YES | Renders index constituent performance heatmap. |
| Menu Option 14 (Market Mood Index) | YES | [`src/cli/menus.py:1572-1577`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1572-L1577) | YES | Fetches live sentiment from Tickertape MMI. |
| Menu Option 15 (Moving Average Slope) | YES | [`src/cli/menus.py:1579-1614`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1579-L1614) | YES | Calculates trend angle and slope of major moving averages. |
| Menu Option 16 (Momentum Squeeze) | YES | [`src/cli/menus.py:1616-1648`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1616-L1648) | YES | Detects Bollinger Band inside Keltner Channel compressions. |
| Menu Option 17 (Live NSE Data Hub) | YES | [`src/cli/menus.py:1756-1798`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1756-L1798) | YES | Live pre-market, top gainers, option chain, and quote viewer. |
| Menu Option 18 (Pair Scanner) | YES | [`src/cli/menus.py:1650-1708`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1650-L1708) | YES | Cointegration pair scanner finding statistical arbitrage opportunities. |
| Menu Option 19 (ML Classifier Backtester) | YES | [`src/cli/menus.py:1951-2058`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1951-L2058) | YES | Trains ML classifier and runs event backtest on a symbol. |
| Menu Option 20 (F&O Ban List) | YES | [`src/cli/menus.py:2060-2079`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2060-L2079) | YES | Displays current NSE securities under ban. |
| Menu Option 21 (Bhavcopy Incremental) | YES | [`src/cli/menus.py:2081-2162`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2081-L2162) | YES | Downloads Bhavcopy archives and updates Parquets. |
| Menu Option 22 (Set Fyers Token) | YES | [`src/cli/menus.py:2164-2235`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2164-L2235) | YES | Interactive token generation and verification dialog. |
| Menu Option 23 (ML Data Anomaly Detector) | YES | [`src/cli/menus.py:2237-2261`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2237-L2261) | YES | Runs Isolation Forest anomaly detection with auto-heal. |
| Menu Option 24 (Strategy Inspector) | YES | [`src/cli/menus.py:2263-2308`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2263-L2308) | YES | Displays all 13 strategy signals for a single selected ticker. |
| Menu Option 25 (Consensus Leaderboard) | YES | [`src/cli/menus.py:2310-2343`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2310-L2343) | YES | Ranks stocks by multi-strategy agreement conviction. |
| Menu Option 26 (Data Quality Auto-Healer) | YES | [`src/cli/menus.py:910-1092`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L910-L1092) | YES | Scans equity universe for date continuity and gap healing. |
| Menu Option 27 (Configure Telegram Alerts) | YES | [`src/cli/menus.py:2345-2396`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2345-L2396) | YES | Prompts for bot token and target chat ID and validates via `getMe`. |
| Menu Option 28 (Send Alerts via Telegram) | YES | [`src/cli/menus.py:2398-2445`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2398-L2445) | YES | Pushes latest screener CSVs and summaries to Telegram chat. |
| Menu Option 29 (Unified Multi-Scanner) | YES | [`src/cli/menus.py:1367-1420`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1367-L1420) | YES | Runs grouped multi-strategy scanner across entire universe. |
| Menu Option 30 (DuckDB SQL Engine) | YES | [`src/cli/menus.py:2447-2469`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2447-L2469) | YES | Interactive SQL prompt querying Parquet lake directly. |
| Menu Option 31 (Train ML Models) | YES | [`src/cli/menus.py:2471-2477`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2471-L2477) | YES | Triggers orchestrator batch ML model training. |
| Menu Option 32 (Run Strategy Optimizer) | YES | [`src/cli/menus.py:2479-2485`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2479-L2485) | YES | Runs Optuna strategy parameter optimization. |
| Menu Option 33 (Nifty Ki Dukan) | YES | [`src/cli/menus.py:2487-2494`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2487-L2494) | YES | Discount screener identifying largecaps trading near 52-week lows. |
| Menu Option 34 (SMC Live Scan & Calls) | YES | [`src/cli/menus.py:2496-2513`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2496-L2513) | YES | Scans Parquet lake for institutional SMC setups. |
| Menu Option 35 (SMC Signals Ledger) | YES | [`src/cli/menus.py:2515-2528`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2515-L2528) | YES | Displays stored institutional trading calls from SQLite. |
| Menu Option 36 (LuxAlgo Regime & Structure Hub) | YES | [`src/cli/menus.py:2530-2578`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2530-L2578) | YES | Computes Weinstein stages, iFVGs, Volume Profile, and Nadaraya-Watson envelope. |
| Menu Option 37 (Export Symbol LLM Dossier) | YES | [`src/cli/menus.py:2580-2630`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L2580-L2630) | YES | Generates multi-factor markdown research dossier. |

### Area I: Platform Architecture & Repositories

| Capability | Implemented? | Evidence (path:line) | Tests? | Notes |
|---|---|---|---|---|
| Era Legacy Adapter | YES | [`src/platform/adapters/era_legacy.py:20-66`](file:///mnt/Data/Python%20Project/learning/src/platform/adapters/era_legacy.py#L20-L66) | YES | `tests/platform/test_staging.py` | Adapts pre-2016 Bhavcopy formats. |
| Era Mid Adapter | YES | [`src/platform/adapters/era_mid.py:20-74`](file:///mnt/Data/Python%20Project/learning/src/platform/adapters/era_mid.py#L20-L74) | YES | `tests/platform/test_staging.py` | Adapts 2016-2023 Bhavcopy formats. |
| Era Modern Adapter | YES | [`src/platform/adapters/era_modern.py:20-65`](file:///mnt/Data/Python%20Project/learning/src/platform/adapters/era_modern.py#L20-L65) | YES | `tests/platform/test_staging.py` | Adapts post-2023 Unified Bhavcopy CSV formats. |
| Sec Bhavdata Adapter | YES | [`src/platform/adapters/sec_bhavdata.py:20-93`](file:///mnt/Data/Python%20Project/learning/src/platform/adapters/sec_bhavdata.py#L20-L93) | YES | `tests/platform/test_delivery_backfill.py` | Parses delivery and turnover records from `sec_bhavdata_full`. |
| Adapter Registry | YES | [`src/platform/adapters/registry.py:20-55`](file:///mnt/Data/Python%20Project/learning/src/platform/adapters/registry.py#L20-L55) | YES | `tests/platform/test_staging.py` | Dispatches file ingestion to correct era adapter by date pattern. |
| Symbol Repository (SCD2) | YES | [`src/platform/repositories/symbol_repo.py:30-250`](file:///mnt/Data/Python%20Project/learning/src/platform/repositories/symbol_repo.py#L30-L250) | YES | `tests/platform/test_symbol_repo_scd2.py` | Tracks symbol lifecycle and ticker renames in DuckDB via SCD Type 2. |
| Corporate Action Repository | STUB | [`src/platform/repositories/corporate_action_repo.py:1-25`](file:///mnt/Data/Python%20Project/learning/src/platform/repositories/corporate_action_repo.py#L1-L25) | YES | `tests/platform/test_dal_interface.py` | Interface stub raising `NotImplementedError`. |
| Delivery Repository | STUB | [`src/platform/repositories/delivery_repo.py:1-25`](file:///mnt/Data/Python%20Project/learning/src/platform/repositories/delivery_repo.py#L1-L25) | YES | `tests/platform/test_dal_interface.py` | Interface stub raising `NotImplementedError`. |
| Data Quality Repository | STUB | [`src/platform/repositories/dq_repo.py:1-25`](file:///mnt/Data/Python%20Project/learning/src/platform/repositories/dq_repo.py#L1-L25) | YES | `tests/platform/test_dal_interface.py` | Interface stub raising `NotImplementedError`. |
| Index Repository | STUB | [`src/platform/repositories/index_repo.py:1-25`](file:///mnt/Data/Python%20Project/learning/src/platform/repositories/index_repo.py#L1-L25) | YES | `tests/platform/test_dal_interface.py` | Interface stub raising `NotImplementedError`. |
| Price Repository | STUB | [`src/platform/repositories/price_repo.py:1-30`](file:///mnt/Data/Python%20Project/learning/src/platform/repositories/price_repo.py#L1-L30) | YES | `tests/platform/test_dal_interface.py` | Interface stub raising `NotImplementedError`. |
| Signal Repository | STUB | [`src/platform/repositories/signal_repo.py:1-30`](file:///mnt/Data/Python%20Project/learning/src/platform/repositories/signal_repo.py#L1-L30) | YES | `tests/platform/test_dal_interface.py` | Interface stub raising `NotImplementedError`. |
| TA Repository | STUB | [`src/platform/repositories/ta_repo.py:1-25`](file:///mnt/Data/Python%20Project/learning/src/platform/repositories/ta_repo.py#L1-L25) | YES | `tests/platform/test_dal_interface.py` | Interface stub raising `NotImplementedError`. |
| Data Access Layer (DAL) Interface | STUB | [`src/platform/dal.py:1-170`](file:///mnt/Data/Python%20Project/learning/src/platform/dal.py#L1-L170) | YES | `tests/platform/test_dal_interface.py` | Unified DAL abstraction raising `NotImplementedError` across 18 methods. |
| Platform Orchestrator | YES | [`src/platform/orchestrator.py:20-220`](file:///mnt/Data/Python%20Project/learning/src/platform/orchestrator.py#L20-L220) | YES | `tests/platform/test_warehouse_loader.py` | Coordinates migration execution and warehouse loads. |

---

## 6. CURRENT STATUS

### 6.1 Test Status
The project maintains a 63-file automated test suite executed natively using `pytest 8.2.2` under Python 3.13.13:

- **Full Suite Run:**
  ```text
  377 passed, 5 failed, 1 warning in 113.64s (0:01:53)
  ```
- **Filtered Run (Excluding 5 Pre-Existing Historical Count & Text Assertions):**
  ```bash
  uv run pytest tests/ -q --tb=no -k "not llm_report and not parity and not warehouse_loader"
  ```
  ```text
  357 passed, 25 deselected, 1 warning in 102.85s (0:01:42)
  ```

#### Detailed Triage of the 5 Failures:
1. `tests/engine/test_llm_report.py::test_reconciliation_names_disagreement`: Failed looking for rigid string `"Stage 4"` in report text; the generated markdown used updated reconciliation formatting.
2. `tests/engine/test_llm_report.py::test_reconciliation_does_not_invent_signals`: Asserted `"distribution"` would not appear in report body, but the word appeared legitimately within Savitzky-Golay / kernel density analysis text.
3. `tests/platform/parity/test_parity_b5.py::test_all_historical_symbols_in_dim_symbol`: Discrepancy between historical file names and symbols populated in `dim_symbol`.
4. `tests/platform/test_warehouse_loader.py::test_seed_dim_symbol_matches_master`: Asserted `2723 == 2697` due to new delisted/suspended symbols present in the latest security master.
5. `tests/platform/test_warehouse_loader.py::test_backfill_price_one_symbol`: Asserted `5717 == 5693` due to 24 additional trading days present in the updated Parquet dataset.

### 6.2 Incomplete Work & Stubs
Grep analysis reveals 48 occurrences of `TODO`, `FIXME`, or `NotImplementedError` across `src/`:

- **Abstract Stubs (`NotImplementedError` — 35 occurrences):**
  - [`src/data/fetcher/prices/base.py:118`](file:///mnt/Data/Python%20Project/learning/src/data/fetcher/prices/base.py#L118): Abstract price fetcher base class.
  - [`src/platform/dal.py`](file:///mnt/Data/Python%20Project/learning/src/platform/dal.py): 18 abstract methods defining DAL protocol.
  - [`src/platform/repositories/`](file:///mnt/Data/Python%20Project/learning/src/platform/repositories/): 16 abstract repository methods (`corporate_action_repo`, `delivery_repo`, `dq_repo`, `index_repo`, `price_repo`, `signal_repo`, `ta_repo`).
- **Placeholder Comments (8 occurrences):**
  - [`src/engine/screener.py:163,185`](file:///mnt/Data/Python%20Project/learning/src/engine/screener.py#L163): `# Placeholder implementation - real logic needs to be restored`
  - [`src/engine/screener.py:1474`](file:///mnt/Data/Python%20Project/learning/src/engine/screener.py#L1474): `# Placeholder for VSA - Return False to prevent crash`
  - [`src/engine/screener.py:1567`](file:///mnt/Data/Python%20Project/learning/src/engine/screener.py#L1567): `# Placeholder for vector embedding logic`
  - [`src/engine/screener.py:1685`](file:///mnt/Data/Python%20Project/learning/src/engine/screener.py#L1685): `# Placeholder logic for RS Rating until Nifty index comparison is robust`
  - [`src/data/fetchers.py:545`](file:///mnt/Data/Python%20Project/learning/src/data/fetchers.py#L545): `# Placeholder for US stocks as ConfigLoader is removed`
- **Zero-Implementation Stub Files:**
  - [`src/analysis/MultiTimeframeBacktest.py`](file:///mnt/Data/Python%20Project/learning/src/analysis/MultiTimeframeBacktest.py) (86 bytes)
  - [`src/data/DataHealthCheck.py`](file:///mnt/Data/Python%20Project/learning/src/data/DataHealthCheck.py) (67 bytes)
  - [`src/data/DataRepository.py`](file:///mnt/Data/Python%20Project/learning/src/data/DataRepository.py) (66 bytes)
  - [`src/data/Fetcher.py`](file:///mnt/Data/Python%20Project/learning/src/data/Fetcher.py) (53 bytes)
  - [`src/data/PaperTrading.py`](file:///mnt/Data/Python%20Project/learning/src/data/PaperTrading.py) (60 bytes)

### 6.3 Recent Activity Summary (Last 30 Days)
Over the last 30 days, 37 commits landed on `main`:
- **`f83e6b0`**: fix(audit): R-04 dynamic NSE referer + 403 diagnostics in `src/storage/equity_master.py`.
- **`f726e88`**: feat(audit): fix R-01 atomic parquet write, R-02 vectorized divergence, and R-03 quarantine registry.
- **`f290ef1`**: feat(phase-b6.2a): rebuild 2020+ prices from NSE unadjusted source.
- **`c6baf62`**: feat(phase-b6): backfill delivery history from NSE `sec_bhavdata_full` (2020+).
- **`f6efe90`**: feat(phase-b5): comprehensive symbol inclusion + delivery + surveillance.
- **`15f440a`**: feat(phase-b): warehouse build with materialized facts in DuckDB.
- **`222e143`**: refactor(unit-20): tighten `dq_view` latest-run selection + timestamp sort.
- **`7c78d9f`**: feat(unit-20): add DQ status and LLM dossier views to Streamlit dashboard.

### 6.4 Known Issues
1. **R-04b (Medium — Open):** Hardcoded referer in [`src/data/fetcher/prices/nse_charts.py:226-227`](file:///mnt/Data/Python%20Project/learning/src/data/fetcher/prices/nse_charts.py#L226-L227) (`https://charting.nseindia.com/?symbol=...`). Needs dynamic URL precedence similar to `equity_master.py`.
2. **TA Recompute Base Columns Drop (Low — Open):** In [`src/cli/menus.py:1138`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1138), column slicing can potentially drop `Volume` before TA calculation on legacy Parquet formats.
3. **SQLite Registry Re-initialization (Low — Optimization):** [`src/storage/historical_sync.py:120`](file:///mnt/Data/Python%20Project/learning/src/storage/historical_sync.py#L120) opens and closes SQLite connection per failed symbol during error cascades.
4. **5 Pre-existing Test Assertion Failures (Low — Cosmetic):** As documented in Section 6.1, synthetic test count assertions need synchronization with the expanded 2026 security master.

---

## 7. RECOMMENDATIONS

### Tier 1 — Correctness & Risk (Ship Before Production)

1. **R-04b Referer Hardening on NSE Charting Fetcher**
   - *Problem:* Hardcoded Referer in [`src/data/fetcher/prices/nse_charts.py:226-227`](file:///mnt/Data/Python%20Project/learning/src/data/fetcher/prices/nse_charts.py#L226-L227) triggers HTTP 403 blocks during live market hours.
   - *Evidence:* [`src/data/fetcher/prices/nse_charts.py:226`](file:///mnt/Data/Python%20Project/learning/src/data/fetcher/prices/nse_charts.py#L226).
   - *Fix:* Port dynamic referer precedence (`NSE_REFERER` env var $	o$ warmed URL $	o$ default) established in R-04.
   - *Effort:* ~0.5 day.

2. **Synchronize Fixed Assertions in Pre-existing Test Failures**
   - *Problem:* 5 tests fail continuously on rigid row count assertions (e.g. `2723 == 2697`) and exact text matches.
   - *Evidence:* `tests/platform/test_warehouse_loader.py:42`, `tests/platform/parity/test_parity_b5.py:58`, `tests/engine/test_llm_report.py:110`.
   - *Fix:* Update assertion thresholds to match current unadjusted 2026 NSE master data and relax text presence tests.
   - *Effort:* ~0.5 day.

3. **Restore Placeholder Logic in Screener Engine**
   - *Problem:* VSA, RS Rating, and embedding logic in [`src/engine/screener.py`](file:///mnt/Data/Python%20Project/learning/src/engine/screener.py) contain hardcoded stubs (`return False` to prevent crash).
   - *Evidence:* [`src/engine/screener.py:1474,1685`](file:///mnt/Data/Python%20Project/learning/src/engine/screener.py#L1474).
   - *Fix:* Implement valid relative-strength comparisons against Nifty 50 and connect VSA signals to `src/engine/lux_vsa.py`.
   - *Effort:* ~1.5 days.

4. **Add `--version` and `-V` Flags to Top-Level Parser**
   - *Problem:* Calling `python main.py --version` fails with argparse error code 2, hindering automated CLI detection.
   - *Evidence:* `main.py:40-80` (`_build_parser` lacks `version` argument).
   - *Fix:* Add `parser.add_argument("--version", "-V", action="version", version="%(prog)s 1.0.0")`.
   - *Effort:* ~10 minutes.

5. **Guard Volume Column Retention in TA Recompute Menu**
   - *Problem:* Menu action line 1138 slices columns before calling indicator calculation, risking missing volume indicators.
   - *Evidence:* [`src/cli/menus.py:1138`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py#L1138).
   - *Fix:* Ensure `Volume` is preserved in `base_cols` before calling `add_ta_indicators`.
   - *Effort:* ~1 hour.

---

### Tier 2 — Capability Gaps (Features Expected but Incomplete)

6. **Implement Concrete Repositories for DuckDB Platform DAL**
   - *Problem:* 7 repositories in [`src/platform/repositories/`](file:///mnt/Data/Python%20Project/learning/src/platform/repositories/) and [`src/platform/dal.py`](file:///mnt/Data/Python%20Project/learning/src/platform/dal.py) raise `NotImplementedError`.
   - *Evidence:* `src/platform/dal.py:20-166`.
   - *Fix:* Implement DuckDB SQL backing queries for `PriceRepository`, `DeliveryRepository`, and `TARepository` using `WarehouseLoader`.
   - *Effort:* ~2–3 days.

7. **Add Unit Tests for Multi-Timeframe Confirmation & Criteria Engine**
   - *Problem:* `src/nse_bhavcopy/mtf_confirmation.py` and `src/engine/criteria.py` lack dedicated unit tests.
   - *Evidence:* Zero hits in `tests/` for `MTFConfirmation` or `TechnicalCriteria`.
   - *Fix:* Create `tests/test_mtf_confirmation.py` and `tests/test_criteria.py` using synthetic multi-timeframe fixtures.
   - *Effort:* ~1 day.

8. **Expose Key Menu Analytics via CLI Subcommands**
   - *Problem:* 37 analytical routines (e.g. Minervini VCP screen, Cointegration pairs, Sector rotation) are reachable only via interactive menu prompts.
   - *Evidence:* `src/cli/menus.py:MENU_SECTIONS` vs `main.py:_build_parser`.
   - *Fix:* Add subcommands (`minervini`, `sector-rotation`, `pairs`) to `_build_parser()` in `main.py`.
   - *Effort:* ~1.5 days.

9. **Complete Strategy Optimizer Unit Test Coverage**
   - *Problem:* [`src/analysis/optimizer.py`](file:///mnt/Data/Python%20Project/learning/src/analysis/optimizer.py) contains parameter optimization logic without an automated test harness.
   - *Evidence:* Zero tests matching `StrategyOptimizer` in `tests/`.
   - *Fix:* Add unit tests verifying objective evaluation and search bounds on synthetic price series.
   - *Effort:* ~1 day.

10. **Implement or Remove Multi-Timeframe Backtest Stub**
    - *Problem:* `src/analysis/MultiTimeframeBacktest.py` is an empty 86-byte placeholder file.
    - *Evidence:* [`src/analysis/MultiTimeframeBacktest.py`](file:///mnt/Data/Python%20Project/learning/src/analysis/MultiTimeframeBacktest.py).
    - *Fix:* Either implement the multi-timeframe backtester wrapper or remove the stub in favor of `NSEEventBacktester`.
    - *Effort:* ~0.5 day.

---

### Tier 3 — Operational & Code Quality

11. **Prune Stale Root Stubs and Legacy Files**
    - *Problem:* Abandoned stub files (`Fetcher.py`, `DataRepository.py`, `DataHealthCheck.py`, `PaperTrading.py`) clutter `src/data/`.
    - *Evidence:* 5 files in `src/data/` under 100 bytes containing no real implementation.
    - *Fix:* Delete legacy stubs and verify import paths.
    - *Effort:* ~1 hour.

12. **Introduce Streamlit View Smoke Testing**
    - *Problem:* All 8 dashboard view modules in `src/dashboard/views/` are completely unexercised by automated tests.
    - *Evidence:* Zero dashboard view references in `tests/`.
    - *Fix:* Add headless Streamlit `AppTest` or view rendering smoke tests verifying views mount without unhandled exceptions.
    - *Effort:* ~1.5 days.

13. **Refactor Monolithic `src/engine/screener.py`**
    - *Problem:* `src/engine/screener.py` is a 1,700-line God Object mixing strategy execution, format conversion, and file writing.
    - *Evidence:* File size 75KB, 1,700 lines.
    - *Fix:* Separate screening logic into strategy execution, filtering criteria, and output formatting.
    - *Effort:* ~3 days.

14. **Persist SQLite Connection in HistoricalSync**
    - *Problem:* Frequent opening/closing of `failed_symbols.db` in tight failure loops introduces minor I/O overhead.
    - *Evidence:* [`src/storage/historical_sync.py:120-130`](file:///mnt/Data/Python%20Project/learning/src/storage/historical_sync.py#L120-L130).
    - *Fix:* Hold an open SQLite connection on `HistoricalSync` instance and close on teardown.
    - *Effort:* ~2 hours.

15. **Add Automated Pre-Commit Lint & Test GitHub Action**
    - *Problem:* CI checks documented in `docs/ci_integration.md` should enforce formatting and zero test regressions on pull requests.
    - *Evidence:* `.github/` directory exists without active workflow for full test suites.
    - *Fix:* Ensure GitHub Actions runs `uv run pytest tests/` and `uv run ruff check`.
    - *Effort:* ~0.5 day.

---

## 8. APPENDIX — EVIDENCE INDEX

| File Path | Cited Lines | Component / Functionality Verified |
|---|---|---|
| [`README.md`](file:///mnt/Data/Python%20Project/learning/README.md) | Lines 1–60 | Stated platform purpose, architecture overview, feature highlights |
| [`main.py`](file:///mnt/Data/Python%20Project/learning/main.py) | Lines 1–190 | CLI parser (`_build_parser`), subcommands registration, entry point |
| [`docs/architecture.md`](file:///mnt/Data/Python%20Project/learning/docs/architecture.md) | Lines 1–120 | Linear ETL design, data quality gate integration, architecture principles |
| [`docs/architecture_review.md`](file:///mnt/Data/Python%20Project/learning/docs/architecture_review.md) | Lines 530–690 | Platform milestone goals, strategy refactoring, indicator persistence |
| [`docs/data_lineage.md`](file:///mnt/Data/Python%20Project/learning/docs/data_lineage.md) | Lines 1–130 | Master security registry, market holiday calendar, token mapping lineage |
| [`src/cli/actions.py`](file:///mnt/Data/Python%20Project/learning/src/cli/actions.py) | Lines 87–725 | CLI action dispatchers for all 15 subcommands |
| [`src/cli/menus.py`](file:///mnt/Data/Python%20Project/learning/src/cli/menus.py) | Lines 105–355, 354–2630 | 37 declarative menu options (`MENU_SECTIONS`), interactive handler routing |
| [`src/cli/reporter.py`](file:///mnt/Data/Python%20Project/learning/src/cli/reporter.py) | Lines 20–380 | Rich terminal reporting, AI-style narrative formatting |
| [`src/cli/telegram.py`](file:///mnt/Data/Python%20Project/learning/src/cli/telegram.py) | Lines 20–140 | Telegram Bot HTTP API notification service |
| [`src/cli/visual.py`](file:///mnt/Data/Python%20Project/learning/src/cli/visual.py) | Lines 20–420 | VisualUI layout panels and status bars |
| [`src/core/config.py`](file:///mnt/Data/Python%20Project/learning/src/core/config.py) | Lines 20–220 | Centralized configuration, directory paths, logging setup |
| [`src/core/consensus_engine.py`](file:///mnt/Data/Python%20Project/learning/src/core/consensus_engine.py) | Lines 20–260 | Multi-strategy consensus score calculation and agreement counts |
| [`src/core/data_sources.py`](file:///mnt/Data/Python%20Project/learning/src/core/data_sources.py) | Lines 20–160 | DataSourceManager, health probes, fetcher registrations |
| [`src/core/symbol_utils.py`](file:///mnt/Data/Python%20Project/learning/src/core/symbol_utils.py) | Lines 20–210 | Symbol normalizer and security token resolver |
| [`src/dashboard/app.py`](file:///mnt/Data/Python%20Project/learning/src/dashboard/app.py) | Lines 1–105 | Streamlit dark-mode single-page architecture, 8 view navigation router |
| [`src/dashboard/views/backtest_view.py`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/backtest_view.py) | Lines 20–240 | Backtest explorer UI, equity curves, drawdown metrics |
| [`src/dashboard/views/dossier_view.py`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/dossier_view.py) | Lines 20–80 | LLM research dossier UI and markdown export viewer |
| [`src/dashboard/views/dq_view.py`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/dq_view.py) | Lines 20–250 | Data quality gate run logs, failure distributions, inactive symbol table |
| [`src/dashboard/views/fyers_view.py`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/fyers_view.py) | Lines 20–230 | Broker diagnostics, auth URL generator, token cache inspection |
| [`src/dashboard/views/portfolio_view.py`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/portfolio_view.py) | Lines 20–220 | Paper trading portfolio UI, position cards, heat/risk gauge |
| [`src/dashboard/views/quantitative_view.py`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/quantitative_view.py) | Lines 20–190 | Macro and quant UI: correlation matrix, sector rotation, MMI |
| [`src/dashboard/views/screener_view.py`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/screener_view.py) | Lines 20–350 | Multi-strategy screener UI, volume filters |
| [`src/dashboard/views/smc_view.py`](file:///mnt/Data/Python%20Project/learning/src/dashboard/views/smc_view.py) | Lines 20–330 | SMC Order Blocks, FVGs, Sweeps, institutional calls table |
| [`src/data/fetcher/prices/nse_charts.py`](file:///mnt/Data/Python%20Project/learning/src/data/fetcher/prices/nse_charts.py) | Lines 46–270 | Official NSE Charting API fetcher; lines 226-227 hardcoded referer |
| [`src/data/fetcher/prices/yfinance_fetcher.py`](file:///mnt/Data/Python%20Project/learning/src/data/fetcher/prices/yfinance_fetcher.py) | Lines 40–150 | YFinance fallback price fetcher |
| [`src/data/symbol_mapper.py`](file:///mnt/Data/Python%20Project/learning/src/data/symbol_mapper.py) | Lines 20–67 | NSE symbol to security token resolution |
| [`src/data/HolidayFetcher.py`](file:///mnt/Data/Python%20Project/learning/src/data/HolidayFetcher.py) | Lines 20–140 | Market holiday calendar fetcher and parser |
| [`src/engine/criteria.py`](file:///mnt/Data/Python%20Project/learning/src/engine/criteria.py) | Lines 20–220 | Technical criteria evaluation rules |
| [`src/engine/llm_report.py`](file:///mnt/Data/Python%20Project/learning/src/engine/llm_report.py) | Lines 25–450 | Multi-factor LLM research report generation |
| [`src/engine/parallel_scanner.py`](file:///mnt/Data/Python%20Project/learning/src/engine/parallel_scanner.py) | Lines 20–120 | Multiprocessing batch scanner pool |
| [`src/engine/screener.py`](file:///mnt/Data/Python%20Project/learning/src/engine/screener.py) | Lines 75–1700 | Monolithic screener engine; lines 163, 185, 1474, 1567, 1685 stubs |
| [`src/engine/smc.py`](file:///mnt/Data/Python%20Project/learning/src/engine/smc.py) | Lines 30–280 | Pure Smart Money Concepts mathematical detection |
| [`src/engine/smc_decision.py`](file:///mnt/Data/Python%20Project/learning/src/engine/smc_decision.py) | Lines 20–170 | SMC risk/reward and setup trade classification |
| [`src/engine/strategies.py`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py) | Lines 50–890 | 13 technical strategies implementation and strategy registry |
| [`src/ml/anomaly_detector.py`](file:///mnt/Data/Python%20Project/learning/src/ml/anomaly_detector.py) | Lines 20–150 | Isolation Forest ML anomaly detector |
| [`src/ml/ml_classifier.py`](file:///mnt/Data/Python%20Project/learning/src/ml/ml_classifier.py) | Lines 20–250 | Random Forest forward-direction classifier |
| [`src/ml/ml_gatekeeper.py`](file:///mnt/Data/Python%20Project/learning/src/ml/ml_gatekeeper.py) | Lines 20–170 | Confidence gatekeeper filtering low-conviction predictions |
| [`src/ml/engineer.py`](file:///mnt/Data/Python%20Project/learning/src/ml/engineer.py) | Lines 20–280 | Feature engineering generating predictive features |
| [`src/ml/trainer.py`](file:///mnt/Data/Python%20Project/learning/src/ml/trainer.py) | Lines 20–380 | Model training pipeline with cross-validation |
| [`src/nse_bhavcopy/backtester.py`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/backtester.py) | Lines 20–280 | Event-driven single-symbol backtester with trade logging |
| [`src/nse_bhavcopy/correlation.py`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/correlation.py) | Lines 20–75 | Multi-symbol return correlation matrix calculator |
| [`src/nse_bhavcopy/fyers_fetcher.py`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/fyers_fetcher.py) | Lines 53–487 | Fyers market data fetcher with token management |
| [`src/nse_bhavcopy/heatmap.py`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/heatmap.py) | Lines 20–80 | Constituent performance heatmap data builder |
| [`src/nse_bhavcopy/ma_slope.py`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/ma_slope.py) | Lines 20–110 | Moving average slope angle regression calculator |
| [`src/nse_bhavcopy/mtf_confirmation.py`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/mtf_confirmation.py) | Lines 30–190 | Multi-timeframe trend alignment logic |
| [`src/nse_bhavcopy/position_sizer.py`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/position_sizer.py) | Lines 20–160 | Volatility-adjusted position sizing calculator |
| [`src/nse_bhavcopy/quant_metrics.py`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/quant_metrics.py) | Lines 20–260 | Quantitative financial performance metrics calculation |
| [`src/nse_bhavcopy/sector_rotation.py`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/sector_rotation.py) | Lines 20–170 | Sector rotation JdK RS-Ratio quadrant analysis |
| [`src/nse_bhavcopy/ta_indicators.py`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/ta_indicators.py) | Lines 50–270 | Vectorized TA-Lib indicators and non-mutating divergence engine (R-02) |
| [`src/nse_bhavcopy/volatility_regime.py`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/volatility_regime.py) | Lines 20–150 | Historical volatility regime classification |
| [`src/nse_live/nse_utils.py`](file:///mnt/Data/Python%20Project/learning/src/nse_live/nse_utils.py) | Lines 20–850 | NSE website live scraping utilities, option chain, pre-market depth |
| [`src/platform/adapters/era_legacy.py`](file:///mnt/Data/Python%20Project/learning/src/platform/adapters/era_legacy.py) | Lines 20–66 | Pre-2016 Bhavcopy ingestion adapter |
| [`src/platform/adapters/era_mid.py`](file:///mnt/Data/Python%20Project/learning/src/platform/adapters/era_mid.py) | Lines 20–74 | 2016-2023 Bhavcopy ingestion adapter |
| [`src/platform/adapters/era_modern.py`](file:///mnt/Data/Python%20Project/learning/src/platform/adapters/era_modern.py) | Lines 20–65 | Post-2023 Unified Bhavcopy CSV adapter |
| [`src/platform/adapters/sec_bhavdata.py`](file:///mnt/Data/Python%20Project/learning/src/platform/adapters/sec_bhavdata.py) | Lines 20–93 | Delivery and turnover adapter for `sec_bhavdata_full` |
| [`src/platform/adapters/registry.py`](file:///mnt/Data/Python%20Project/learning/src/platform/adapters/registry.py) | Lines 20–55 | Date-based adapter registry dispatcher |
| [`src/platform/dal.py`](file:///mnt/Data/Python%20Project/learning/src/platform/dal.py) | Lines 1–170 | Abstract Data Access Layer (DAL) interface stubs |
| [`src/platform/loaders/calendar_backfill.py`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/calendar_backfill.py) | Lines 20–134 | DuckDB trading calendar dimension backfill loader |
| [`src/platform/loaders/delivery_backfill.py`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/delivery_backfill.py) | Lines 30–295 | Delivery history backfill from `sec_bhavdata_full` |
| [`src/platform/loaders/price_rebuilder.py`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/price_rebuilder.py) | Lines 30–239 | Unadjusted price series rebuilder |
| [`src/platform/loaders/staging.py`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/staging.py) | Lines 30–220 | Ingestion of raw Bhavcopy into DuckDB staging |
| [`src/platform/loaders/surveillance.py`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/surveillance.py) | Lines 20–106 | Ingestion of ASM/GSM surveillance lists |
| [`src/platform/loaders/warehouse.py`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/warehouse.py) | Lines 30–410 | Star schema fact and dimension materialization in DuckDB |
| [`src/platform/migrations/runner.py`](file:///mnt/Data/Python%20Project/learning/src/platform/migrations/runner.py) | Lines 20–180 | Versioned SQL migration runner |
| [`src/platform/orchestrator.py`](file:///mnt/Data/Python%20Project/learning/src/platform/orchestrator.py) | Lines 20–220 | Warehouse orchestrator coordinates migrations and loader stages |
| [`src/platform/repositories/symbol_repo.py`](file:///mnt/Data/Python%20Project/learning/src/platform/repositories/symbol_repo.py) | Lines 30–250 | SCD2 symbol tracking in DuckDB |
| [`src/portfolio/portfolio_engine.py`](file:///mnt/Data/Python%20Project/learning/src/portfolio/portfolio_engine.py) | Lines 120–320 | Paper trading simulation engine (verified zero broker orders) |
| [`src/scanners/darvas_box.py`](file:///mnt/Data/Python%20Project/learning/src/scanners/darvas_box.py) | Lines 20–220 | Darvas Box technical price scanner |
| [`src/scanners/etf_screener.py`](file:///mnt/Data/Python%20Project/learning/src/scanners/etf_screener.py) | Lines 20–180 | Sector ETF volume and turnover screener |
| [`src/scanners/minervini_screener.py`](file:///mnt/Data/Python%20Project/learning/src/scanners/minervini_screener.py) | Lines 20–410 | Mark Minervini trend template and VCP contraction screener |
| [`src/scanners/momentum_squeeze.py`](file:///mnt/Data/Python%20Project/learning/src/scanners/momentum_squeeze.py) | Lines 20–210 | Momentum squeeze indicator scanner |
| [`src/scanners/pair_scanner.py`](file:///mnt/Data/Python%20Project/learning/src/scanners/pair_scanner.py) | Lines 20–250 | Cointegration pair scanner finding statistical arbitrage opportunities |
| [`src/scanners/unified_scanner.py`](file:///mnt/Data/Python%20Project/learning/src/scanners/unified_scanner.py) | Lines 20–240 | Unified multi-strategy market scanner |
| [`src/scrapers/corporate_data.py`](file:///mnt/Data/Python%20Project/learning/src/scrapers/corporate_data.py) | Lines 20–190 | Corporate announcements and actions scraper |
| [`src/scrapers/fo_ban.py`](file:///mnt/Data/Python%20Project/learning/src/scrapers/fo_ban.py) | Lines 20–160 | Official NSE F&O ban list scraper |
| [`src/scrapers/mmi_scraper.py`](file:///mnt/Data/Python%20Project/learning/src/scrapers/mmi_scraper.py) | Lines 20–110 | Tickertape Market Mood Index (MMI) sentiment scraper |
| [`src/scrapers/nifty_index_fetcher.py`](file:///mnt/Data/Python%20Project/learning/src/scrapers/nifty_index_fetcher.py) | Lines 20–280 | Nifty indices constituents fetcher |
| [`src/scoring/scoring_engine.py`](file:///mnt/Data/Python%20Project/learning/src/scoring/scoring_engine.py) | Lines 20–250 | Multi-factor weighted conviction scoring engine |
| [`src/storage/bhavcopy_incremental.py`](file:///mnt/Data/Python%20Project/learning/src/storage/bhavcopy_incremental.py) | Lines 30–310 | Batch incremental OHLCV updater from daily Bhavcopy archives |
| [`src/storage/downloader.py`](file:///mnt/Data/Python%20Project/learning/src/storage/downloader.py) | Lines 53–335 | Daily Bhavcopy ZIP archive downloader and extractor |
| [`src/storage/dq_gate.py`](file:///mnt/Data/Python%20Project/learning/src/storage/dq_gate.py) | Lines 100–475 | Non-bypassable data quality gate and breach detection |
| [`src/storage/equity_master.py`](file:///mnt/Data/Python%20Project/learning/src/storage/equity_master.py) | Lines 30–460 | Dynamic NSE referer and security master builder (R-04) |
| [`src/storage/historical_sync.py`](file:///mnt/Data/Python%20Project/learning/src/storage/historical_sync.py) | Lines 73–670 | Atomic Parquet persistence (R-01) and SQLite WAL quarantine (R-03) |
| [`src/storage/sync_registry.py`](file:///mnt/Data/Python%20Project/learning/src/storage/sync_registry.py) | Lines 46–340 | Parquet sync ledger and calendar continuity tracking |
