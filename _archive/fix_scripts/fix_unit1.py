#!/usr/bin/env python3
"""
fix_unit_1.py — Unit 1: Safety + Canonical Codebase + Archive

Purpose:
  * Create _archive/ structure
  * Move duplicates / experiments (NOT delete) into _archive/
  * Generate PROJECT_MAP.md
  * Print a verification report

Safety:
  * Dry-run by default — pass --apply to actually move files.
  * Never deletes files.
  * Idempotent — safe to run multiple times.
  * Preserves git history via `git mv` when inside a git repo.

Usage:
  python fix_unit_1.py             # dry-run (preview)
  python fix_unit_1.py --apply     # actually move files + write PROJECT_MAP.md
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent

ARCHIVE_DIRS = [
    "_archive",
    "_archive/merge_this",
    "_archive/scratch",
    "_archive/legacy_tests",
    "_archive/legacy_root",
]

# (source, destination) — source can be file or directory
MOVES: list[tuple[str, str]] = [
    # Screeni-py copy — not referenced by src/
    ("merge this", "_archive/merge_this"),

    # Experimental scripts
    ("scratch", "_archive/scratch"),

    # Backup / one-off root files (kept for reference only)
    ("project_backup.py", "_archive/legacy_root/project_backup.py"),
    ("scan_project.py",   "_archive/legacy_root/scan_project.py"),
    ("check_yfinance_fixed.py", "_archive/legacy_root/check_yfinance_fixed.py"),
    ("screener_v2.py",    "_archive/legacy_root/screener_v2.py"),

    # Leaked credentials file — moved for safety, will be rewritten in Unit 14
    ("test_fyers.py",     "_archive/legacy_root/test_fyers.py"),
]

# These entry points MUST stay at root (we'll fix them in Unit 2)
PROTECTED_AT_ROOT = {
    "main.py",
    "interactive_scanner.py",
    "check_data_sources.py",
    "download_historical_data.py",
    "repair_data.py",
    "nse_data_fetcher.py",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        return p.returncode, (p.stdout + p.stderr).strip()
    except FileNotFoundError:
        return 127, "command not found"


def move(src: Path, dst: Path, apply: bool, git_available: bool) -> str:
    """
    Move src → dst. Returns a status string:
      'moved-git'    — moved via `git mv`
      'moved-shutil' — moved via shutil
      'skipped-<n>'  — source missing
      'conflict'     — destination already exists (renamed with timestamp)
    """
    if not src.exists():
        return f"skipped (not found): {src.relative_to(ROOT)}"

    dst.parent.mkdir(parents=True, exist_ok=True)

    # Handle destination conflict — timestamp the incoming file
    if dst.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if dst.is_dir():
            dst = dst.with_name(f"{dst.name}__{ts}")
        else:
            dst = dst.with_name(f"{dst.stem}__{ts}{dst.suffix}")
        note = f" (renamed due to conflict → {dst.name})"
    else:
        note = ""

    if not apply:
        return f"DRY-RUN would move: {src.relative_to(ROOT)} → {dst.relative_to(ROOT)}{note}"

    if git_available:
        rc, out = run(["git", "mv", str(src), str(dst)], cwd=ROOT)
        if rc == 0:
            return f"moved (git): {src.relative_to(ROOT)} → {dst.relative_to(ROOT)}{note}"
        # Fall through to shutil if git mv fails (e.g. file untracked)
    try:
        shutil.move(str(src), str(dst))
        return f"moved (shutil): {src.relative_to(ROOT)} → {dst.relative_to(ROOT)}{note}"
    except Exception as exc:  # noqa: BLE001
        return f"ERROR moving {src}: {exc}"


def check_gitignore() -> tuple[bool, list[str]]:
    """Return (exists, missing_patterns)."""
    gi = ROOT / ".gitignore"
    required = [
        ".env",
        ".env.*",
        "data/cache/fyers_token.txt",
        "*.sqlite",
        "__pycache__/",
        ".venv/",
    ]
    if not gi.exists():
        return False, required
    text = gi.read_text(encoding="utf-8", errors="ignore")
    missing = [p for p in required if p not in text]
    return True, missing


def check_env() -> tuple[bool, list[str]]:
    """Return (exists, missing_keys)."""
    env = ROOT / ".env"
    required = [
        "FYERS_API_KEY=",
        "FYERS_API_SECRET=",
        "FYERS_REDIRECT_URI=",
        "FYERS_ACCESS_TOKEN=",
    ]
    if not env.exists():
        return False, [k.rstrip("=") for k in required]
    text = env.read_text(encoding="utf-8", errors="ignore")
    missing = [k.rstrip("=") for k in required if k not in text]
    return True, missing


def ensure_env_and_gitignore(apply: bool) -> list[str]:
    """Create .env / .gitignore if missing; append missing keys."""
    actions: list[str] = []

    # --- .env ---
    env_path = ROOT / ".env"
    env_template = (
        "# Created by fix_unit_1.py — fill in your real values!\n"
        "FYERS_API_KEY=\n"
        "FYERS_API_SECRET=\n"
        "FYERS_REDIRECT_URI=https://trade.fyers.in/api-login/redirect-uri/index.html\n"
        "FYERS_ACCESS_TOKEN=\n"
        "TELEGRAM_BOT_TOKEN=\n"
        "TELEGRAM_CHAT_ID=\n"
    )
    if not env_path.exists():
        actions.append("DRY-RUN would create: .env")
        if apply:
            env_path.write_text(env_template, encoding="utf-8")
            actions[-1] = "created: .env"
    else:
        existing = env_path.read_text(encoding="utf-8", errors="ignore")
        missing_keys = [k for k in env_template.splitlines() if k.endswith("=") and k not in existing]
        if missing_keys:
            actions.append(f"DRY-RUN would append {len(missing_keys)} missing key(s) to .env")
            if apply:
                with env_path.open("a", encoding="utf-8") as fh:
                    fh.write("\n# Added by fix_unit_1.py\n")
                    for k in missing_keys:
                        fh.write(k + "\n")
                actions[-1] = f"appended {len(missing_keys)} key(s) to .env"
        else:
            actions.append("ok: .env already has all required keys")

    # --- .gitignore ---
    gi_path = ROOT / ".gitignore"
    gi_template = (
        "\n# Added by fix_unit_1.py\n"
        ".env\n"
        ".env.*\n"
        "data/cache/fyers_token.txt\n"
        "*.sqlite\n"
        "__pycache__/\n"
        ".venv/\n"
    )
    if not gi_path.exists():
        actions.append("DRY-RUN would create: .gitignore")
        if apply:
            gi_path.write_text(gi_template.lstrip(), encoding="utf-8")
            actions[-1] = "created: .gitignore"
    else:
        existing = gi_path.read_text(encoding="utf-8", errors="ignore")
        required = [".env", ".env.*", "data/cache/fyers_token.txt", "*.sqlite", "__pycache__/", ".venv/"]
        missing = [p for p in required if p not in existing]
        if missing:
            actions.append(f"DRY-RUN would append {len(missing)} pattern(s) to .gitignore")
            if apply:
                with gi_path.open("a", encoding="utf-8") as fh:
                    fh.write(gi_template)
                actions[-1] = f"appended {len(missing)} pattern(s) to .gitignore"
        else:
            actions.append("ok: .gitignore already has required patterns")

    return actions


# ---------------------------------------------------------------------------
# PROJECT_MAP.md content
# ---------------------------------------------------------------------------

PROJECT_MAP = """# Project Map

