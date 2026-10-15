# Project Map

_Last updated on 2026-10-15 (Unit 9)_

## Canonical package: `src/`

## Entry points (live at root)
- `main.py` — CLI arg parser + dispatch
- `interactive_scanner.py` — interactive menu entry
- `check_data_sources.py` — data source diagnostics
- `download_historical_data.py` — bulk download
- `repair_data.py` — data repair
- `nse_data_fetcher.py` — NSE insider/bulk/block deals (standalone)

## Documentation & sources
- `docs/pine_sources/`          — 12 LuxAlgo Pine Script v6 sources (upstream reference for src/engine/lux_*.py)
- `docs/session/`               — historical session notes (SESSION.md, TASKS.md, DECISION.md, MASTER_CONTEXT.md, STRATEGY.md, PROJECT_STRUCTURE.md)
- `docs/session/CONTINUATION.md` — master resume state (read first in any new session)
- `docs/session/RESUME_PROMPT.md` — copy-paste prompt for new chat sessions
- `docs/*.md`                   — architecture_review.md, screener_analysis_logic.md, strategies.md
- `CHANGELOG.md`, `INSTALLATION.md`, `README.md`, `YFINANCE_FIX_GUIDE.md`, `PROJECT_MAP.md` — kept at root

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

## Tool Configuration

- `pyproject.toml`:
  * `ruff` excludes `_archive` — no linting of archived code
  * `mypy` excludes `_archive` and `src/dashboard` (dynamic Streamlit imports)
  * `pytest.norecursedirs` excludes `_archive`, `data`, `.venv`
  * `pytest.filterwarnings` silences 2 third-party warnings (advanced_ta, sklearn)
  * Known ruff debt: ~1,122 findings (mostly E501 line-length + UP0xx modernizations) — deferred to Unit 10
- `pyproject.toml` baseline snapshot: `_archive/audits/pyproject_before_unit7.toml`

## Archived (do NOT delete — reference only)
- `_archive/merge_this/`                 — old Screeni-py copy (imports `screeni.*`)
- `_archive/scratch/`                    — old experiments
- `_archive/legacy_root/`                — old root scripts / backups
- `_archive/legacy_root/fyers/`          — orphaned OpenAlgo broker extract
- `_archive/legacy_root/profile_scan.py` — stale cProfile helper
- `_archive/legacy_shims/`               — PascalCase compatibility shims (Momentum.py, Trend.py)
- `_archive/legacy_tests/`               — old test scripts
- `_archive/audits/`                     — project_audit.txt, project_backup.txt, project_bundle.txt
- `_archive/audits/pytest_unit5_baseline.txt` — full pytest -v output of the 205/205 pass baseline
- `_archive/audits/pytest_unit6_postfix.txt`  — pytest baseline after Unit 6 fixes
- `_archive/audits/pytest_unit7_postfix.txt`  — post-Unit-7 test baseline
- `_archive/audits/pytest_unit8_postfix.txt`  — pytest baseline after Unit 8 fixes (206 tests)
- `_archive/audits/pytest_unit9_postfix.txt`  — post-Unit-9 test baseline (206 tests)
- `_archive/audits/pyproject_before_unit7.toml` — pre-Unit-7 config snapshot
- `_archive/exports/`                    — Exported_Grouped_Strategies_*.csv (3 files)
- `_archive/debug/`                      — nse_charting_response_TCS.json, scan_profile.prof, tests_baseline.txt
- `_archive/fix_scripts/`                — fix_unit1.py (one-time migration helper)

## Known Issues (fix order)
- [x] Unit 2 — Root scripts import legacy paths (resolved: shims work)
- [x] Unit 3 — Root clutter: moved pine sources → docs/, session docs → docs/session/, audits/exports/debug → _archive/
- [x] Unit 4 — `src/scanners/__init__.py` — BreakoutStrategy shadow removed
- [x] Unit 4 — Case-duplicate files `Momentum.py` / `Trend.py` archived
- [x] Unit 5 — Full pytest baseline: 205/205 PASSED, 0 errors, 19 warnings (2 ours)
- [x] Unit 6 — `datetime.utcnow()` removed from src + tests
- [x] Unit 6 — `src/engine/screener.py::validateCandlePatterns` bug fixed
- [x] Unit 6 — `src/ml/selector.py` cleanup
- [x] Unit 6 — Parallel test fork() warnings eliminated
- [x] Unit 7 — `pyproject.toml`: remove stale `scratch`/`fyers` excludes
- [x] Unit 8 — `fo_ban.py` parser bug fixed (regression test added)
- [x] Unit 8 — `main.py` epilog documents global flag ordering
- [x] Unit 8 — All 13 CLI subcommands validated end-to-end (0 failures)
- [x] Unit 8 — Duplicate validator methods in `src/engine/screener.py` (verified clean in Unit 9 Stage A — 0 duplicates; note was stale)
- [x] Unit 9 — `src/cli/menus.py` NameErrors fixed (LOGGER + Path)
- [x] Unit 9 — `.gitignore` cleaned (deduped, broken line repaired)
- [ ] Unit 10 — Selective ruff modernization (~1,122 findings)
- [ ] Unit 14 — Revive parts of _archive/legacy_root/fyers/ if needed

## Credentials policy
- All secrets live in `.env` (gitignored).
- `data/cache/fyers_token.txt` is per-day and gitignored.
- Historical leaked creds archived at `_archive/legacy_root/test_fyers.py` — MUST be revoked.
