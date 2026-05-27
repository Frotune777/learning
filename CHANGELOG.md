# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
