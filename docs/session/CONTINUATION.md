# Project Continuation State

**Last updated:** 2026-10-16 (after Unit 13)
**Repo root:** /mnt/Data/Python Project/learning
**Canonical package:** `src/`

## Working Conventions (NON-NEGOTIABLE)

1. **Never delete anything.** Move to `_archive/` instead.
2. **Never use `git add -A`** — stage specific paths only.
3. **`src/` and `tests/` are protected** — no unit may modify them unless explicitly listed in that unit's scope.
4. **Dry-run first** — any filesystem operation runs in preview mode before `--apply`.
5. **Each unit = one commit**, with message format `chore(unit-N): ...` or `fix(unit-N): ...`.
6. **User commits manually** — the AI agent never runs `git commit` / `git push`.
7. **Discovery before fix** — every unit starts with a read-only inventory stage (Stage A).
8. **`.env` secrets never printed** — only key names, never values.
9. **`PROJECT_MAP.md` is updated** at the end of every structural unit.
10. **Commit messages are surgical** — no drive-by edits bundled in.
11. **No magic numbers in tests.** When tests need data, use real sources — network APIs or actual stored data files (Parquet, CSV). If a real source is too slow for a unit test, capture a snapshot of real data as a fixture and check in the fixture. Never fabricate synthetic candles, prices, or volumes just to make an assertion pass.

## Commit History

| Unit | Commit | Description |
|------|--------|-------------|
| 1 | `fa81afb` | Archive duplicates, harden .env/.gitignore, add PROJECT_MAP |
| 2 | `61a2d27` | Quarantine orphaned fyers/, archive stale profile_scan.py, untrack runtime log |
| 3 | `31c4c90` | Reorganize root — pine sources, session docs, audits, exports, debug to subdirs |
| 4 | `d4d3660` | Fix BreakoutStrategy shadowing + archive case-duplicate shims |
| 5 | `0a6af31` | Full pytest baseline — 205/205 PASSED, 19 warnings |
| 6 | `259ca8a` | Fix 5 items: utcnow×2, fork spawn, patterns_found bug, selector cleanup |
| 7 | `c2ff56d` | pyproject.toml cleanup — remove scratch/fyers, exclude _archive, silence 2 third-party warnings |
| 8 | `10427fb` | Fix fo_ban parser bug + document main.py flag ordering + regression test |
| 9 | `e5588c0` | Fix 2 NameErrors in menus.py + clean .gitignore + correct stale PROJECT_MAP note |
| 10 | `da1b0d5` | Ruff UP+I modernization — 85 files, 2933-line diff, 0 imports deleted |
| 11 | `77bfe06` | Fix src.ui ↔ src.data circular import; add cold-start regression test (16 tests); encode Rule 11 |
| 12 | (see git log HEAD) | Harden 15 shims with __all__; F401 cleanup (120 findings → 0); UP038+UP031 fixes (10 manual) |
| 13 | `00aa7d0` | Fix sync-history --resume, screen --processed-dir, screener CLOSE<=0 guard; add 4 CLI regression tests |
| 14 | (audit) | Data quality audit across all 2,699 Parquet files (read-only) |
| 15 | (see git log HEAD) | Add holidays config, fix health fallback/date typing, sync 1d data |

## Current Status

- **Completed:** Units 1–15
- **Current unit:** 15 — commit pending (Stage B)
- **Project health:** ✅ 228/228 tests pass · ✅ 0 F401 · ✅ 0 UP · ✅ 0 F821 · ✅ 0 warnings · ✅ Incremental 1d sync verified (2,293 current files) · ⚠️ E501/W29* cosmetic (skipped by choice)

## Next Unit Plan (Unit 14 — Options)

**The project is functionally complete.** Three candidate tracks for Unit 14:

**Track A — Cosmetic cleanup (low value, safe):**
- W291/W293 trailing whitespace
- W292 (missing newline at EOF)
- Skip E501 (line length) — pure churn

**Track B — Revive pieces of `_archive/legacy_root/fyers/`:**
- Only if a specific feature (order routing, HSM streaming) is needed
- Requires porting OpenAlgo scaffolding (broker/, database/, utils/)
- Estimated 1-2 days

**Track C — New feature / real usage:**
- Start using the pipeline for real analysis
- Any bugs found become new units

**Recommendation:** Stop here. Project is clean, tested, and validated.
Add new units only in response to real usage discoveries.

## Key Decisions Log

