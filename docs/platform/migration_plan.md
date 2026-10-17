NSE Platform Migration Plan & Parity Gates (v2)

Status: Approved Implementation Roadmap (Pre-Phase 0)
Strategy: Phased Non-Breaking Dual-Run Migration (Zero Big-Bang)
Baseline commit: 7c78d9f
Python: 3.13.13 (required by powernse ≥ 3.13)
Safety invariant: The existing system (main.py, src/dashboard/app.py, scripts/dq_gate.sh) remains 100% operational and green after every phase. No phase advances without its Parity Gate passing with an attached diff report.
0. Technology stack & sources
Layer	Primary source	License	Decision
Landing	powernse 0.7.0 (PyPI)	MIT	✅ Fork + wrap as LandingLoader
Staging	nsefast collectors (selective)	MIT	⚠️ Copy collectors/ for domains powernse lacks
Warehouse	nse-warehouse (Frotune777/nse-warehouse)	MIT (confirmed)	✅ Fork + vendor corporate_actions.py, schema.py, quality.py
Marts	Custom	—	Build (unique sector/surveillance work)
Orchestration	Custom (single Python runner)	—	Build
SCD2/PIT patterns	hyperdb DESIGN.md	Reference only	📖 Read docs, do not copy code

Non-negotiable dependency changes:

    pyproject.toml: requires-python = ">=3.13" (bumped from >=3.12)

    uv add powernse — resolves cleanly with pandas 2.2.3, pyarrow 19.0.1, duckdb 1.1.3

    Vendor nse-warehouse under vendor/nse-warehouse/ — MIT attribution in commit message

DuckDB architecture (correction to prior plan): Single DuckDB connection querying Parquet via zero-copy views, not 3 physical .duckdb files:
text

Parquet raw files ──view──> bars ──view──> bars_adjusted ──view──> features

This avoids single-writer file lock conflicts and matches nse-warehouse's actual implementation.
1. Phased architecture overview
text

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Phase 0     │──> │     Phase A     │──> │     Phase B     │──> │     Phase B.5   │──> │     Phase C     │──> │   Phase D+E     │
│  Scaffolding &  │    │  Shadow Ingest  │    │ Warehouse Views │    │ Master Enrich   │    │   First Mart    │    │ Cutover & Prune │
│  Contract Stubs │    │  (powernse)     │    │  (nse-warehouse)│    │  (Tier 1+2 NSE) │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
   • Schemas (.yaml)      • Landing storage      • dim_* + fact_*         • ISIN + sector           • marts.enriched_        • dq_view -> dossier
   • Typed exceptions     • Staging Parquets       via DuckDB views         • Index membership         daily                   • screener_view -> CLI
   • Abstract DAL         • powernse wrapper      • DQ Gate writes           • ASM/GSM/ESM            • Parity vs legacy       • dq-check LAST
   • Lineage writer       • Zero consumer           to fact_dq_run          • Surveillance fact                                 • Archive legacy (90d)
   • nse-warehouse vendor   impact

Total effort: 17 days (~3 weeks), down from 24.
Phase	Days	Cumulative
0 — Scaffolding	1	1
A — Landing (powernse)	2	3
B — Warehouse views	3	6
B.5 — Master enrichment	5	11
C — First mart	1	12
D — Consumer cutover	4	16
E — Decommission	1	17
2. Phase-by-phase specifications & parity gates
Phase 0 — Scaffolding, Schemas, Contract Stubs & Dependencies

Establishes foundational type safety, schema definitions, contract interfaces, and external dependencies before any data moves.

Objective: Create the platform skeleton, staging YAML schemas, abstract DAL interface, repository stubs, typed exception hierarchy, lineage writer, and wire in powernse + vendor nse-warehouse.

