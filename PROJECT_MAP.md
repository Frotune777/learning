# Project Map

_Last updated on 2026-10-15 (Unit 2)_

## Canonical package: `src/`

## Entry points (live at root)
- `main.py` — CLI arg parser + dispatch
- `interactive_scanner.py` — interactive menu entry
- `check_data_sources.py` — data source diagnostics
- `download_historical_data.py` — bulk download (⚠ broken imports — Unit 2)
- `repair_data.py` — data repair (⚠ broken imports — Unit 2)
- `nse_data_fetcher.py` — NSE insider/bulk/block deals (standalone)

## Packages under `src/`
- `src/core/`         — Config, UserPrefs, Signal, decorators, symbol_utils, consensus_engine, data_sources
- `src/data/`         — Fetchers, storage, health, paper, manager, DataRepository
- `src/analysis/`     — Indicators, patterns, backtesting, optimizer, validator
- `src/scanners/`     — 13+ scanner strategies
- `src/engine/`       — Screener, scanner, orchestrator, SMC, criteria
- `src/ml/`           — FeatureEngineer, MLTrainer, MLClassifier, AnomalyDetector, selector
- `src/ui/`           — VisualUI, MenuService, reporting, telegram, universe
- `src/cli/`          — actions, menus, reporter, formatters, visual
- `src/dashboard/`    — Streamlit app + views + pages
- `src/storage/`      — Downloader, historical_sync, bhavcopy_incremental, sync_registry, smc_db, equity_master
- `src/nse_bhavcopy/` — Backtester, quant_metrics, risk_metrics, sector_rotation, etc.
- `src/nse_live/`     — nse_utils
- `src/portfolio/`    — portfolio_engine
- `src/presentation/` — daily_signal_reporter
- `src/scoring/`      — scoring_engine
- `src/scrapers/`     — corporate_data, fo_ban, mmi_scraper, nifty_index_fetcher

## Separate modules (not part of `src/`)
- `tests/`   — pytest suite

## Archived (do NOT delete — reference only)
- `_archive/merge_this/`                 — old Screeni-py copy (imports `screeni.*`)
- `_archive/scratch/`                    — old experiments
- `_archive/legacy_root/`                — old root scripts / backups
- `_archive/legacy_root/fyers/`          — orphaned OpenAlgo broker extract
- `_archive/legacy_root/profile_scan.py` — stale cProfile helper
- `_archive/legacy_tests/`               — old test scripts

## Known Issues (fix order)
- [x] Unit 2 — Root scripts import legacy paths (resolved: shims work)
- [ ] Unit 3  — `src/scanners/__init__.py` — `BreakoutStrategy` imported twice (shadowing)
- [ ] Unit 8  — `src/engine/screener.py::validateCandlePatterns` — `patterns_found` undefined
- [ ] Unit 9  — `src/ml/selector.py` — strategies commented out
- [ ] Unit 14 — Revive parts of _archive/legacy_root/fyers/ if needed
- [ ] Unit 3  — Case-duplicate files: `Momentum.py` / `momentum.py`, `Trend.py` / `trend.py`
- [ ] Unit 8  — Duplicate validator methods in `src/engine/screener.py`

## Credentials policy
- All secrets live in `.env` (gitignored).
- `data/cache/fyers_token.txt` is per-day and gitignored.
- Historical leaked creds archived at `_archive/legacy_root/test_fyers.py` — MUST be revoked.