_Last updated by fix_unit_1.py on {ts}_

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
- `fyers/`   — OpenAlgo broker integration (⚠ missing parents `utils.*`, `database.*`)
- `scripts/` — profile_scan.py
- `tests/`   — pytest suite

## Archived (do NOT delete — reference only)
- `_archive/merge_this/`   — old Screeni-py copy (imports `screeni.*`)
- `_archive/scratch/`      — old experiments
- `_archive/legacy_root/`  — old root scripts / backups
- `_archive/legacy_tests/` — old test scripts

## Known Issues (fix order)
- [ ] Unit 2  — Root scripts import legacy paths (`src.data.DataRepository`, `src.data.Fetcher`, `src.ui.StockUniverseSelector`)
- [ ] Unit 3  — `src/scanners/__init__.py` — `BreakoutStrategy` imported twice (shadowing)
- [ ] Unit 8  — `src/engine/screener.py::validateCandlePatterns` — `patterns_found` undefined
- [ ] Unit 9  — `src/ml/selector.py` — strategies commented out
- [ ] Unit 14 — `fyers/` — broken imports (`utils.httpx_client`, `database.token_db`)
- [ ] Unit 3  — Case-duplicate files: `Momentum.py` / `momentum.py`, `Trend.py` / `trend.py`
- [ ] Unit 8  — Duplicate validator methods in `src/engine/screener.py`