Deliverables:

    pyproject.toml — requires-python = ">=3.13", powernse added

    vendor/nse-warehouse/ — MIT-licensed fork (add to .gitignore if not committing; document choice)

    src/platform/exceptions.py — typed hierarchy (PlatformError, SchemaValidationError, LineageIntegrityError, WarehouseConstraintViolation, DataQualityHaltError)

    src/platform/schemas.py — YAML loader with signature definitions and type mapping (~30 LOC real code)

    src/platform/dal.py — abstract DALInterface with all entity methods (~50 LOC)

    src/platform/repositories/ — stubs: symbol_repo.py, price_repo.py, ta_repo.py, delivery_repo.py, signal_repo.py, dq_repo.py, index_repo.py, corporate_action_repo.py

    src/platform/lineage.py — batch ID, SHA-256, manifest writer (~40 LOC)

    src/platform/migrations/runner.py — up/down with empty migration list (~40 LOC)

    src/platform/loaders/ — stubs: landing.py, staging.py, warehouse.py

    src/platform/orchestrator.py — CLI dispatcher stub

    schemas/staging/*.yaml — six schemas: price_daily, delivery_daily, corporate_actions, equity_master, surveillance, index_membership

Dependencies: powernse, pyyaml, pyarrow, duckdb (all present or resolvable)
Time: 1 day, ~150 net LOC for platform (plus vendored code)
🛡️ PARITY GATE 0 → A: Contract, Schema & Dependency Readiness
bash

# 1. Verify powernse installs cleanly
uv run python -c "import powernse; print('powernse:', powernse.__version__)"

# 2. Verify nse-warehouse license
head -3 vendor/nse-warehouse/LICENSE  # must show MIT

# 3. Verify platform imports
uv run python -c "
from src.platform.exceptions import PlatformError, SchemaValidationError
from src.platform.schemas import load_schema
from src.platform.dal import DALInterface
from src.platform.lineage import compute_file_sha256, write_manifest
from src.platform.repositories.symbol_repo import SymbolRepo
from src.platform.repositories.price_repo import PriceRepo
from src.platform.repositories.signal_repo import SignalRepo
from src.platform.repositories.dq_repo import DQRepo

for name in ['price_daily', 'delivery_daily', 'corporate_actions',
             'equity_master', 'surveillance', 'index_membership']:
    schema = load_schema(f'schemas/staging/{name}.yaml')
    assert 'columns' in schema, f'Schema {name} missing columns'
    print(f'Schema {name}: {len(schema[\"columns\"])} columns validated')
print('PARITY GATE 0->A: PASSED')
"

# 4. Verify no regressions
uv run pytest -q  # must be 290+ passing

Expected output: powernse version printed, MIT license confirmed, 6 schemas validated, all existing tests green.
Fail-stop rule: If powernse import fails, LICENSE is not MIT, or any existing test regresses, STOP and report.
Phase A — Shadow Ingest via powernse

Runs the new immutable landing layer and canonical staging pipeline in parallel with current downloads, wrapping powernse instead of building downloaders from scratch.

Objective: Ingest Bhavcopy and Fyers bars into data/landing/ and write validated data/staging/ Parquets without touching data/historical/1d/*.parquet.

Entry criteria: Parity Gate 0 → A passed. All existing tests green.

Exact commands run:
bash

# 1. Shadow ingest via powernse wrapper
uv run python -m src.platform.orchestrator ingest --source nse_bhavcopy --trade-date 2026-10-16

# 2. Stage the downloaded batch into canonical typed Parquets
uv run python -m src.platform.orchestrator stage --batch-id bhavcopy_20261016_001

Implementation notes:

    LandingLoader in src/platform/loaders/landing.py wraps powernse.BhavcopyDownloader

    Adopt powernse's nse-data/ tree layout under data/landing/ — this gives manifest with SHA-256 for free

    StagingLoader reads landing batch, transforms to canonical schema, writes data/staging/price_daily/dt=YYYY-MM-DD/

Rollback: rm -rf data/landing/ data/staging/. Existing pipeline files untouched.

Time: 2 days.
🛡️ PARITY GATE A → B: Landing → Staging Parity
bash

uv run python -c "
import json, pandas as pd
with open('data/landing/nse_bhavcopy/2026-10-16/bhavcopy_20261016_001/manifest.json') as f:
    manifest = json.load(f)
stg_df = pd.read_parquet('data/staging/price_daily/dt=2026-10-16/')

assert len(stg_df) == manifest['row_count'], f'Count: {len(stg_df)} vs {manifest[\"row_count\"]}'
assert stg_df['symbol'].isna().sum() == 0, 'Null symbols'
assert stg_df['trade_date'].isna().sum() == 0, 'Null trade_date'
assert (stg_df['high'] >= stg_df['low']).all(), 'high < low'
assert (stg_df['close'] > 0).all(), 'close <= 0'
print(f'PARITY GATE A->B: PASSED ({len(stg_df)} rows)')
"

Expected: exact 1:1 row count parity; 0 nulls in keys; 0 OHLC violations.
Fail-stop: If staging loses a single symbol or prices drift, halt before warehouse load. Attach diff report.
Phase B — Warehouse via DuckDB Views (adapted from nse-warehouse)

Builds the DuckDB warehouse catalog using the view-over-Parquet pattern proven by nse-warehouse. Single connection, no physical .duckdb file splitting.

Objective: Create dimensional model in DuckDB; register zero-copy views over staging + historical Parquets; populate dimensions; backfill fact_price_daily and fact_ta_daily; connect DQ gate to fact_dq_run.

Entry criteria: Parity Gate A → B passed.

Exact commands run:
bash

# 1. Apply DDL migrations
uv run python -m src.platform.migrations.runner migrate

# 2. Seed dimensions (dim_date from holidays.json; dim_symbol from equity master; dim_index; dim_source)
uv run python -m src.platform.orchestrator seed-dimensions

# 3. Register views over Parquet (zero-copy)
uv run python -m src.platform.orchestrator register-views

# 4. Backfill warehouse facts from staging + data/historical/1d/*.parquet
uv run python -m src.platform.orchestrator backfill-warehouse --source-dir data/historical/1d/

# 5. Ingest existing DQ gate logs into fact_dq_run
uv run python -m src.platform.orchestrator backfill-dq --runs-log logs/dq/runs.jsonl

Implementation notes:

    Single data/warehouse.duckdb catalog — contains dims, facts, and view definitions

    Views registered from Parquet: CREATE VIEW bars AS SELECT * FROM read_parquet('data/staging/price_daily/*.parquet')

    Vendor corporate_actions.py and quality.py from nse-warehouse for adjustment logic and DQ checks

    Adapt bench/run_bench.py (single file wins on query speed; partition only for incremental rebuilds)

Rollback: Delete data/warehouse.duckdb. Re-run legacy tests. Zero consumer dependencies shifted.

Time: 3 days (down from 5).
🛡️ PARITY GATE B → C: Staging → Warehouse Parity
sql

-- 1. Foreign key integrity (must return 0)
SELECT count(*) FROM fact_price_daily f
LEFT JOIN dim_symbol s ON f.symbol_sk = s.symbol_sk
WHERE s.symbol_sk IS NULL;

-- 2. Date dimension integrity (must return 0)
SELECT count(*) FROM fact_price_daily f
LEFT JOIN dim_date d ON f.date_sk = d.date_sk
WHERE d.date_sk IS NULL;

-- 3. Historical depth parity (TCS sample)
SELECT count(*) AS rows, min(trade_date) AS first_date, max(trade_date) AS last_date
FROM fact_price_daily f
JOIN dim_symbol s ON f.symbol_sk = s.symbol_sk
WHERE s.symbol = 'TCS';

Expected: 0 orphan FKs; rows matches len(TCS.parquet) exactly; date bounds match to the day.
Fail-stop: If any FK violation or symbol count mismatch, halt before mart build.
Phase B.5 — Master Enrichment (Tier 1 + Tier 2)

Populates dim_symbol with full identity + classification, fact_index_membership with history, fact_symbol_surveillance with daily snapshots. This is genuinely unique work — no existing project covers it.

Objective: Move from ~20% master coverage to ~90%. Add ISIN, sector/industry, F&O flags, ASM/GSM/ESM state, index membership history.

Entry criteria: Parity Gate B → C passed.

Tier 1 sources (CSV, no auth):

    EQUITY_L.csv → ISIN, listing_date, market_lot, face_value

    25 index constituent CSVs → sector, industry, membership

    fo_mktlots.csv → is_fo_eligible, fo_lot_size

    sec_list.csv → is_t2t

Tier 2 sources (session cookies):

    api/reportASM → is_asm, asm_stage

    /reports/gsm → is_gsm, gsm_stage

    /reports/esm → is_esm

Exact commands run:
bash

uv run python -m src.platform.orchestrator enrich-master --tiers 1 2

Implementation notes:

    SCD2 change detection on dim_symbol: tracked attributes hashed; change → close old row, insert new

    fact_index_membership: current snapshot only (weights deferred to Tier 3)

    fact_symbol_surveillance: daily snapshot; time-varying by design

    Adopt powernse manifest.json for source batch tracking

Rollback: Revert dim_symbol to snapshot source; drop surveillance table.

Time: 5 days.
🛡️ PARITY GATE B.5

    dim_symbol row count matches master snapshot (allowing SCD2 duplicates)

    Sample: TCS ISIN matches EQUITY_L.csv

    Sample: HDFCBANK sector = "Financial Services"

    fact_index_membership has 25 indices populated

    fact_symbol_surveillance has today's snapshot

Phase C — First Analytical Mart

Builds and materializes marts.enriched_daily as a DuckDB view over facts (not a physical table — matching nse-warehouse's view pattern).

Objective: Produce a single denormalized dataset matching the exact columns expected by screener algorithms and dashboard views.

Entry criteria: Parity Gate B → C and B.5 passed.

Exact commands run:
bash

uv run python -m src.platform.orchestrator build-marts --as-of 2026-10-16

Implementation notes:

    mart_enriched_daily is a view, not a table — 0 storage overhead

    Extend nse-warehouse's feature.duckdb view chain: bars_adjusted → features → mart_enriched_daily

    Add your 7-factor composite, consensus, portfolio action columns

Rollback: DROP VIEW IF EXISTS mart_enriched_daily; DROP VIEW IF EXISTS mart_consensus_daily; etc.

Time: 1 day (down from 3).
🛡️ PARITY GATE C → D: Mart vs Legacy Engine Parity
bash

uv run python -c "
import pandas as pd
from src.platform.dal import DAL

legacy_df = pd.read_parquet('data/historical/1d/TCS.parquet')
legacy = legacy_df.iloc[-1]
mart = DAL().get_enriched_symbol('TCS', '2026-10-16')

assert abs(legacy['close'] - mart['close']) < 1e-4
assert abs(legacy.get('ema_50', 0) - mart['ema_50']) < 1e-3
assert abs(legacy.get('rsi_14', 0) - mart['rsi_14']) < 1e-2
assert int(legacy.get('weinstein_stage', 0)) == int(mart['weinstein_stage'])
print('PARITY GATE C->D: PASSED')
"

Expected: numerical delta < 0.001 for all MAs/RSI; exact categorical match (Weinstein Stage 4 for TCS).
Fail-stop: If any indicator diverges, block Phase D cutover until calculation matches.
Phase D — Consumer Cutover (One-by-One)

Sequentially points consumers to src/platform/dal.py. Each cutover is a discrete git commit.

Strict execution order:

    src/dashboard/views/dq_view.py — reads fact_dq_run + dim_symbol via DAL

    src/dashboard/views/dossier_view.py — reads prices + indicators via DAL

    src/dashboard/views/screener_view.py — reads marts.enriched_daily via DAL

    CLI screeners (cmd_screen, cmd_smc_scan) — write to fact_signal_daily

    scripts/dq_gate.sh and cmd_dq_check — LAST (points to warehouse assertions)

Rollback: Git revert the specific view commit. Legacy files remain until Phase E.

Time: 4 days.

Per-consumer parity: byte-identical output (where files produced), numeric match (where UI), no perf regression > 20%.
Phase E — Decommission Legacy Paths

Retires dead storage directories, removes bypassing CLI commands, organizes archive.

Entry criteria: All 8 dashboard tabs and CLI workflows verified against DAL. All tests green.

Exact commands run:
bash

mkdir -p data/archive/
mv data/processed/ data/archive/
mv user_data/ data/archive/
mv data/screener_output/ data/archive/
mv data/smc_calls.sqlite data/archive/
mkdir -p data/archive/historical_csvs/
mv data/historical/*.csv data/archive/historical_csvs/
tar -czf data/archive/legacy_1d_parquets.tar.gz data/historical/1d/
# Keep data/historical/1d/ read-only for 90-day burn-in

Time: 1 day.

Parity Gate E: warehouse row counts match archived parquet counts; all consumers work exclusively through DAL; zero file reads outside src/platform/.
3. Decisions & governance ledger
Resolved architectural decisions
#	Decision	Resolution	Rationale
1	Staging retention	Keep forever	~3 GB for 20 years; provides file-based auditability
2	Corporate actions	Unadjusted in fact, adjusted in mart	Kimball standard; auditability against NSE Bhavcopy
3	Warehouse storage	Single DuckDB + nightly Parquet backup	Vectorized perf; backup mitigates single-file risk
4	Surrogate keys	DuckDB sequences	Native, compact, no hash collisions
5	Consumer cutover	dq_view → dossier_view → screener_view → CLI → dq-check LAST	Migrate readers first; keep the safety net until mature
6	Phase E archival	90 days (up from 60)	Parquets are fallback if DuckDB corrupts
7	DAL return types	DTOs for singles; DataFrames for series; no plain dicts	Type safety
8	Signal retention	Permanent	~20 MB/year; walk-forward validation needs full history
9	DAL time-series type	Pandas with dtype_backend='pyarrow'	Drop-in for all existing consumers; mechanical Polars swap later
10	nse-warehouse source	Fork Frotune777/nse-warehouse (MIT confirmed)	Legally forkable; saves ~2 days vendor adaptation
11	DuckDB layering	Single connection + zero-copy views over Parquet	Avoids single-writer file lock; matches actual nse-warehouse impl
12	Python version	>= 3.13 (bumped from >=3.12)	Required by powernse 0.7.0
13	Ingestion foundation	powernse 0.7.0 (fork + wrap)	Saves ~1 day; handles cookies, retries, XBOM calendar, manifests
14	Dossier column convention	Rename report_delisted_in_summary → report_inactive_in_summary	Consistency with Unit 19A artifact rename

No pending decisions. All 14 architectural forks are locked.
4. Anti-patterns (must not reproduce)
Pattern	Where it exists	Why forbidden
Consumer globs files directly	screener_view.py	No DAL, no schema guarantee
Producer writes CSV as primary output	screener.py → data/historical/*.csv	CSVs are exports, not storage
Silent overwrite on write	historical_sync._save	No lineage, no idempotency key
Hardcoded paths in modules	storage.py Path("user_data/stock_data")	Paths belong in Config
Snapshot with no history	nse_equity_master_*.parquet	Cannot answer "what was true on X?"
Boolean flags for time-varying facts	25 is_nifty_* columns	Cannot express rebalancing
Two storage patterns for same fact	data/historical/1d/ and user_data/stock_data/	Duplication, drift
Parallel ingestion logic	historical_sync vs bhavcopy_incremental	Duplication; unify through loaders
Implicit module-level state	_GLOBAL_CACHE in scanner	Not testable, not safe
except: pass	Scattered	Swallows errors
print() in library code	Various	Use logging
Untyped dicts as returns	Various	Use DTOs
Physical .duckdb per layer	(proposed, now rejected)	Single-writer lock conflicts; use views
5. Immediate next action
bash

# 1. Bump Python version
sed -i 's/requires-python = ">=3.12"/requires-python = ">=3.13"/' pyproject.toml

# 2. Add powernse
uv add powernse

# 3. Verify
uv run python -c "import powernse; print(powernse.__version__)"

# 4. Fork + vendor nse-warehouse
gh repo fork Frotune777/nse-warehouse --clone
mkdir -p vendor/
mv nse-warehouse vendor/
# Add vendor/ to .gitignore OR commit with MIT attribution

# 5. Begin Phase 0 scaffolding per Section 2

Estimated total to L4 analytics capability: 17 days (~3 weeks).