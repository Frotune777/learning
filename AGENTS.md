# AGENTS.md: Fortune Analytical Decision-Support System (Fortune ADSS)

## Canonical Operating Rules for All AI Agents

1. **System Identity & Scope:**
   - **Application Name:** **Fortune Analytical Decision-Support System (Fortune ADSS)** (never Sharegenius).
   - **Purpose:** 100% Analytical Decision-Support & Technical Screening.
   - **Order Execution Boundary:** Strictly ZERO live broker trade placement or execution.

2. **Offline-First Data Architecture:**
   - The platform operates **OFFLINE by default** against the local Parquet data lake in `data/historical/1d/` (~2,966 symbols stored).
   - On startup, the system reports data currency. If the user prompts to download, use the **3-tier cascade:**
     1. **Yahoo Finance (`yfinance`)**
     2. **Fyers API v3 (`fyers`)** (if token authenticated)
     3. **NSE Website Chart Direct Scraper (`nse_charts`)**
   - Once data is synced, all screeners, strategies, and backtesters operate on stored files until the user explicitly toggles to Live Mode.

3. **No-Scan Policy (State Ledger):**
   - **DO NOT** execute recursive scans across the 200+ files in this repository to "understand" the project.
   - Read [`PROJECT_MAP.md`](PROJECT_MAP.md) and [`PROJECT_DOSSIER.md`](PROJECT_DOSSIER.md) first. They contain the canonical architecture, package map, and data schemas.
   - Use the skill [`.agents/skills/fortune-adss-tracker/SKILL.md`](.agents/skills/fortune-adss-tracker/SKILL.md) for state synchronization.

4. **Maintenance & Ledger Sync:**
   - Whenever any file is added, modified, or deleted under `src/` or `data/`, run:
     ```bash
     uv run python scripts/update_project_state.py
     ```
   - This keeps `PROJECT_MAP.md` synchronized with exact date boundaries and git commit info.
