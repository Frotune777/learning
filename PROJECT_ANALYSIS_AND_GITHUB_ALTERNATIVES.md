# Sharegenius NSE Platform: Code-Level Architecture Analysis & GitHub Alternatives

**Generated:** 2026-11-18  
**Repository:** `/mnt/Data/Python Project/learning`  
**Target Market:** National Stock Exchange of India (NSE Equities, F&O, ETFs)  
**Primary Focus:** Local-first quantitative research, technical screening, Smart Money Concepts (SMC), and portfolio analytics.

---

## 1. Executive Summary

The **Sharegenius NSE Quantitative Platform** is an institutional-grade, local-first Python application designed for quantitative screening, historical research, and technical analysis on the National Stock Exchange (NSE) of India (~2,400+ equity symbols). 

The platform operates strictly as an **analytical decision-support system** (no live broker order execution exists in the codebase). It ingests official daily Bhavcopy archives, builds an unadjusted Parquet and DuckDB analytical data lake, runs a 13-strategy technical screener combined with machine learning (Random Forest, Lorentzian KNN, Isolation Forest), detects Smart Money Concepts (Order Blocks, FVGs, Sweeps), and serves findings via both a 28-option interactive CLI and a dark-mode Streamlit dashboard.

---

## 2. Code-Level Architectural Analysis

### 2.1 Component Breakdown

```
src/
├── core/               # Configuration, weighted multi-factor consensus engine, signal contracts
├── storage/            # Equity master, historical Parquet sync, Bhavcopy downloader, DQ gate
├── platform/           # DuckDB star schema (dim_symbol, fact_price_daily, fact_delivery_daily)
│   └── contrib/        # Upstream components adapted from siddharthgaur1/nse-warehouse
├── data/               # Market data fetchers (Fyers API v3, YFinance fallback, circuit breakers)
├── engine/             # 13 technical strategies, SMC engine, parallel multiprocessing scanner
├── scanners/           # Specialized screeners (Minervini VCP, TTM Squeeze, Pairs, ETFs)
├── ml/                 # Random Forest classifier, Isolation Forest anomaly detector, feature engineering
├── portfolio/          # Simulated paper trading ledger (cash tracking, position heat)
├── dashboard/          # Streamlit web UI (8 views: Screener, SMC, Portfolio, Backtest, Macro, DQ)
└── cli/                # 28-option REPL, Rich console tables, VisualUI panels, Telegram alerts
```

### 2.2 Deep Code-Level Strengths & Engineering Patterns

