# Unit 20 Phase 20.0 — Dashboard Diagnostic & Architecture Audit

**Date:** 2026-10-16  
**Commit Baseline:** `7d44e5f` (Unit 19C complete)  
**Scope:** Systematic audit of the Streamlit dashboard architecture (`src/dashboard/app.py`), view layer (`src/dashboard/views/`), legacy multipage files (`src/dashboard/pages/`), and data pipeline artifact wiring.

---

## 1. Live UI Confirmation & Entry Point Routing

- **Live Entry Point:** `src/dashboard/app.py` is the sole configured application entry point. It implements a top-horizontal navigation bar via `streamlit_option_menu` with 6 tabs:
  1. SMC Studio (`render_smc_view`)
  2. Technical Screener (`render_screener_view`)
  3. Portfolio Risk (`render_portfolio_view`)
  4. Backtest Explorer (`render_backtest_view`)
  5. Quantitative / Macro (`render_quantitative_view`)
  6. Data Sources & Gateway (`render_fyers_view`)
- **Sidebar Suppression:** `src/dashboard/theme.py` explicitly injects CSS hiding Streamlit's default left sidebar:
  ```css
  [data-testid="stSidebar"], section[data-testid="stSidebar"] {
      display: none !important;
  }
  [data-testid="collapsedControl"] {
      display: none !important;
  }
  ```
- **Legacy Multipage Isolation:** Streamlit native multipage discovery relies on `src/dashboard/pages/*.py` appearing in the sidebar navigation. Because the sidebar is hidden by CSS and `app.py` does not import or route to any file in `src/dashboard/pages/`, all files in `pages/` are **completely unreachable** in the live application.
- **Codebase Grep Findings:** No production code in `src/` or `main.py` imports `src/dashboard/pages/`. The only reference across the entire repository is in `tests/test_dashboard_file_selection.py`, which tests the file selection heuristic inline without importing the legacy page.

---

## 2. Audit of Existing Views (`src/dashboard/views/`)

### View 1: `screener_view.py`
| Attribute | Details |
|:---|:---|
| **Files / APIs Read** | `glob.glob("data/processed/screen_stocks_*.csv")` |
| **Expected Columns / Keys** | `CAR_Category`, `Volume_Spike_10d`, `Composite_Score`, `SYMBOL`, `SCREENER_STRATEGIES[i]["col"]` |
| **Pipeline Reality** | Pipeline writes to `data/historical/top_250_enriched_*.csv` and `data/historical/top_250_analyzed_*.csv`. No files matching `screen_stocks_*.csv` exist. Real columns are `CAR_RATING`, `VOL_SPIKE`, `COMPOSITE_SCORE`, `SYMBOL`, and strategy action columns `STR_<ID>_ACTION`. `SCREENER_STRATEGIES` in `config.py` uses `file_prefix`, not `col`. |
| **Mismatches & Bugs** | 1. **Stale Glob:** Searches for `data/processed/screen_stocks_*.csv` (0 matches).<br>2. **KeyError:** Accesses `s["col"]` from `SCREENER_STRATEGIES` which only contains `name`, `file_prefix`, `description`, `category`. Filter crashes immediately.<br>3. **Column Drift:** References `CAR_Category`, `Volume_Spike_10d`, and `Composite_Score` (case mismatch). |

### View 2: `portfolio_view.py`
| Attribute | Details |
|:---|:---|
| **Files / APIs Read** | `st.session_state["portfolio_cash"]`, `st.session_state["portfolio_positions"]` |
| **Expected Columns / Keys** | Expects `portfolio_positions` to be a `list` of dicts (`symbol`, `qty`, `entry_price`, `current_price`, `stop_loss`, `target`, `unrealized_pnl`). |
| **Pipeline Reality** | The canonical domain engine `src.portfolio.portfolio_engine.Portfolio` manages `positions` as a `dict[str, dict[str, Any]]` keyed by uppercase symbol. Legacy `02_portfolio.py` also used `dict`. |
| **Mismatches & Bugs** | 1. **Schema Collision:** Uses a `list` rather than the canonical `dict` schema from `Portfolio`.<br>2. **Engine Disconnect:** Does not invoke `Portfolio` methods (`can_add`, `add_position`, `exit_position`, `get_sector_exposures`, `to_dataframe`).<br>3. **Missing Features:** No position exit/close mechanism or sector limit enforcement. |

