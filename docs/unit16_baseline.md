# Unit 16 Phase 0: Baseline & Bug Verification Report

**Date:** 2026-10-16  
**Commit:** `8e93b85` (Unit 15 complete, clean tree)  
**Scope:** Verification of symbol analysis, SMC engine, consensus, scoring, and scanner issues prior to any modifications.

---

## 1. SMC Scan CLI Execution & Setup Breakdown

### Command Executed
```bash
uv run python main.py --data-dir data --hist-dir data/historical smc-scan
```

### Execution Output & Metrics
- **Securities Scanned:** 2,694 / 2,700 Parquet files in `data/historical/1d`.
- **Exit Code:** 0.
- **Total Actionable Decisions Generated:** 53.

### Call Breakdown by Setup Type
| Setup Type | Direction | Count | Percentage |
| :--- | :--- | :--- | :--- |
| `FVG_FILL` | BUY | 47 | 88.7% |
| `OB_DEMAND_TAP` | BUY | 4 | 7.5% |
| `OB_SUPPLY_TAP` | SELL | 2 | 3.8% |
| `FVG_FILL` | SELL | 0 | 0.0% |
| **Total** | | **53** | **100.0%** |

### Evaluation of Bug Claims
1. **Order Block Calls (Demand/Supply Tap):**
   - **Report Claim:** "0 OB_DEMAND_TAP / 0 OB_SUPPLY_TAP".
   - **Verification Finding:** **Partially refuted as absolute zero, but root cause confirmed.** Across the entire 2,694-stock universe, only 6 OB setups triggered (4 demand, 2 supply). The root cause in `src/engine/smc.py:273-293` is verified: `if touch_price <= ob.bar_high: ob.mitigated = True` deletes order blocks prematurely when price touches the top of the demand zone, rather than when price breaches the floor (`low < ob.bar_low`), which directly contradicts the reference LuxAlgo SMC Pine logic (`luxalgo_smc_source.pine:487,493`).
2. **Bearish FVG Calls:**
   - **Verification Finding:** **Confirmed (0 calls).** In `src/engine/smc_decision.py:118-148`, the `2. BEARISH SCENARIOS` block only checks `A. Bearish Order Block Test`. The `B. Bearish FVG Fill` handler is completely absent from the source code.
3. **CLI Formatting Artifact:**
   - **Verification Finding:** **Confirmed.** The scan produced lines:
     ```text
     None: Scanned 2694 securities.
     None: All calls committed to SQLite DB at: data/smc_calls.sqlite
     ```
     This is caused by `print(f"\n{ok('...')}: ...")` where `ok()` in `src/cli/formatters.py:139` prints directly and returns `None`.

---

## 2. Screener/Analyze CLI & Composite Rank Columns

### Code Inspection
- Checked `StockScreener.enrich_analysis` in `src/screener.py:1414-1541`.
- Checked `ScoringEngine` in `src/scoring/scoring_engine.py:15-103`.

### CSV Header Audit
Inspected existing processed outputs in `data/processed/`:
- `top_250_analyzed_20260526.csv`: 16 columns (no factor scores, no composite score, no rank).
- `analysis_results_—_2026-06-09_20260609_1507.csv`: 97 columns (no factor scores, no composite score, no rank).
- `consensus_leaderboard_20260601_1841.csv`: 61 columns (no factor scores, no composite score, no rank).

### Verification Finding
**CONFIRMED.** `ScoringEngine` exists as a complete 7-factor ranking engine (`TREND_FACTOR_SCORE`, `MOMENTUM_FACTOR_SCORE`, `CAR_FACTOR_SCORE`, `RISK_FACTOR_SCORE`, `VOLUME_FACTOR_SCORE`, `VOLATILITY_FACTOR_SCORE`, `CATALYST_FACTOR_SCORE`, `COMPOSITE_SCORE`, `RANK`), but is **never imported or invoked** in `StockScreener.screen_stocks` or `StockScreener.enrich_analysis`. Grep confirmed callers exist only in `src/dashboard/pages/01_daily_signals.py` and `tests/test_scoring.py`.

