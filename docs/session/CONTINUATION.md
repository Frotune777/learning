# Project Continuation State

**Last updated:** 2026-10-15 (after Unit 5)
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
| 5 | (see git log HEAD) | Full pytest baseline — 205/205 PASSED, 19 warnings |

## Current Status

- **Completed:** Units 1, 2, 3, 4, 5
- **Current unit:** 5 — commit pending (Stage B)
- **Next unit:** 6 — Fix 2 real warnings + 2 real bugs from PROJECT_MAP
- **Project health:** ✅ 205/205 tests pass · ✅ 0 import failures · ✅ 0 shadows · ✅ 0 case duplicates · ⚠️ 19 warnings (2 ours)

## Next Unit Plan (Unit 6 Preview)

**Goal:** Fix 2 warnings owned by us + 2 real bugs documented in PROJECT_MAP. No scope creep — only the 4 items below.

**Real warnings (ours):**
1. `tests/test_fyers_fetcher.py:114` — `datetime.utcnow()` deprecated → use `datetime.now(timezone.utc)`
2. `tests/engine/test_parallel_engine.py` — 8× `fork()` on multi-threaded process → set `multiprocessing.set_start_method("spawn", force=True)` inside the test module (test-scoped, not global)

**Real bugs (documented, not exercised by tests):**
3. `src/engine/screener.py::validateCandlePatterns` — `patterns_found` used before initialization
4. `src/ml/selector.py` — 3 strategy classes commented out (silent no-op)

**Deliberately NOT fixed in Unit 6:**
- Third-party deprecation warnings (`advanced_ta`, `sklearn`) — suppressed via `pytest.ini` filterwarnings, not code changes
- Any other warnings from Python 3.13 stdlib

**After Unit 6:**
- Unit 7: `pyproject.toml` cleanup (stale `scratch`/`fyers` excludes; add pytest filterwarnings)
- Unit 8+: deeper src/ code review (only if warranted)

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
audits/ (project_audit.txt, project_backup.txt, project_bundle.txt, pytest_unit5_baseline.txt)
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
- [ ] Unit 6 — `tests/test_fyers_fetcher.py:114` — `datetime.utcnow()` deprecated
- [ ] Unit 6 — `tests/engine/test_parallel_engine.py` — `fork()` on multithreaded process
- [ ] Unit 6 — `src/engine/screener.py::validateCandlePatterns` — `patterns_found` undefined
- [ ] Unit 6 — `src/ml/selector.py` — strategies commented out
- [ ] Unit 7 — `pyproject.toml`: remove stale `scratch`/`fyers` excludes
- [ ] Unit 8 — `src/engine/screener.py` — duplicate validator methods
- [ ] Unit 14 — Revive parts of `_archive/legacy_root/fyers/` if needed
- [ ] `.gitignore` has duplicated `.env` / `.env.*` / `data/**` entries (cosmetic)