### View 3: `quantitative_view.py`
| Attribute | Details |
|:---|:---|
| **Files / APIs Read** | `data/historical/1d/*.parquet`, calls `calculate_weinstein_stage`, `calculate_vsa_bars`. |
| **Expected Columns / Keys** | Parquet `close`, `date`. Tab MMI expects sentiment metrics. |
| **Pipeline Reality** | Parquet files are present in `data/historical/1d/`. `src.scrapers.mmi_scraper.fetch_mmi_score()` is available to scrape/extract real-time Tickertape MMI scores and sentiment regimes. |
| **Mismatches & Bugs** | 1. **Hardcoded Placeholder:** Tab MMI displays hardcoded static HTML (`GREED`, `64.2 / 100`, Advance/Decline `1.42`, VIX `14.71`) instead of invoking `fetch_mmi_score()`.<br>2. **Arbitrary Slice:** Weinstein table hardcodes `files[:30]` slicing first 30 alphabetical files. |

### View 4: `backtest_view.py`
| Attribute | Details |
|:---|:---|
| **Files / APIs Read** | `data/historical/1d/*.parquet`, calls `NSEEventBacktester`, `add_ta_indicators`. |
| **Expected Columns / Keys** | Parquet `Open`, `High`, `Low`, `Close`, `Volume`. Indicator columns `55D_HIGH`, `20D_LOW`, `SMA_100`, `ADX_14`, `PLUS_DI_14`, `MINUS_DI_14`, `RSI_14`, `SMA_150`, `SMA_200`. Backtest result dict (`total_return_pct`, `max_drawdown_pct`, `total_trades`, `final_value`, `history`). |
| **Pipeline Reality** | Parquet files and backtester implementation match the expected signature and output dictionary schema. |
| **Mismatches & Bugs** | Functional and correctly wired. Minor enhancement possible to support additional strategies from `SCREENER_STRATEGIES`. |

### View 5: `smc_view.py`
| Attribute | Details |
|:---|:---|
| **Files / APIs Read** | `data/smc_calls.sqlite` via `SMCDatabase()`, `data/historical/1d/*.parquet`. Calls LuxAlgo engines (`calculate_smc`, `calculate_nwe`, `calculate_savgol`, `calculate_sweeps_ifvgs`, `calculate_volume_profile`, `generate_smc_call`, `generate_symbol_llm_dossier`). |
| **Expected Columns / Keys** | Database table `trading_calls` (`id`, `symbol`, `timestamp`, `direction`, `setup_type`, `entry_price`, `stop_loss`, `target_1`, `target_2`, `risk_reward`, `status`, `notes`). |
| **Pipeline Reality** | Table `trading_calls` in `data/smc_calls.sqlite` contains 409 records. All current records are in `PENDING` status. |
| **Mismatches & Bugs** | Functional and aligned with Unit 16 Phase 1/2 SMC fixes. Contains an embedded mini-dossier expander on the right pane. |

### View 6: `fyers_view.py`
| Attribute | Details |
|:---|:---|
| **Files / APIs Read** | Environment variables (`BROKER_API_KEY`, `BROKER_API_SECRET`, `FYERS_API_KEY`, `FYERS_API_SECRET`, `FYERS_REDIRECT_URI`). Calls `DataSourceManager`, `FyersFetcher`. |
| **Expected Columns / Keys** | `DataSourceManager.get_status_summary()` dict keys (`historical_active`, `live_active`, `fyers`, `parquet_cache`). |
| **Pipeline Reality** | `DataSourceManager` and `FyersFetcher` match the expected contracts. |
| **Mismatches & Bugs** | Functional. Prompts for broker credentials when environment variables are not populated. |

---

## 3. Audit of Legacy Multipage Directory (`src/dashboard/pages/`)