- **`src/` is canonical.** `merge this/` (Screeni-py) archived. `fyers/` (OpenAlgo) archived.
- **`src.nse_bhavcopy/fyers_fetcher.py` is the real Fyers integration** — has 20 live references, remains active.
- **Root scripts are all healthy** — no import fixes needed (Stage A of Unit 2 confirmed).
- **`logs/data_repair.log` untracked** — runtime artifact, not source.
- **`.agents/` and `.antigravitycli/` kept tracked** — IDE config, needed by agent.
- **`fix_unit1.py` archived** — one-time migration helper, no longer needed.
- **Pine files moved to `docs/pine_sources/`** — upstream reference for `src/engine/lux_*.py` ports.
- **Unit 4:** Removed dead `BreakoutStrategy` shadow in `src/scanners/__init__.py`. The `.screenipy.BreakoutStrategy` class stays in its module but is no longer package-re-exported (zero callers). `.breakout.BreakoutStrategy` remains the canonical one used by `src/engine/screener.py`.
- **Unit 4:** Redirected `src/scanners/menu_parity.py` to import `TrendIndicators` from `.trend` (lowercase). Archived both `Momentum.py` and `Trend.py` PascalCase shims to `_archive/legacy_shims/`.
- **Unit 4:** `CONTINUATION.md` uses `(see git log HEAD)` for the current commit hash — avoids chicken-and-egg between writing the file and committing it.
- **Unit 5:** Test suite runs 205/205 green in 21.77s. Zero import errors, zero runtime failures in any tested code path. Project health is significantly better than the original bundle suggested.
- **Unit 5:** Baseline snapshot saved to `_archive/audits/pytest_unit5_baseline.txt` as the reference point for all future comparisons.
- **Unit 5:** 19 warnings — only 2 originate in our code (`utcnow()` in one test; `fork()` in parallel engine test). The other 17 come from third-party libs (`advanced_ta`, `sklearn`) and Python 3.13 stdlib. Our fixes will target only the 2; the rest are silenced via pytest config in a later unit.
- **Unit 5:** Bulk of remaining work is documentation/cleanup, not bug fixes. Project is nearly done with the "fix what it has" phase.
- **Unit 6:** Fixed `datetime.utcnow()` in both test and **production** code (`src/nse_bhavcopy/fyers_fetcher.py:607`) — Python 3.14 will remove it.
- **Unit 6:** Forced `multiprocessing.set_start_method("spawn")` in parallel tests — eliminates 8 fork() warnings without affecting other tests (verified no other test uses multiprocessing).
- **Unit 6:** Fixed real bug in `src/engine/screener.py::validateCandlePatterns` — `patterns_found` was never initialized, silently swallowing all exceptions via `except: return False`. Method was a no-op since introduction. Now initializes a proper list.
- **Unit 6:** Cleaned `src/ml/selector.py` — removed 3 dead commented imports, kept empty `self.strategies` dict but now properly typed and documented. `AutoStrategySelector` remains import-compatible.
- **Unit 6:** Warnings reduced from 19 → ~10. Remaining warnings are all third-party (advanced_ta, sklearn) and will be silenced via pytest config in Unit 7.
- **Unit 7:** Replaced stale `scratch`/`fyers` excludes with `_archive` in all 3 tool configs (ruff, mypy, pytest.norecursedirs). Archives are now invisible to linters and test discovery, so historical code won't produce false positives.
- **Unit 7:** Added module-scoped `filterwarnings` for the 2 remaining third-party warning categories (advanced_ta bitwise-`~`, sklearn All-NaN). Module scope ensures we don't accidentally hide identical warnings from our own code.
- **Unit 7:** Baseline saved as `_archive/audits/pyproject_before_unit7.toml` for diff comparison if any tooling behavior regresses later.
- **Unit 8:** Confirmed all 13 CLI subcommands operational via `--help` + live `fo-ban` network call. Zero tracebacks, zero hangs.
- **Unit 8:** Fixed real bug in `src/scrapers/fo_ban.py` — parser was matching numeric row-index column ("1", "2", "3") instead of the ticker column. Added regression test `test_fo_ban_parses_new_nse_format`. Test count now 206.
- **Unit 8:** Documented argparse flag ordering in `main.py` epilog (global flags before subcommand). Not refactoring — argparse behavior is standard and correct.
- **Unit 8:** NSE's F&O ban list format changed to `N,SYMBOL` — parser now skips numeric cells.
- **Unit 9:** Found and fixed 2 real `F821` (undefined-name) bugs in `src/cli/menus.py` — `LOGGER` at line 937 and `Path` at line 2460. Both would have caused `NameError` at runtime on menu actions `data_quality` and `llm_dossier`.
- **Unit 9:** Verified the "duplicate validator methods" note in PROJECT_MAP.md was stale — 0 duplicate method definitions exist in `screener.py`. Corrected the note.
- **Unit 9:** Rewrote `.gitignore` from scratch to remove duplicates and fix the `.aider*#...` missing-newline bug.
- **Unit 9:** Deferred ruff modernization (1,122 findings, 672 auto-fixable) to Unit 10 for controlled, selective fixes — bulk `--fix` was too invasive for one commit.
- **Unit 10:** Applied `ruff check --select UP,I --fix` across the codebase. 2,933 lines of diff, 85 files, all modernization-only (no logic changes). Chose UP+I only (excluded F401, W, RUF*) for maximum safety and to keep the diff review manageable in one commit.
- **Unit 10:** Zero imports deleted. All shims (`DataRepository`, `Fetcher`, `VisualUI`, etc.) preserved intact.
- **Unit 10:** F401 (unused imports) deferred to Unit 11 for per-file review, since some could be intentional re-exports.
- **Unit 11:** Found and fixed a real circular import in `src/data/manager.py`. Chain: `src.ui/__init__` → `src.ui.universe` → `src.data.Fetcher` → `src.data/__init__` → `src.data.manager` → `download_historical_data` → `src.ui.StockUniverseSelector` → (partially-initialized `src.ui.universe`) → ImportError.
- **Unit 11:** Fix = move 3 top-level imports (`download_historical_data as dhd`, `repair_data as rd`, `from src.ui.StockUniverseSelector import StockUniverseSelector`) from module top into the methods that use them. Zero logic changes.
- **Unit 11:** Added `tests/test_no_circular_imports.py` — 16 parametrized tests that each spawn a fresh Python subprocess and verify a specific import works from a cold start. This catches cycles that pytest's forgiving import order hides.
- **Unit 11:** Encoded **Rule 11** in Working Conventions: tests must use real data sources (network, Parquet, captured fixtures). No fabricated dummy numbers.
- **Unit 12:** Confirmed shims would have been wiped by F401 (Ruff proposed removing 16 imports across 15 one-line files). Fixed by hardening each shim with an explicit `__all__` declaration. This is now the standard pattern for all shim files.
- **Unit 12:** Applied `ruff check --select F401 --fix` — 120 findings resolved (10 test, 5 root scripts, 89 src, 0 __init__, 0 shim post-hardening).
- **Unit 12:** UP035 (47 findings) auto-resolved as a side effect of F401 — they were all on unused typing imports left over from Unit 10's UP006/007 modernization.
- **Unit 12:** Fixed UP038 (isinstance tuple → `|` syntax, 5 instances) and UP031 (% format → f-string, 5 instances). No remaining UP findings.
- **Unit 12:** Shims now have `__all__` = same pattern as `__init__.py` files. Future ruff runs will never strip them.
- **Unit 13:** Real pipeline validated end-to-end with live NSE + Yahoo data. build-master fetched 2,699 securities + 25 Nifty indices; YFinanceFetcher pulled 2 years of daily OHLCV for RELIANCE/TCS/INFY; StockScreener produced real TA signals and 9 output CSVs.
- **Unit 13:** Fixed 3 real runtime bugs found by the live smoke test: sync-history CLI missing --resume arg (HIGH), screen --processed-dir ignoring --data-dir (MED), and ZeroDivisionError on CLOSE=0 in the in-memory candle insert (LOW). All three passed import tests, all three failed at runtime with real data.
- **Unit 13:** Added `tests/test_cli_args.py` with 4 subprocess-based tests that spawn the real `main.py` and inspect actual output. No mocks. Rule 11 compliant. Test count 222 → 226.
- **Unit 13:** CLI defaults now derive from `--data-dir` instead of hardcoded project paths. This makes sandbox runs actually isolated.
- **Unit 14:** Data quality audit across all 2,699 Parquet files found 95.96% ending at 2026-06-08 due to raw bhavcopy cache boundary.
- **Unit 15:** Added `config/holidays.json` (source of truth from TAValidator) and wired DataHealthCheck fallback + warning. Fixed `SyncRegistry` mixed-date TypeError on sort/max with `pd.to_datetime`. Added regression test suite `tests/test_sync_registry.py` (test count 226 → 228). Ran `bhavcopy-sync --days 135` pulling all missing daily Bhavcopy ZIPs from NSE archives, updating 2,423 symbols and bringing 2,293 1d parquet files and 100% of Nifty 50/100/200 symbols to 2026-10-15.

