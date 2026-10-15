# Project Continuation State

**Last updated:** 2026-10-15 (after Unit 3)
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
| 3 | (pending) | Reorganize root — pine sources, session docs, audits, exports, debug to subdirs |

## Current Status

- **Completed:** Units 1, 2, 3 (pending commit)
- **Current unit:** 3 — Stage C commit pending
- **Next unit:** 4 — `src/__init__.py` audit (discovery only, no edits)
- **Project health:** ✅ `src/` imports cleanly · ✅ 205 tests collected · ✅ 0 project-wide import errors (excluding `_archive/`)

## Next Unit Plan (Unit 4 Preview)

**Goal:** Audit every `__init__.py` in `src/` for shadowed re-exports, circular imports, missing `__all__` declarations.

**Scope:**
- READ-ONLY discovery (Stage A)
- No code edits in Unit 4
- Deliverable: an inventory of shadowed names / circular risks

**Known targets (from bundle):**
- `src/scanners/__init__.py` — `BreakoutStrategy` imported twice
- `src/analysis/indicators/__init__.py` — dual casing (`Momentum.py` vs `momentum.py`)
- `src/engine/__init__.py` — may re-export old scanner aliases

**After Unit 4:**
- Unit 5: First full `pytest tests/ -v` run (run, don't fix)
- Unit 6: `pyproject.toml` cleanup (stale `scratch`/`fyers` excludes)
- Unit 7+: Layer-by-layer fix pass (only if real bugs surface)

## Key Decisions Log

- **`src/` is canonical.** `merge this/` (Screeni-py) archived. `fyers/` (OpenAlgo) archived.
- **`src.nse_bhavcopy/fyers_fetcher.py` is the real Fyers integration** — has 20 live references, remains active.
- **Root scripts are all healthy** — no import fixes needed (Stage A of Unit 2 confirmed).
- **`logs/data_repair.log` untracked** — runtime artifact, not source.
- **`.agents/` and `.antigravitycli/` kept tracked** — IDE config, needed by agent.
- **`fix_unit1.py` archived** — one-time migration helper, no longer needed.
- **Pine files moved to `docs/pine_sources/`** — upstream reference for `src/engine/lux_*.py` ports.

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
legacy_tests/ (empty — reserved for future)
audits/ (project_audit.txt, project_backup.txt, project_bundle.txt)
exports/ (Exported_Grouped_Strategies*.csv)
debug/ (nse_charting_response_TCS.json, scan_profile.prof, tests_baseline.txt)
fix_scripts/ (fix_unit1.py)


## How to Resume in a New Chat

See `docs/session/RESUME_PROMPT.md` — paste its contents at the start of any new chat.

## Known Issues (open)

- [ ] Unit 4 — Audit `__init__.py` files for shadowed imports
- [ ] Unit 5 — Run full pytest, triage failures
- [ ] Unit 6 — Clean stale `scratch`/`fyers` excludes in `pyproject.toml`
- [ ] Unit 14 — Revive parts of `_archive/legacy_root/fyers/` (optional)
- [ ] `src/engine/screener.py::validateCandlePatterns` — `patterns_found` undefined (bug)
- [ ] `src/ml/selector.py` — strategies commented out (dead code)
- [ ] Case-duplicate files in `src/analysis/indicators/` (`Momentum.py` vs `momentum.py`)
- [ ] Duplicate validator methods in `src/engine/screener.py`
- [ ] `.gitignore` has duplicated `.env` / `.env.*` / `data/**` entries (cosmetic)
