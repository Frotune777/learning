# Project Continuation State

**Last updated:** 2026-10-15 (after Unit 6)
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

## Commit History

| Unit | Commit | Description |
|------|--------|-------------|
| 1 | `fa81afb` | Archive duplicates, harden .env/.gitignore, add PROJECT_MAP |
| 2 | `61a2d27` | Quarantine orphaned fyers/, archive stale profile_scan.py, untrack runtime log |
| 3 | `31c4c90` | Reorganize root — pine sources, session docs, audits, exports, debug to subdirs |
| 4 | `d4d3660` | Fix BreakoutStrategy shadowing + archive case-duplicate shims |
| 5 | `0a6af31` | Full pytest baseline — 205/205 PASSED, 19 warnings |
| 6 | (see git log HEAD) | Fix 5 items: utcnow×2, fork spawn, patterns_found bug, selector cleanup |

## Current Status

- **Completed:** Units 1–6
- **Current unit:** 6 — commit pending (Stage B)
- **Next unit:** 7 — `pyproject.toml` cleanup + pytest filterwarnings
- **Project health:** ✅ 205/205 tests pass · ✅ 0 import failures · ✅ 0 shadows · ✅ warnings reduced from 19 → ~10 (remaining are third-party only)

## Next Unit Plan (Unit 7 Preview)

**Goal:** Clean up `pyproject.toml` and add pytest warning filters so
third-party deprecations stop polluting test output.

**Scope:**
- Remove stale `scratch` from `[tool.ruff]` / `[tool.mypy]` exclude lists
  (scratch/ was archived in Unit 3)
- Remove stale `fyers` from exclude lists (fyers/ archived in Unit 2)
- Add `[tool.pytest.ini_options] filterwarnings` for the 2 third-party
  warning categories we don't control:
    * advanced_ta bitwise `~` deprecation
    * sklearn All-NaN slice RuntimeWarning
- Do NOT change dependency versions or add new packages

**After Unit 7:**
- Unit 8: Fix remaining documented bugs (if any) from PROJECT_MAP
- Unit 9+: First-run validation of `main.py` CLI subcommands with real data

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
audits/ (project_audit.txt, project_backup.txt, project_bundle.txt, pytest_unit5_baseline.txt, pytest_unit6_postfix.txt)
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
- [ ] Unit 7 — `pyproject.toml`: remove stale `scratch`/`fyers` excludes
- [ ] Unit 8 — `src/engine/screener.py` — duplicate validator methods
- [ ] Unit 9+ — First-run validation of `main.py` CLI subcommands against real NSE data
- [ ] Unit 14 — Revive parts of `_archive/legacy_root/fyers/` if needed
- [ ] `.gitignore` has duplicated `.env` / `.env.*` / `data/**` entries (cosmetic)