## Archive Layout

archive/
merge_this/ (Screeni-py copy)
scratch/ (old experiments)
legacy_root/
fyers/ (orphaned OpenAlgo — has STATUS.md)
profile_scan.py
project_backup.py
scan_project.py
check_yfinance_fixed.py
screener_v2.py
test_fyers.py
.env copy.example
legacy_shims/ (Momentum.py, Trend.py)
legacy_tests/ (empty — reserved for future)
audits/ (project_audit.txt, project_backup.txt, project_bundle.txt, pytest_unit5_baseline.txt, pytest_unit6_postfix.txt, pytest_unit7_postfix.txt, pyproject_before_unit7.toml, pytest_unit8_postfix.txt, pytest_unit9_postfix.txt, pytest_unit10_postfix.txt, pytest_unit11_postfix.txt, pytest_unit12_postfix.txt, pytest_unit13_postfix.txt)
exports/ (Exported_Grouped_Strategies*.csv)
debug/ (nse_charting_response_TCS.json, scan_profile.prof, tests_baseline.txt)
fix_scripts/ (fix_unit1.py)


## How to Resume in a New Chat

See `docs/session/RESUME_PROMPT.md` — paste its contents at the start of any new chat.

## Known Issues (open)

- [x] Unit 4 — Audit `__init__.py` files for shadowed imports (fixed: BreakoutStrategy dedup)
- [x] Unit 4 — Case-duplicate files (`Momentum.py`, `Trend.py`) archived to `_archive/legacy_shims/`
- [x] Unit 5 — First full pytest run: 205/205 PASSED (baseline saved)
- [x] Unit 5 — 0 import errors, 0 runtime failures across src/ and tests/
- [x] Unit 6 — `datetime.utcnow()` in test + src
- [x] Unit 6 — `fork()` warnings in parallel engine test
- [x] Unit 6 — `patterns_found` uninitialized bug
- [x] Unit 6 — `src/ml/selector.py` dead commented code
- [x] Unit 7 — `pyproject.toml`: stale excludes removed, `_archive` excluded, warning filters added
- [x] Unit 8 — `src/scrapers/fo_ban.py` parser picked row index instead of symbol (fixed + regression test added)
- [x] Unit 8 — `main.py` flag ordering undocumented (fixed: epilog hint added)
- [x] Unit 9 — `src/cli/menus.py` NameErrors fixed (LOGGER + Path)
- [x] Unit 9 — `.gitignore` cleaned (deduped, formatting bug repaired)
- [x] Unit 9 — PROJECT_MAP.md stale "duplicate validator methods" note corrected
- [x] Unit 10 — Ruff UP+I modernization applied across src/ + tests/ + root scripts
- [x] Unit 11 — Circular import `src.ui` ↔ `src.data` fixed (regression test added)
- [x] Unit 11 — 16 cold-start import tests added (test count 206 → 222)
- [x] Unit 12 — F401 unused imports cleanup (120 findings → 0)
- [x] Unit 12 — 15 shims hardened with `__all__`
- [x] Unit 12 — UP038 + UP031 residual fixes (10 manual)
- [x] Unit 12 — UP035 auto-resolved via F401
- [x] Unit 13 — `sync-history --resume` fixed (CLI no longer crashes)
- [x] Unit 13 — `screen --processed-dir` derives from `--data-dir`
- [x] Unit 13 — `screener.py` guards CLOSE<=0 in in-memory candle insert
- [x] Unit 13 — Real pipeline smoke test passed (2,699 symbols, 3 real OHLCV files, StockScreener output)
- [x] Unit 14 — Data quality audit of all 2,699 Parquet files (read-only)
- [x] Unit 15 — Add holidays config, fix health fallback, fix SyncRegistry date typing, incremental 1d bhavcopy sync
- [ ] Unit 16 (optional) — Whitespace cleanup OR fyers revival
- [ ] Ongoing — Any issues found during real usage
- [ ] `.gitignore` has duplicated `.env` / `.env.*` / `data/**` entries (cosmetic)