---

## 3. Data Directory Audit: `user_data/stock_data` vs `data/historical`

### Code Inspection
- `src/data/storage.py:350-353`:
  ```python
  self.timeframe = timeframe
  self.base_path = Path("user_data/stock_data") / timeframe
  ```
- `src/engine/scanner.py:123`:
  ```python
  data = self._get_data_optimized(symbol, primary_tf, "1y", shared_cache)
  # queries self.fetcher.fetch_data -> self.dataRepository.load_data(symbol)
  ```

### Filesystem Audit
- `user_data/stock_data/1d`: Contains **50 files** (Nifty 50), last modified Oct 15 01:44, ending at bar date `2026-10-14`.
- `data/historical/1d`: Contains **2,699 files** (full NSE equity universe), synced to `2026-10-15`.

### Git History & Pipeline Origin
- Checked commit `fa81afb`: `user_data/` is the storage tree imported from the legacy `screeni-py` merge.
- The canonical pipeline built throughout Units 1–15 uses `data/historical/1d`.
- **Finding:** The split was not an intentional architectural design for separate datasets; it is an incomplete convergence artifact. The `Scanner` (`UltraOptimizedMultiTimeframeScanner`) queries `DataRepository` and thus only finds the 50 cached Nifty stocks in `user_data/`, ignoring the 2,649 other stocks in `data/historical/1d`.

---

## 4. Live Path Audit: `src/analysis/patterns.py`

### Grep Audit Across Active Codebase
1. `src/engine/scanner.py:53, 134`:
   ```python
   from src.analysis.patterns import SMCPatterns
   ...
   smc = SMCPatterns.analyze_smc(data)
   ```
2. `src/ml/engineer.py:200-208`:
   ```python
   from src.analysis.SMCPatterns import SMCPatterns, WilliamsFractals
   bos = SMCPatterns.detect_bos(df)
   choch = SMCPatterns.detect_choch(df)
   ```
3. Callers of `scanner.py`:
   - `src/engine/orchestrator.py:15` (`MultiTimeframeScanner`)
   - `src/cli/interactive_scanner.py:198, 200, 202` (interactive Quick Scan, Custom Scan, Watchlist Scan)
   - `src/cli/actions.py:459` (`cmd_train_ml`, `cmd_run_optimizer`)

### Lookahead Analysis in `SMCPatterns.detect_order_blocks`
- Line 83: `next_close = data["Close"].shift(-1)`
- **Finding:** **CONFIRMED on live path.** When running scans through `interactive_scanner.py` or training models via `cmd_train_ml`, `SMCPatterns.analyze_smc` is invoked, which executes `detect_order_blocks` containing `shift(-1)`. This represents an active lookahead leak on that subsystem.

---

## 5. Phase 0 Summary of Findings

| Item | Component | Issue | Verification Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `smc.py` | Order block mitigation inverted | **Confirmed** (6/2,694 OB calls vs 47 FVG) | Fix in Phase 1 |
| 2 | `smc_decision.py` | Missing Bearish FVG fill | **Confirmed** (0 bearish FVG calls, branch missing) | Fix in Phase 1 |
| 3 | `formatters.py` | `ok()` prints and returns `None` | **Confirmed** (`None: Scanned...` in CLI output) | Fix in Phase 3 |
| 4 | `consensus_engine.py` | Dead branch `elif net_score >= 5.0` | **Confirmed** in line 270 | Fix in Phase 2 |
| 5 | `consensus_engine.py` | `is_nifty_bank` mapped to `^CNXPSUBANK` | **Confirmed** in line 68 | Fix in Phase 2 |
| 6 | `scoring_engine.py` | NaN volatility gets penalized 10.0 | **Confirmed** in line 255 | Fix in Phase 2 |
| 7 | `screener.py` | `ScoringEngine` not wired in `enrich_analysis` | **Confirmed** (composite columns missing) | Fix in Phase 2 |
| 8 | `scanner.py` | Sell SL/TP inverted for short calls | **Confirmed** in line 737 | Fix in Phase 3 |
| 9 | `scanner.py` | Rolling mean delta used as fake ATR | **Confirmed** in line 732 | Fix in Phase 3 |
| 10 | `daily_signals.py` | Dashboard prefers analyzed over enriched | **Confirmed** in line 89 | Fix in Phase 3 |
| 11 | `storage.py` | `DataRepository` points to `user_data` (50 stocks) | **Confirmed** merge artifact | Fix in Phase 3 |
| 12 | `patterns.py` | Lookahead `shift(-1)` in order blocks | **Confirmed** on live orchestrator/ML path | Fix in Phase 3 |