## Credentials policy
- All secrets live in `.env` (gitignored).
- `data/cache/fyers_token.txt` is per-day and gitignored.
- Historical leaked creds archived at `_archive/legacy_root/test_fyers.py` — MUST be revoked.
"""


def write_project_map(apply: bool) -> str:
    target = ROOT / "PROJECT_MAP.md"
    content = PROJECT_MAP.format(ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if not apply:
        return f"DRY-RUN would write: PROJECT_MAP.md ({len(content)} chars)"
    target.write_text(content, encoding="utf-8")
    return f"wrote: PROJECT_MAP.md ({len(content)} chars)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Unit 1 fixer — safe, dry-run by default.")
    parser.add_argument("--apply", action="store_true", help="Actually perform moves and file writes.")
    args = parser.parse_args()

    apply = args.apply
    mode = "APPLY" if apply else "DRY-RUN"

    print("=" * 78)
    print(f"fix_unit_1.py — mode: {mode}")
    print(f"root: {ROOT}")
    print("=" * 78)

    # --- Header checks ---
    git_repo = is_git_repo(ROOT)
    print(f"git repo detected: {git_repo}")

    leaked = ROOT / "test_fyers.py"
    if leaked.exists():
        print("⚠️  test_fyers.py found at root — it contains hardcoded Fyers credentials.")
        print("    → Revoke the API secret NOW (outside the IDE).")
        print("    → This script will move it to _archive/legacy_root/ for reference.")

    env_exists, env_missing = check_env()
    gi_exists, gi_missing = check_gitignore()
    print(f".env         exists={env_exists} missing_keys={env_missing}")
    print(f".gitignore   exists={gi_exists} missing_patterns={gi_missing}")
    print()

    # --- 1) Archive dirs ---
    print("-" * 78)
    print("STEP 1: create archive directories")
    print("-" * 78)
    for rel in ARCHIVE_DIRS:
        d = ROOT / rel
        if d.exists():
            print(f"  ok      : {rel}/")
        else:
            print(f"  {'created' if apply else 'DRY-RUN would create'}: {rel}/")
            if apply:
                d.mkdir(parents=True, exist_ok=True)
    print()

    # --- 2) Moves ---
    print("-" * 78)
    print("STEP 2: move duplicates / experiments into _archive/")
    print("-" * 78)
    for src_rel, dst_rel in MOVES:
        src = ROOT / src_rel
        dst = ROOT / dst_rel
        # If src is a file and dst is a dir path ending without suffix, keep file name
        if src.is_file() and not Path(dst_rel).suffix:
            dst = dst / src.name
        status = move(src, dst, apply=apply, git_available=git_repo)
        print(f"  {status}")
    print()

    # --- 3) .env + .gitignore ---
    print("-" * 78)
    print("STEP 3: ensure .env and .gitignore")
    print("-" * 78)
    for line in ensure_env_and_gitignore(apply=apply):
        print(f"  {line}")
    print()

    # --- 4) PROJECT_MAP.md ---
    print("-" * 78)
    print("STEP 4: PROJECT_MAP.md")
    print("-" * 78)
    print(f"  {write_project_map(apply=apply)}")
    print()

    # --- 5) Sanity check — protected files ---
    print("-" * 78)
    print("STEP 5: sanity check — protected root files")
    print("-" * 78)
    for name in sorted(PROTECTED_AT_ROOT):
        p = ROOT / name
        print(f"  {'present' if p.exists() else 'MISSING':8} : {name}")
    print()

    # --- Final summary ---
    print("=" * 78)
    print("DONE" if apply else "DRY-RUN COMPLETE")
    print("=" * 78)
    if not apply:
        print("Nothing was changed. Re-run with --apply to execute.")
    else:
        print("All moves and file writes are complete.")
        print("Next: run `git status` and commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())