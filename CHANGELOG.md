# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
