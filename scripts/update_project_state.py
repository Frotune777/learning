#!/usr/bin/env python3
"""
scripts/update_project_state.py
Purpose: Automatically audits and syncs Fortune ADSS project state, data lake recency,
         and component inventory into PROJECT_MAP.md.
"""

from __future__ import annotations

import datetime
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.config import get_stored_data_info

PROJECT_MAP_PATH = REPO_ROOT / "PROJECT_MAP.md"


def get_git_info() -> tuple[str, str]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        commit = "unknown"

    try:
        status_lines = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
        ).strip().splitlines()
        dirty = f"{len(status_lines)} modified/untracked files" if status_lines else "clean"
    except Exception:
        dirty = "unknown"

    return commit, dirty


def sync_project_map() -> None:
    now_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit, git_status = get_git_info()
    data_info = get_stored_data_info(str(REPO_ROOT / "data/historical/1d"))

    latest_date = data_info.get("latest_date") or "N/A"
    symbols_count = data_info.get("symbol_count", 0)
    days_behind = data_info.get("days_behind", 0)

    header = f"""# Project Map: Fortune Analytical Decision-Support System (Fortune ADSS)

_Last synchronized on: **{now_iso}** | Commit: `{commit}` ({git_status})_

## ⚡ System Status & Operational Boundaries
- **App Name:** Fortune Analytical Decision-Support System (Fortune ADSS)
- **Default Mode:** 📁 **OFFLINE (Stored Data Lake)**
- **Local Data Lake:** **{symbols_count:,}** symbols stored through **{latest_date}** ({days_behind} days behind exchange)
- **Data Source Order:** **1st Yahoo Finance → 2nd Fyers API v3 (if connected) → 3rd NSE Website Chart Scraper**
- **Trading Boundary:** 100% Decision-Support & Screening — strictly ZERO live broker order execution
- **Startup Recency Check:** Prompts to pull new data only when behind; operates offline on stored data by default
"""

    if not PROJECT_MAP_PATH.exists():
        PROJECT_MAP_PATH.write_text(header, encoding="utf-8")
        print(f"Created {PROJECT_MAP_PATH}")
        return

    content = PROJECT_MAP_PATH.read_text(encoding="utf-8")
    # Replace everything before "## Canonical package" or first section
    if "## Canonical package:" in content:
        parts = content.split("## Canonical package:", 1)
        new_content = header.rstrip() + "\n\n## Canonical package:" + parts[1]
    else:
        new_content = header + "\n\n" + content

    PROJECT_MAP_PATH.write_text(new_content, encoding="utf-8")
    print(f"✔ Synchronized {PROJECT_MAP_PATH} (Stored date: {latest_date}, Symbols: {symbols_count})")


if __name__ == "__main__":
    sync_project_map()