---

## 6. Phase 1 Results: SMC Core Fixes

### Before vs. After Universe Call Counts (2,694 Securities)
| Setup Type | Direction | Phase 0 (Before) | Phase 1 (After) | Net Change |
| :--- | :--- | :--- | :--- | :--- |
| `OB_DEMAND_TAP` | BUY | 4 | **36** | +32 (+800%) |
| `OB_SUPPLY_TAP` | SELL | 2 | **23** | +21 (+1050%) |
| `FVG_FILL` | BUY | 47 | **46** | -1 (1 moved to OB) |
| `FVG_FILL` | SELL | 0 | **4** | +4 (new setup) |
| **Total** | | **53** | **109** | **+56 (+105.7%)** |

### Implemented Predicate (`src/engine/smc.py:273-293`)
```python
        # Order Block Mitigation Check
        surviving_obs = []
        for ob in active_order_blocks:
            # Bullish OB (Demand): Mitigated when price violates the floor (bar_low)
            if ob.bias == BULLISH:
                breached = (c < ob.bar_low) if close_mitigation else (l < ob.bar_low)
                if breached:
                    ob.mitigated = True
                    ob.mitigated_bar_index = i
                else:
                    surviving_obs.append(ob)
            # Bearish OB (Supply): Mitigated when price violates the ceiling (bar_high)
            else:
                breached = (c > ob.bar_high) if close_mitigation else (h > ob.bar_high)
                if breached:
                    ob.mitigated = True
                    ob.mitigated_bar_index = i
                else:
                    surviving_obs.append(ob)
        active_order_blocks = surviving_obs[-max_order_blocks:]
```

### Reference Logic
- Sourced from `docs/pine_sources/luxalgo_smc_source.pine:487, 493` (`deleteOrderBlocks`):
  - Bearish OB: `bearishOrderBlockMitigationSource > eachOrderBlock.barHigh`
  - Bullish OB: `bullishOrderBlockMitigationSource < eachOrderBlock.barLow`
  - Source definitions (`luxalgo_smc_source.pine:311, 313`):
    `bearishOrderBlockMitigationSource = orderBlockMitigationInput == CLOSE ? close : high`
    `bullishOrderBlockMitigationSource = orderBlockMitigationInput == CLOSE ? close : low`

### Deliberately Preserved Behavior
1. **Config flag `close_mitigation`:** Maintained as a configurable argument (defaulting to `False`, matching LuxAlgo's default `HIGHLOW` wick-based mitigation).
2. **Proximity and Risk Thresholds in `smc_decision.py`:** Kept exact existing thresholds:
   - Max risk: 6% of CMP (`cmp * 0.06`).
   - Risk/Reward minimum: `rr >= 1.8`.
   - Proximity tap tolerance: 1.5% for OB (`ob.bar_low <= cmp <= ob.bar_high * 1.015`), 1.5x ATR for FVG.
3. **Bearish FVG Parameters:** Built symmetrically to Bullish FVG without introducing any speculative parameters.