| Page File | Reachability | Classification | Justification & Migration Plan |
|:---|:---:|:---:|:---|
| `01_daily_signals.py` | Unreachable | **MIGRATABLE** | Contains advanced filtering, multi-strategy `_BUY_VALS` mapping, KPI cards (`In Bull Run`, `High Conviction`, `GTT Setups`), and priority display column formatting for `top_250_enriched_*.csv`. Migrate logic into `src/dashboard/views/screener_view.py` before pruning. |
| `02_portfolio.py` | Unreachable | **MIGRATABLE** | Integrates directly with `src.portfolio.portfolio_engine.Portfolio` using the canonical `dict` schema, supports position close/exit transactions, and renders sector limit allocations. Migrate logic into `src/dashboard/views/portfolio_view.py` before pruning. |
| `03_backtest_explorer.py` | Unreachable | **DEAD** | Direct prototype of `src/dashboard/views/backtest_view.py`. Contains no unique logic. Safe for deletion. |
| `04_strategy_inspector.py` | Unreachable | **DEAD** | Legacy screeni-py Format 5/6 inspector for `top_250_analyzed_*.csv`. Superceded by enriched screener views. Safe for deletion. |
| `05_unified_scanner.py` | Unreachable | **DEAD** | Wrapper around legacy `run_unified_scanner`. Superceded by `screener_view.py`. Safe for deletion. |
| `06_smc_calls.py` | Unreachable | **DEAD** | Earlier prototype of `src/dashboard/views/smc_view.py`. `smc_view.py` has superior geometry, NWE, VP, and Sweeps. Safe for deletion. |
| `07_fyers_auth.py` | Unreachable | **DEAD** | Prototype of `src/dashboard/views/fyers_view.py`. Fully absorbed into `fyers_view.py`. Safe for deletion. |

---

## 4. Required New Views & UI Panels (Units 17–19 Artifacts)

### 1. Data Quality Gate Panel (`src/dashboard/views/dq_view.py`)
- **Artifacts Consumed:**
  - `logs/dq/runs.jsonl`: Line-delimited audit runs from Unit 17 & 19A.
  - `logs/dq/symbols.jsonl`: Symbol-level inspection logs with classification (`HEALTHY`, `STALE_TRADING`, `INACTIVE`).
  - `data/historical/inactive_symbols.csv`: Canonical inactive/delisted registry (287 symbols, 90+ days inactive).
- **Core Capabilities Needed:**
  - Latest Gate Status KPI: Pass/Halt banner, failure rate % vs. threshold (8.0%), symbols checked.
  - Bucket Breakdown: Metrics for Healthy (2,212), Inactive (287), Stale Trading (114), Low Coverage (87), Stale TA (0).
  - Historical Run Log: Interactive table of the last 20 gate runs from `runs.jsonl`.
  - Inactive Universe Table: Searchable table of `data/historical/inactive_symbols.csv` with last trade date and inactivity duration.
  - Actionable Stale Triage Table: Recent 100 failing symbols from `symbols.jsonl` requiring operator attention.

### 2. LLM Quantitative Dossier Panel (`src/dashboard/views/dossier_view.py`)
- **Artifacts Consumed:**
  - `data/historical/1d/*.parquet`: 2,700 available equity tickers.
  - `TCS_LLM_DOSSIER.md` & `data/llm_reports/*.md`: Pre-generated dossiers from Unit 18.
  - `src.engine.llm_report.generate_symbol_llm_dossier()`: Real-time dossier synthesis engine.
- **Core Capabilities Needed:**
  - Ticker Selection: Searchable selectbox over all 2,700 Parquet tickers (defaults to `TCS`).
  - On-Demand Generation: Streamlit action button calling `generate_symbol_llm_dossier(symbol)`.
  - Rich Markdown Viewer: Render formatted multi-factor quantitative dossier directly in Streamlit via `st.markdown()`.
  - Markdown Download: One-click export of `{symbol}_LLM_DOSSIER.md`.

---

## 5. Navigation & Session State Modernization Plan

1. **Option Menu Expansion in `src/dashboard/app.py`:**
   Expand top-horizontal options to 8 modules:
   - `SMC Studio` (`crosshair`)
   - `Technical Screener` (`funnel`)
   - `Portfolio Risk` (`briefcase`)
   - `Backtest Explorer` (`graph-down`)
   - `Quantitative / Macro` (`pie-chart`)
   - `Data Quality Gate` (`shield-check`)
   - `LLM Dossier` (`file-earmark-text`)
   - `Broker & Data Gateway` (`database-gear`)
2. **Canonical Portfolio State Schema:**
   Standardize `st.session_state["portfolio_positions"]` to `dict[str, dict[str, Any]]` across all views, ensuring full compatibility with `src.portfolio.portfolio_engine.Portfolio`.
3. **Dead Code Cleanup:**
   Delete `src/dashboard/pages/` after migrating relevant signal filtering and portfolio exit logic.
