# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-06-01

### Added
- Ported and integrated 5 advanced trading strategies: Minervini Volatility Contraction Pattern (VCP), TTM Squeeze (Bollinger Band compression inside Keltner Channels), Dual Supertrend (Pine-Script match), Candlestick Pattern Recognition, and Lorentzian Machine Learning Classification.
- Overhauled consensus and scoring engine to use strategy weightings, trend state classification (BULL RUN, RECOVERY, BEAR TERRITORY, SIDEWAYS), and dynamic Quant Decision Support (simulated trading actions, confidence metrics, ATR-based stops & targets).
- Added bulleted AI Quant Narrative explaining positive catalysts, risk factors, and actionable verdicts.
- Developed state-of-the-art dark-mode Streamlit dashboard with detailed Landing Page, Daily Signals Explorer, and a double-tabbed Strategy Inspector (Leaderboard & Deep-Dive Inspector).
- Built a premium double-border visual CLI REPL menu using `VisualUI` panels, tables, and categorized options.
- Phase 5 Data Quality Safeguards: 
  - Integrated lightweight `requests` + `BeautifulSoup` parsing for Tickertape's Market Mood Index (MMI) via `__NEXT_DATA__` React state extraction (100x faster, zero local Chrome dependency).
  - Added robust CSV fallbacks for NSE Index constituents loading from `nsearchives.nseindia.com` in `get_index_details` and `nifty_index_fetcher.py` to bypass Cloudflare and 404 blocks.
  - Implemented interactive CLI Option `26` (Data Quality & Auto-Healer) to diagnose and heal low-coverage equities.
  - Added a Data Quality status KPI card to the Streamlit Strategy Inspector page.

### Changed
- Refactored `screener.screen_stocks` to support in-memory passes with optional CSV exports.
- Upgraded the entire platform test coverage to 187 passing unit and integration tests.

## [1.2.0] - 2026-05-30

### Added
- Integrated `CorporateDataScraper` to automatically fetch and cache NSE Corporate Actions, Announcements, Event Calendars, and Insider Trading (SEBI Reg 7) data.
- Added fundamental overlay columns (`Corp Action`, `Catalyst Boost`, `Event Risk (Days)`, `Insider Score`) to the Technical Screener outputs for the Final, Swing, and Super lists.
- Decoupled `main.py` "God Script" into modularized components inside `src/cli/` (actions, menus, formatters) for clean REPL execution.
- Implemented `validate_symbol` and input parsing utilities in `src/core/utils.py`.

### Changed
- Refactored `get_event_calendar()` in `NseUtils` to capture all corporate events (AGMs, Board Meetings) instead of strictly financial results.
- Fixed directory structure mappings causing `master_not_found` errors.

## [1.1.0] - 2026-05-27

### Added
- Integrated high-performance Parquet local caching under `data/processed/.yfcache/` for historical Yahoo Finance data.
- Implemented **Incremental Daily Cache CRUD** updating closing prices directly from downloaded daily Bhavcopy CSV records.
- Created standalone connectivity diagnostic and checking scripts inside `scratch/`.
- Enforced strict 50, 100, and 200 look-back lookups for DMA indicators to flag short-history IPO tickers safely.
- Implemented single-ticker MultiIndex wrapping to prevent pipeline failure during single-chunk downloads.
- Added ZIP archive validation checks (PK signature and non-empty namelists) in `downloader.py`.
- Developed comprehensive test coverage reaching 98% with targeted unit mocks in `tests/test_screener.py`.

### Changed
- Upgraded `yfinance` to `1.4.0` resolving empty dataframe and IP block errors permanently.
- Standardized turnover columns by normalizing lakhs-denominated values (`TURNOVER_LACS`) to Rupee values.
- Refined ETF/BEES regex filter patterns to strictly match boundaries, protecting legitimate tickers like GOLDIAM and LIQUIDFLEX.
- Hardened exception bubble-up and trace logs inside orchestrator loop in `lerarning.py`.

## [1.0.0] - 2026-05-26

### Added
- Created institutional-grade modular core in `src/nse_bhavcopy/downloader.py` implementing `BhavcopyDownloader` class.
- Configured local directories for raw ZIP downloads (`data/raw/`) and processed equity CSV exports (`data/processed/`).
- Added TOML config loader in `lerarning.py` using Python's built-in `tomllib` to safely read options from `pyproject.toml`.
- Implemented comprehensive `pytest` test suite in `tests/test_downloader.py` reaching 100% test coverage with robust unit mocks.
- Formulated static typing specifications checking cleanly with strict `mypy`.
- Added configuration templates and standardizing linter constraints with `ruff`.

### Changed
- Refactored `lerarning.py` into a clean local automation script running in English.
- Replaced Google Sheet updates with automatic local CSV data files showing Top 250 EQ stocks by daily turnover.

### Removed
- Completely dropped Google Sheet client bindings (`gspread`, `oauth2client`) and dependencies.