1. **Robust Data Pipeline & Atomic Storage:**
   - [`src/storage/historical_sync.py`](file:///mnt/Data/Python%20Project/learning/src/storage/historical_sync.py): Implements atomic Parquet persistence using `tempfile.NamedTemporaryFile` and `os.replace` to prevent corrupted files upon sudden termination or process interruption.
   - [`src/storage/dq_gate.py`](file:///mnt/Data/Python%20Project/learning/src/storage/dq_gate.py): Enforces a strict, non-bypassable Data Quality Gate checking row counts, date bounds, null ratios, and inactive/delisted symbols before running downstream screeners.
   - [`src/storage/sync_registry.py`](file:///mnt/Data/Python%20Project/learning/src/storage/sync_registry.py) & `failed_symbols.db`: Uses SQLite with WAL (Write-Ahead Logging) to track quarantined and failing symbols rather than repeatedly scanning unindexed CSVs.

2. **Point-in-Time Technical Analysis (Zero Lookahead Bias):**
   - [`src/nse_bhavcopy/ta_indicators.py`](file:///mnt/Data/Python%20Project/learning/src/nse_bhavcopy/ta_indicators.py): Point-in-time rolling window RSI/MACD divergence detection calculated without lookahead bias or in-place DataFrame mutations.
   - Vectorized TA-Lib calculations for moving averages (20, 50, 100, 150, 200 EMA/SMA), SuperTrend, Bollinger Bands, ATR, and ADX.

3. **Multi-Strategy Confluence & Consensus Engine:**
   - [`src/engine/strategies.py`](file:///mnt/Data/Python%20Project/learning/src/engine/strategies.py): Computes 13 distinct strategies (Minervini VCP, TTM Squeeze, Dual SuperTrend, Lorentzian KNN Classification, Turtle Breakouts, RDX, 100 SMA base breakouts, Super BO, DMADMA, Buy Low Sell High, Nifty Shop).
   - [`src/core/consensus_engine.py`](file:///mnt/Data/Python%20Project/learning/src/core/consensus_engine.py): Scores tickers using weighted conviction matrix across technical indicators, trend confirmation, and volume surges.

4. **Institutional Smart Money Concepts (SMC) & LuxAlgo Ports:**
   - [`src/engine/smc.py`](file:///mnt/Data/Python%20Project/learning/src/engine/smc.py) & [`src/engine/smc_decision.py`](file:///mnt/Data/Python%20Project/learning/src/engine/smc_decision.py): Pure Python implementation of institutional ICT concepts: Order Blocks (OB), Fair Value Gaps (FVG), Liquidity Sweeps, and Break of Structure (BOS), generating automated Entry, SL, Target 1, Target 2, and Risk-to-Reward (R:R) calculations.
   - [`src/engine/lux_*.py`](file:///mnt/Data/Python%20Project/learning/src/engine): Python ports of 12 LuxAlgo TradingView Pine Script v6 algorithms (Nadaraya-Watson Envelope, Savitzky-Golay Filter, Weinstein Stage Analysis, Volume Profile, VSA, BOS Pullback).

5. **Analytical Star-Schema Warehouse:**
   - [`src/platform/loaders/warehouse.py`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/warehouse.py): Uses DuckDB to build an analytical star schema (`dim_symbol`, `fact_price_daily`, `fact_delivery_daily`) with versioned migrations (`V001`-`V003`).

### 2.3 Code-Level Rough Edges & Technical Debt

- **Stubs & Placeholders:**
  - [`src/analysis/MultiTimeframeBacktest.py`](file:///mnt/Data/Python%20Project/learning/src/analysis/MultiTimeframeBacktest.py) is a 5-line empty stub.
  - [`src/engine/screener.py`](file:///mnt/Data/Python%20Project/learning/src/engine/screener.py) contains legacy placeholder logic for certain VSA and RS rating branches.
- **Legacy Shims & Duplication:**
  - Multiple parallel scanner entry points (`src/scanners/screenipy.py`, `src/scanners/unified_scanner.py`, `src/engine/parallel_scanner.py`) carry residual legacy scaffolding inherited from Screeni-py.
- **Scraper Fragility:**
  - Custom HTTP scrapers for NSE corporate actions, holiday calendars, and F&O ban lists require regular maintenance whenever NSE alters site cookies or anti-bot headers.

---

## 3. Direct Ancestors & Embedded Upstreams in This Repo

Audit of the codebase, git history, and comments reveals that parts of this platform were directly inspired by or adapted from several open-source GitHub projects:

1. **`pranjal-joshi/Screeni-py` & `pkjmesra/PKScreener`:**
   - Evidence: Commit `398d6e6`, `src/scanners/screenipy.py`, legacy imports, and 28-option terminal menu architecture.
2. **`siddharthgaur1/nse-warehouse`:**
   - Evidence: Directly adapted under [`src/platform/contrib/nse_warehouse/`](file:///mnt/Data/Python%20Project/learning/src/platform/contrib/nse_warehouse/README.md) for UDiFF Bhavcopy schema normalization, corporate action inference, and data quality checks.
3. **`powernse`:**
   - Evidence: Installed dependency (`pyproject.toml:32`) and imported in [`src/platform/loaders/landing.py`](file:///mnt/Data/Python%20Project/learning/src/platform/loaders/landing.py) for Bhavcopy downloading.
4. **`hudson-and-thames/advanced-ta`:**
   - Evidence: Cited in `pyproject.toml:54` for the Lorentzian Distance KNN classification algorithm.
5. **`marketcalls/openalgo`:**
   - Evidence: Referenced in legacy broker extracts for Fyers authentication and data streaming.
6. **`LuxAlgo Pine Script v6`:**
   - Evidence: 12 TradingView Pine Script files in [`docs/pine_sources/`](file:///mnt/Data/Python%20Project/learning/docs/pine_sources) ported into Python algorithms in `src/engine/`.

---

## 4. Similar & Alternative Open-Source Projects on GitHub

If you want to replace, cross-verify, or extend parts of this application, the following open-source projects on GitHub cover similar domains:

### 4.1 Stock Screeners & Market Scanners (NSE / Indian Market)

| Project | GitHub Repository | Primary Strengths | Code Overlap with Sharegenius | Recommendation |
|---|---|---|---|---|
| **PKScreener** | [`pkjmesra/PKScreener`](https://github.com/pkjmesra/PKScreener) | The active, community-maintained successor to Screeni-py. Features 100+ technical scans, automated Telegram bot (`@nse_pkscreener_bot`), Dockerized runs, and PyPI packaging. | High (~75% overlap on screener logic, CLI menu patterns, and candlestick filters). | **High Value Alternative.** Can be used as a standalone scanner or benchmark for technical scan rules. |
| **Screeni-py** | [`pranjal-joshi/Screeni-py`](https://github.com/pranjal-joshi/Screeni-py) | The original open-source stock screener for NSE/BSE breakout stocks and consolidation patterns. | Historical base of the CLI menu and scanner modules in this repo. | Mostly superseded by PKScreener, but serves as reference for legacy logic. |

### 4.2 NSE Data Ingestion, Bhavcopies & Market Data

| Project | GitHub Repository | Primary Strengths | Code Overlap with Sharegenius | Recommendation |
|---|---|---|---|---|
| **jugaad-data** | [`jugaad-py/jugaad-data`](https://github.com/jugaad-py/jugaad-data) | The de-facto standard Python library for NSE historical data, Bhavcopies, indices, derivatives, and live market quotes. Features built-in disk caching and cookie management. | High overlap with `src/storage/downloader.py` and `src/data/fetcher/`. | **Strongly Recommended.** Using `jugaad-data` can eliminate custom, fragile web scrapers for quotes and bhavcopies. |
| **nselib** | [`RuchiTanmay/nselib`](https://github.com/RuchiTanmay/nselib) | Rich library specifically built for NSE scraping: block/bulk deals, FII/DII data, F&O ban lists, holiday calendars, and deliverable position reports. | Direct overlap with `src/scrapers/fo_ban.py`, `src/scrapers/corporate_data.py`, and `src/data/HolidayFetcher.py`. | **Recommended.** Can replace custom scrapers with maintained upstream functions. |
| **nse-warehouse** | [`siddharthgaur1/nse-warehouse`](https://github.com/siddharthgaur1/nse-warehouse) | DuckDB-powered analytical warehouse for NSE Bhavcopy archives with corporate action adjustment and multi-era schema normalization. | Already partially embedded in `src/platform/contrib/nse_warehouse/`. | Continue maintaining alignment with upstream releases. |
| **GetBhavCopy** | [`AricKaji/GetBhavCopy`](https://github.com/AricKaji/GetBhavCopy) & [`pparesh25/NSE_BSE_Downloader`](https://github.com/pparesh25/NSE_BSE_Downloader) | Multi-threaded standalone GUI/CLI downloaders for NSE/BSE Bhavcopies. | Alternative for automated daily EOD archive downloads. | Useful utility if external standalone download is preferred. |

### 4.3 Smart Money Concepts (SMC) & Institutional Trading

| Project | GitHub Repository | Primary Strengths | Code Overlap with Sharegenius | Recommendation |
|---|---|---|---|---|
| **smartmoneyconcepts** | [`joshyattridge/smart-money-concepts`](https://github.com/joshyattridge/smart-money-concepts) | Dedicated, highly starred pure-Python library for Fair Value Gaps (FVG), Order Blocks (OB), BOS, CHoCH, and liquidity levels on Pandas DataFrames. | Direct overlap with `src/engine/smc.py` and `src/engine/lux_ifvg_sweeps.py`. | **Top Pick for SMC.** Adopting this library can reduce ~400 lines of custom SMC indicator code to standardized calls. |
| **SMC-Screener** | [`Prasad1612/SMC-Screener`](https://github.com/Prasad1612/SMC-Screener) | Python screener and Matplotlib visualizer applying institutional SMC on stock universes (Nifty 50, custom lists). | Similar to `smc-scan` CLI command and `smc_view.py` Streamlit page. | Great reference for visual plotting of mitigated/unmitigated zones. |

### 4.4 Broker Integration & Live Algorithmic Execution

| Project | GitHub Repository | Primary Strengths | Code Overlap with Sharegenius | Recommendation |
|---|---|---|---|---|
| **OpenAlgo** | [`marketcalls/openalgo`](https://github.com/marketcalls/openalgo) | Full-featured, self-hosted open-source algorithmic trading hub supporting 38+ Indian stock brokers (Fyers, Zerodha, AngelOne, Upstox, Dhan, Shoonya). Provides unified REST API and WebSockets. | Fills the missing live trading execution boundary of this repo. | **Best Choice if Live Trading is Needed.** Keep Sharegenius as the analytical brain and route trade orders via OpenAlgo's unified API. |

### 4.5 Quantitative Backtesting Engines

| Project | GitHub Repository | Primary Strengths | Code Overlap with Sharegenius | Recommendation |
|---|---|---|---|---|
| **vectorbt** | [`polakowo/vectorbt`](https://github.com/polakowo/vectorbt) | Lightning-fast vectorized backtesting engine using NumPy and Numba. Already installed in `pyproject.toml`. | Used in `src/analysis/backtesting.py`. | Continue using for multi-asset parameter sweeps. |
| **backtesting.py** | [`kernc/backtesting.py`](https://github.com/kernc/backtesting.py) | Lightweight, intuitive event-driven backtesting engine with Bokeh interactive equity curve visualizers. | Overlaps with `src/nse_bhavcopy/backtester.py`. | Clean alternative for single-stock event-driven backtests. |

---

## 5. Comparative Capability Matrix

| Feature / Domain | Current Sharegenius Codebase | PKScreener | OpenAlgo | nse-warehouse + smartmoneyconcepts |
|---|---|---|---|---|
| **Target Universe** | 2,400+ NSE Equities | NSE & BSE Equities / F&O | Multi-broker Indian equities, F&O, Crypto | NSE Equities |
| **Local Data Lake** | Parquet + DuckDB Star Schema | In-memory / Cached yfinance | Broker API / In-memory | DuckDB Star Schema |
| **SMC Detection** | Custom `smc.py` + LuxAlgo ports | Basic chart patterns | Third-party signals (TradingView, etc.) | Vectorized OB, FVG, BOS, CHoCH |
| **Consensus Engine** | Weighted 13-strategy scoring | Multi-factor checklist | Custom flow rules | N/A (Indicator library) |
| **User Interfaces** | Streamlit (8 views) + 28-option CLI | Interactive CLI + Telegram Bot | React Web UI + No-code Flow Canvas | N/A (Library / CLI) |
| **Live Order Execution** | **No (Strictly Assist Only)** | No | **Yes (38+ Indian Brokers)** | No |
| **Machine Learning** | Random Forest + Isolation Forest | AI Candle / Pattern summaries | ML through Python SDK | N/A |
| **Data Quality Gate** | Strict, non-bypassable DQ Gate | Basic error handling | Broker API validation | Code-based quality checks |

---

## 6. Strategic Recommendations: What to Keep vs. What to Adopt

### 1. What to KEEP in Sharegenius (High Value & Unique)
- **The Parquet & DuckDB Data Lake:** The local-first historical Parquet storage with atomic writes and DuckDB analytical queries is superior to cloud-dependent screeners that hit rate limits.
- **The Consensus Scoring Engine:** The weighted confluence algorithm in `src/core/consensus_engine.py` is proprietary and highly tailored.
- **The Streamlit Dark-Mode Dashboard:** The multi-page visual cockpit (SMC Studio, Portfolio Risk Manager, Screener Leaderboard) provides a unified experience unmatched by standard CLI screeners.

### 2. What to ADOPT / REPLACE from GitHub (Reducing Code Debt)
- **Replace custom SMC math with `smartmoneyconcepts`:**  
  Replacing custom order block and fair value gap calculations with `joshyattridge/smart-money-concepts` will eliminate maintenance overhead and ensure edge-case-tested market structure math.
- **Replace fragile scrapers with `jugaad-data` and `nselib`:**  
  Instead of custom HTTP requests that break when NSE changes headers (e.g., in `HolidayFetcher.py` or `fo_ban.py`), use `jugaad-data` for Bhavcopies and `nselib` for corporate actions and F&O data.
- **Use `marketcalls/openalgo` if live trading is ever needed:**  
  If the project scope expands from analysis to automated execution, do not write custom broker connectors. Connect Sharegenius signals to a local OpenAlgo instance to trade on Zerodha, Fyers, AngelOne, or Dhan out of the box.
- **Benchmark against `pkjmesra/PKScreener`:**  
  Use PKScreener to validate screener candidate lists and cross-verify momentum breakout signals.
